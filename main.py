"""
TITAN NEON ULTRA — Android-friendly Kivy starter app (upgraded)
Run in Pydroid 3 with Kivy support. Keep API keys private.

Install: pip install kivy requests (Plyer is optional; Android native TTS fallback is included)
Features: AI chat, image generation, gallery, notes, memory, calculator, settings.
"""
import ast
import json
import math
import os
import re
import shutil
import threading
import socket
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.image import AsyncImage, Image
from kivy.uix.video import Video
from kivy.core.audio import SoundLoader
from kivy.uix.widget import Widget

try:
    from plyer import filechooser
except Exception:
    filechooser = None

APP_NAME = "TITAN NEON ULTRA"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
POLLINATIONS_URL = "https://gen.pollinations.ai/image/"
POLLINATIONS_VIDEO_URL = "https://gen.pollinations.ai/video/"
POLLINATIONS_AUDIO_URL = "https://gen.pollinations.ai/audio/"
BASE_DIR = Path(__file__).resolve().parent
# Android APK assets are read-only. User data must live in app-private writable storage.
DATA_DIR = BASE_DIR / "titan_neon_data"
MEDIA_DIR = DATA_DIR / "gallery"
SETTINGS_FILE = DATA_DIR / "settings.json"
NOTES_FILE = DATA_DIR / "notes.json"
MEMORY_FILE = DATA_DIR / "memory.json"
CHATS_FILE = DATA_DIR / "chats.json"
PROJECTS_FILE = DATA_DIR / "projects.json"
PROMPTS_FILE = DATA_DIR / "prompts.json"


def configure_data_dirs(app):
    global DATA_DIR, MEDIA_DIR, SETTINGS_FILE, NOTES_FILE, MEMORY_FILE
    global CHATS_FILE, PROJECTS_FILE, PROMPTS_FILE
    if platform == "android":
        DATA_DIR = Path(app.user_data_dir) / "titan_neon_data"
    else:
        DATA_DIR = BASE_DIR / "titan_neon_data"
    MEDIA_DIR = DATA_DIR / "gallery"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    NOTES_FILE = DATA_DIR / "notes.json"
    MEMORY_FILE = DATA_DIR / "memory.json"
    CHATS_FILE = DATA_DIR / "chats.json"
    PROJECTS_FILE = DATA_DIR / "projects.json"
    PROMPTS_FILE = DATA_DIR / "prompts.json"
    for folder in (DATA_DIR, MEDIA_DIR):
        folder.mkdir(parents=True, exist_ok=True)

# TITAN Light/Dark themes. Colors are normalized RGBA values.
THEMES = {
    "Light": {
        "BG": (1.0, 1.0, 1.0, 1),
        "PANEL": (0.98, 0.98, 0.98, 1),       # #FAFAFA
        "PANEL2": (0.94, 0.94, 0.94, 1),
        "CYAN": (0.08, 0.32, 0.68, 1),       # accessible blue accent
        "PURPLE": (0.31, 0.25, 0.58, 1),
        "WHITE": (0.08, 0.08, 0.08, 1),      # foreground text
        "MUTED": (0.35, 0.35, 0.35, 1),
        "GREEN": (0.08, 0.42, 0.25, 1),
    },
    "Dark": {
        "BG": (0.071, 0.071, 0.071, 1),       # #121212
        "PANEL": (0.118, 0.118, 0.118, 1),    # #1E1E1E
        "PANEL2": (0.16, 0.16, 0.16, 1),
        "CYAN": (0.35, 0.72, 1.0, 1),
        "PURPLE": (0.72, 0.58, 0.98, 1),
        "WHITE": (0.95, 0.95, 0.95, 1),
        "MUTED": (0.68, 0.68, 0.68, 1),
        "GREEN": (0.35, 0.82, 0.55, 1),
    },
}
BG = THEMES["Dark"]["BG"]
PANEL = THEMES["Dark"]["PANEL"]
PANEL2 = THEMES["Dark"]["PANEL2"]
CYAN = THEMES["Dark"]["CYAN"]
PURPLE = THEMES["Dark"]["PURPLE"]
WHITE = THEMES["Dark"]["WHITE"]
MUTED = THEMES["Dark"]["MUTED"]
GREEN = THEMES["Dark"]["GREEN"]


def apply_theme(name):
    """Update shared theme colors; invalid values safely fall back to Dark."""
    global BG, PANEL, PANEL2, CYAN, PURPLE, WHITE, MUTED, GREEN
    palette = THEMES.get(name, THEMES["Dark"])
    BG, PANEL, PANEL2 = palette["BG"], palette["PANEL"], palette["PANEL2"]
    CYAN, PURPLE = palette["CYAN"], palette["PURPLE"]
    WHITE, MUTED, GREEN = palette["WHITE"], palette["MUTED"], palette["GREEN"]


def load_json(path, fallback):
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value
    except (OSError, ValueError, TypeError):
        return fallback


def save_json(path, value):
    """Atomic JSON save; returns False rather than crashing the UI."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
        temp.replace(path)
        return True
    except (OSError, TypeError, ValueError):
        return False


def safe_math(expression):
    """Evaluate a deliberately small arithmetic grammar without eval/exec."""
    if not expression or len(expression) > 100:
        raise ValueError("Enter a short arithmetic expression.")
    tree = ast.parse(expression, mode="eval")
    binary = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }
    unary = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}

    def visit(node, depth=0):
        if depth > 30:
            raise ValueError("Expression is too deeply nested.")
        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError("Number is too large.")
            return value
        if isinstance(node, ast.UnaryOp) and type(node.op) in unary:
            return unary[type(node.op)](visit(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            left = visit(node.left, depth + 1)
            right = visit(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e12):
                raise ValueError("Power is too large.")
            result = binary[type(node.op)](left, right)
            if isinstance(result, complex) or not math.isfinite(result) or abs(result) > 1e100:
                raise ValueError("Result is too large or unsupported.")
            return result
        raise ValueError("Only numbers, parentheses, and basic arithmetic are allowed.")

    return visit(tree)


class NeonButton(Button):
    def __init__(self, text="", accent="cyan", **kwargs):
        super().__init__(text=text, **kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = WHITE
        self.font_size = "12sp"
        self.bold = True
        self.size_hint_y = None
        self.height = dp(40)
        self._accent = PURPLE if accent == "purple" else CYAN
        with self.canvas.before:
            Color(*PANEL2)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
            Color(*self._accent)
            self._outline = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(9)), width=1.0)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._outline.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(9))


class NeonCard(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.padding, self.spacing = dp(9), dp(5)
        with self.canvas.before:
            Color(*PANEL)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(11)])
            Color(*CYAN)
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(11)), width=0.8)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(11))


class TitanApp(App):
    def build(self):
        self.title = APP_NAME
        Window.clearcolor = BG
        configure_data_dirs(self)
        if platform != "android":
            Window.size = (360, 680)
        self.settings = load_json(SETTINGS_FILE, {
            "groq_key": "", "pollinations_key": "",
            "personality": "You are TITAN, a friendly, honest, supportive AI. Explain clearly and admit uncertainty.",
            "memory_enabled": True,
            "theme": "Dark",
            "model": DEFAULT_MODEL,
            "video_model": "google/veo-3.1-fast",
            "voice": "nova",
            "voice_auto_play": False,
        })
        apply_theme(self.settings.get("theme", "Dark"))
        Window.clearcolor = BG
        self.notes = load_json(NOTES_FILE, [])
        self.memories = load_json(MEMORY_FILE, [])
        self.chats = load_json(CHATS_FILE, [])
        self.projects = load_json(PROJECTS_FILE, [{"name": "General", "created": datetime.now().isoformat(timespec="minutes")}])
        self.prompts = load_json(PROMPTS_FILE, [])
        self.active_project = "General"
        self.current_messages = []
        self.current_chat_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.status_text = "READY"
        self.root_box = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(8))
        with self.root_box.canvas.before:
            Color(*BG)
            self._root_bg = RoundedRectangle(pos=self.root_box.pos, size=self.root_box.size)
        self.root_box.bind(pos=self._update_root_bg, size=self._update_root_bg)
        self.show_home()
        return self.root_box

    def _update_root_bg(self, *_):
        self._root_bg.pos, self._root_bg.size = self.root_box.pos, self.root_box.size

    def clear(self):
        self.root_box.clear_widgets()

    def label(self, text, size=14, color=WHITE, height=None, bold=False, halign="left"):
        label = Label(text=str(text), color=color, font_size=f"{size}sp", bold=bold,
                      halign=halign, valign="middle", size_hint_y=None,
                      height=dp(height or max(26, size * 2)))
        label.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        return label

    def input_box(self, hint, text="", multiline=False, height=48, password=False):
        return TextInput(text=text, hint_text=hint, multiline=multiline, password=password,
                         size_hint_y=None, height=dp(height), padding=[dp(12), dp(10)],
                         background_normal="", background_active="", background_color=PANEL2,
                         foreground_color=WHITE, hint_text_color=MUTED, cursor_color=CYAN,
                         font_size="15sp")

    def header(self, title, subtitle="YOUR PERSONAL AI"):
        row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        back = NeonButton(text="HOME", accent="purple")
        back.size_hint_x, back.width = None, dp(82)
        back.bind(on_release=self.show_home)
        row.add_widget(back)
        titles = BoxLayout(orientation="vertical", spacing=0)
        titles.add_widget(self.label(title, 18, CYAN, 28, True))
        titles.add_widget(self.label(subtitle, 10, MUTED, 18))
        row.add_widget(titles)
        return row

    def set_page(self, title, subtitle="TITAN NEON ULTRA"):
        self.clear()
        self.root_box.add_widget(self.header(title, subtitle))

    def add_status(self, text=None):
        """Update one status line instead of adding a new label each time."""
        if text is not None:
            self.status_text = text

        current = getattr(self, "_status_label", None)
        if current is not None and current.parent is self.root_box:
            current.text = self.status_text
            return

        self._status_label = self.label(self.status_text, 10, GREEN, 22)
        self.root_box.add_widget(self._status_label)

    def popup(self, title, message):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        lab = Label(text=str(message), color=WHITE, halign="left", valign="middle")
        lab.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        box.add_widget(lab)
        close = NeonButton(text="CLOSE")
        box.add_widget(close)
        pop = Popup(title=title, content=box, size_hint=(0.9, 0.48),
                    auto_dismiss=False, title_color=CYAN, separator_color=PURPLE)
        close.bind(on_release=pop.dismiss)
        pop.open()

    def show_home(self, *_):
        self.page = "HOME"
        self.clear()

        # Compact Obsidian Gold dashboard; text-only labels avoid Android missing-glyph boxes.
        top = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        brand = self.label("TITAN", 18, CYAN, 30, True)
        top.add_widget(brand)
        top.add_widget(self.label("OBSIDIAN GOLD", 9, MUTED, 24, True))
        top.add_widget(Widget())
        settings_quick = NeonButton(text="SETTINGS", accent="purple")
        settings_quick.size_hint_x = None
        settings_quick.width = dp(76)
        settings_quick.height = dp(32)
        settings_quick.bind(on_release=self.show_settings)
        top.add_widget(settings_quick)
        self.root_box.add_widget(top)

        # Gold divider under the brand bar.
        with self.root_box.canvas.after:
            Color(*CYAN)
            self._home_rule = Line(points=[0, 0, 100, 0], width=1.0)
        def update_rule(*_):
            self._home_rule.points = [self.root_box.x + dp(2), self.root_box.top - dp(42),
                                      self.root_box.right - dp(2), self.root_box.top - dp(42)]
        self.root_box.bind(pos=update_rule, size=update_rule)
        Clock.schedule_once(update_rule, 0)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), scroll_type=["bars", "content"])
        dashboard = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None, padding=[dp(1), dp(5), dp(1), dp(5)])
        dashboard.bind(minimum_height=dashboard.setter("height"))

        hero = NeonCard(orientation="vertical", size_hint_y=None, height=dp(222), spacing=dp(2))
        logo_path = BASE_DIR / "titan_logo.png"
        if logo_path.is_file():
            hero.add_widget(Image(source=str(logo_path), size_hint=(1, None), height=dp(112),
                                  allow_stretch=True, keep_ratio=True))
        hero.add_widget(self.label("YOUR PERSONAL AI SYSTEM", 9, MUTED, 17, True, "center"))
        hero.add_widget(self.label("TITAN", 30, CYAN, 36, True, "center"))
        hero.add_widget(self.label("NEON ULTRA", 14, WHITE, 22, True, "center"))
        hero.add_widget(self.label("CREATE  /  THINK  /  SPEAK  /  IMAGINE", 9, MUTED, 17, True, "center"))
        ready = "CHAT SYSTEM CONNECTED" if self.settings.get("groq_key") else "SETUP: ADD YOUR CHAT KEY IN SETTINGS"
        hero.add_widget(self.label(ready, 8, GREEN if self.settings.get("groq_key") else MUTED, 17, True, "center"))
        dashboard.add_widget(hero)

        dashboard.add_widget(self.label("WORKSPACE", 10, CYAN, 19, True))
        grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        items = [
            ("AI CHAT", self.show_chat, "cyan"),
            ("PHOTO STUDIO", self.show_studio, "purple"),
            ("AI VIDEO LAB", self.show_video_lab, "purple"),
            ("VOICE LAB", self.show_voice_lab, "cyan"),
            ("IMAGE GALLERY", self.show_gallery, "cyan"),
            ("NOTES", self.show_notes, "purple"),
            ("MEMORY", self.show_memory, "cyan"),
            ("CALCULATOR", self.show_calculator, "purple"),
            ("CHAT PRO", self.show_chat_history, "purple"),
            ("SYSTEM HEALTH", self.show_health_center, "cyan"),
            ("PROJECT WORKSPACES", self.show_projects, "purple"),
            ("PROMPT VAULT", self.show_prompt_vault, "cyan"),
            ("BACKUP & SECURITY", self.show_backup_center, "purple"),
        ]
        for title, fn, accent in items:
            button = NeonButton(text=title, accent=accent)
            button.height = dp(39)
            button.font_size = "11sp"
            button.bind(on_release=fn)
            grid.add_widget(button)
        dashboard.add_widget(grid)

        quick = NeonCard(orientation="vertical", size_hint_y=None, height=dp(58), spacing=dp(2))
        quick.add_widget(self.label("BUILT FOR YOUR NEXT BIG IDEA", 9, CYAN, 17, True))
        quick.add_widget(self.label("Images, video, voice and your ideas in one workspace.", 9, MUTED, 22))
        dashboard.add_widget(quick)
        scroll.add_widget(dashboard)
        self.root_box.add_widget(scroll)
        self.add_status()
        self.root_box.add_widget(self.label("TITAN NEON ULTRA  /  MOBILE EDITION", 8, MUTED, 15, False, "center"))

    def _persist_chat(self):
        record = {"id": self.current_chat_id, "date": datetime.now().isoformat(timespec="minutes"),
                  "title": next((c.get("title") for c in self.chats if c.get("id") == self.current_chat_id and c.get("title")), ""),
                  "messages": self.current_messages}
        for index, chat in enumerate(self.chats):
            if chat.get("id") == self.current_chat_id:
                self.chats[index] = record
                break
        else:
            self.chats.append(record)
        save_json(CHATS_FILE, self.chats)

    def show_chat(self, *_):
        self.page = "CHAT"
        self.set_page("TITAN CHAT", "TALK • ASK • BUILD")
        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            scroll_type=["bars", "content"],
        )
        self.chat_scroll = scroll
        self.chat_area = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.chat_area.bind(minimum_height=self.chat_area.setter("height"))
        scroll.add_widget(self.chat_area)
        self.root_box.add_widget(scroll)
        for item in self.current_messages:
            self.add_chat_bubble(item.get("role", "assistant"), item.get("content", ""), persist=False)
        self.chat_input = self.input_box("Type a message...", multiline=True, height=76)
        self.root_box.add_widget(self.chat_input)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        send, new = NeonButton(text="SEND MESSAGE"), NeonButton(text="NEW CHAT", accent="purple")
        send.bind(on_release=self.send_chat)
        new.bind(on_release=self.new_chat)
        row.add_widget(send)
        row.add_widget(new)
        self.root_box.add_widget(row)
        self.add_status()

    def add_chat_bubble(self, role, content, persist=True):
        """Add a message bubble whose height follows its actual wrapped text."""
        if not hasattr(self, "chat_area"):
            return

        # Providers sometimes return HTML line breaks; Kivy labels need newlines.
        content = str(content)
        content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)

        color = CYAN if role == "assistant" else PURPLE
        bubble = NeonCard(orientation="vertical", size_hint_y=None)
        bubble.bind(minimum_height=bubble.setter("height"))

        bubble.add_widget(self.label(
            "TITAN" if role == "assistant" else "YOU",
            10, color, 20, True
        ))

        text = Label(
            text=content,
            color=WHITE,
            font_size="14sp",
            halign="left",
            valign="top",
            size_hint_y=None,
        )

        def update_text_width(*_):
            text.text_size = (max(dp(100), bubble.width - dp(30)), None)

        text.bind(width=lambda *_: update_text_width())
        text.bind(
            texture_size=lambda instance, size:
            setattr(instance, "height", size[1] + dp(8))
        )
        bubble.bind(width=lambda *_: update_text_width())
        bubble.add_widget(text)

        if role == "assistant":
            speak = NeonButton(text="SPEAK RESPONSE", accent="purple")
            speak.height = dp(34)
            speak.bind(on_release=lambda _btn, t=content: self.speak_text(t))
            bubble.add_widget(speak)

        self.chat_area.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.15)

        if persist:
            self.current_messages.append({"role": role, "content": content})
            self._persist_chat()

    def new_chat(self, *_):
        self._persist_chat()
        self.current_messages = []
        self.current_chat_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.show_chat()

    def send_chat(self, *_):
        message = self.chat_input.text.strip()
        if not message:
            return
        key = self.settings.get("groq_key", "").strip()
        if not key:
            self.popup("API KEY NEEDED", "Open SETTINGS and add your Groq API key first.")
            return
        self.chat_input.text = ""
        self.add_chat_bubble("user", message)
        self.add_status("TITAN IS THINKING...")
        # Explicit, user-controlled memory: only save when the user asks TITAN to remember.
        self._remember_from_explicit_request(message)
        # Snapshot a bounded amount of recent history on the UI thread.
        history = self._build_context_history()
        threading.Thread(target=self._chat_worker, args=(message, key, history), daemon=True).start()

    def _remember_from_explicit_request(self, message):
        """Save only clear 'remember that/this:' requests; never auto-profile users."""
        match = re.match(r"^\s*(?:titan[, :]\s*)?(?:please\s+)?remember\s+(?:that\s+|this\s*:?\s*)?(.+)$",
                         message, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return
        text = match.group(1).strip()[:700]
        if len(text) < 3:
            return
        # Avoid silently storing credentials or highly private contact details.
        sensitive_terms = ("password", "passcode", "api key", "secret key", "access token",
                           "private key", "credit card", "bank account")
        if any(term in text.lower() for term in sensitive_terms):
            Clock.schedule_once(lambda dt: self.popup(
                "MEMORY NOT SAVED", "For safety, TITAN will not auto-save passwords, keys, or financial credentials."), 0)
            return
        normalized = text.casefold()
        if any(str(item.get("text", "")).casefold() == normalized for item in self.memories):
            return
        self.memories.append({"text": text, "date": datetime.now().isoformat(timespec="minutes"),
                              "source": "explicit chat request"})
        self.memories = self.memories[-100:]
        if save_json(MEMORY_FILE, self.memories):
            Clock.schedule_once(lambda dt: self.add_status("MEMORY SAVED"), 0)

    def _build_context_history(self, max_chars=18000, max_messages=30):
        """Keep recent turns under a conservative character budget (not a token guarantee)."""
        selected = []
        used = 0
        for item in reversed(self.current_messages[-max_messages:]):
            content = str(item.get("content", ""))
            if not content:
                continue
            if used + len(content) > max_chars:
                remaining = max_chars - used
                if remaining < 300:
                    break
                content = content[-remaining:]
            selected.append({"role": item.get("role", "user"), "content": content})
            used += len(content)
            if used >= max_chars:
                break
        selected.reverse()
        return selected

    def _query_needs_reference(self, message):
        text = message.lower()
        markers = ("latest", "right now", "current", "currently", "today", "this week",
                   "recent news", "breaking news", "weather", "stock price", "exchange rate",
                   "who won", "newest version", "as of 2026")
        return any(marker in text for marker in markers)

    def _quick_reference_lookup(self, query):
        """Try a no-key DuckDuckGo Instant Answer lookup; results can be incomplete/stale."""
        try:
            response = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query[:240], "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": "TITAN-Neon-Ultra/1.0"},
                timeout=(5, 8),
            )
            if response.status_code >= 400:
                return ""
            data = response.json()
            pieces = []
            abstract = re.sub(r"<[^>]+>", "", str(data.get("AbstractText", ""))).strip()
            abstract_url = str(data.get("AbstractURL", "")).strip()
            if abstract:
                pieces.append(abstract + (f" Source: {abstract_url}" if abstract_url else ""))
            for item in data.get("RelatedTopics", [])[:4]:
                if not isinstance(item, dict):
                    continue
                text = re.sub(r"<[^>]+>", "", str(item.get("Text", ""))).strip()
                url = str(item.get("FirstURL", "")).strip()
                if text:
                    pieces.append(text + (f" Source: {url}" if url else ""))
            return "\n".join(pieces[:5])[:3500]
        except Exception:
            return ""

    def _chat_worker(self, message, key, history):
        try:
            personality = self.settings.get("personality") or "You are a helpful AI assistant."
            memory_items = self.memories[-20:] if self.settings.get("memory_enabled", True) else []
            memory_context = "\nSaved user memories (use only when relevant):\n" + "\n".join(
                "- " + str(item.get("text", ""))[:500] for item in memory_items
            ) if memory_items else ""
            project_context = "\nActive project workspace: " + str(getattr(self, "active_project", "General"))
            reliability_rules = (
                "\n\nReliability rules: Be honest and precise. Never invent facts, sources, quotes, "
                "or capabilities. If unsure, say so and ask a useful clarifying question. Distinguish "
                "verified facts from guesses. Do not claim you searched the live web unless reference "
                "results are supplied. This chat sends text only; do not claim to have seen an image, "
                "heard audio, or watched video unless that media was actually provided to the model. "
                "Use a clear, natural tone and avoid unnecessary long lists or repeated offers."
            )
            reference_context = ""
            if self._query_needs_reference(message):
                lookup = self._quick_reference_lookup(message)
                if lookup:
                    reference_context = (
                        "\n\nOptional quick reference results (DuckDuckGo Instant Answer; may be "
                        "incomplete or stale; verify before relying on them):\n" + lookup
                    )
                else:
                    reference_context = (
                        "\n\nThe user asks for potentially current information, but no reliable "
                        "reference result was available. Be transparent that you cannot verify it live."
                    )
            messages = [{"role": "system", "content": personality + memory_context + project_context +
                         reliability_rules + reference_context}]
            messages.extend(history)  # includes the current user message exactly once
            response = requests.post(
                GROQ_URL,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={"model": self.settings.get("model") or DEFAULT_MODEL, "messages": messages,
                      "temperature": 0.7, "max_tokens": 1600},
                timeout=(15, 90),
            )
            if response.status_code >= 400:
                try:
                    detail = response.json().get("error", {}).get("message", response.text[:300])
                except ValueError:
                    detail = response.text[:300]
                raise RuntimeError(f"Groq HTTP {response.status_code}: {detail}")
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
            Clock.schedule_once(lambda dt: self._finish_chat(answer), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self._finish_chat("Connection error: " + error), 0)

    def _finish_chat(self, answer):
        self.add_chat_bubble("assistant", answer)
        self.add_status("READY")

    def show_chat_history(self, *_):
        """Chat Pro: search saved conversations, reopen, rename, and export them."""
        self.page = "CHAT_HISTORY"
        self.set_page("CHAT PRO", "SEARCH • ORGANIZE • EXPORT")
        self.root_box.add_widget(self.label("Search conversation titles and message text.", 11, MUTED, 28))
        self.history_search = self.input_box("Search chats...", height=42)
        self.root_box.add_widget(self.history_search)
        refresh = NeonButton(text="SEARCH CHATS", accent="purple")
        refresh.bind(on_release=self._render_chat_history)
        self.root_box.add_widget(refresh)
        self.history_list = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None)
        self.history_list.bind(minimum_height=self.history_list.setter("height"))
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        scroll.add_widget(self.history_list)
        self.root_box.add_widget(scroll)
        self._render_chat_history()
        self.add_status()

    def _render_chat_history(self, *_):
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear_widgets()
        query = self.history_search.text.strip().lower() if hasattr(self, "history_search") else ""
        matches = []
        for chat in reversed(self.chats):
            messages = chat.get("messages", [])
            title = chat.get("title") or next((str(m.get("content", ""))[:42] for m in messages if m.get("role") == "user"), "Untitled chat")
            searchable = title + " " + " ".join(str(m.get("content", "")) for m in messages)
            if query and query not in searchable.lower():
                continue
            matches.append((chat, title, messages))
        if not matches:
            self.history_list.add_widget(self.label("No matching saved chats yet.", 12, MUTED, 42))
        for chat, title, messages in matches[:100]:
            card = NeonCard(orientation="vertical", size_hint_y=None, height=dp(112), spacing=dp(3))
            card.add_widget(self.label(title, 12, CYAN, 24, True))
            card.add_widget(self.label(f"{len(messages)} messages  |  {chat.get('date', 'date unknown')}", 9, MUTED, 18))
            actions = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
            open_btn = NeonButton(text="OPEN", accent="cyan")
            open_btn.bind(on_release=lambda _b, item=chat: self.open_saved_chat(item))
            rename_btn = NeonButton(text="RENAME", accent="purple")
            rename_btn.bind(on_release=lambda _b, item=chat: self.rename_saved_chat(item))
            export_btn = NeonButton(text="EXPORT", accent="purple")
            export_btn.bind(on_release=lambda _b, item=chat: self.export_saved_chat(item))
            for b in (open_btn, rename_btn, export_btn):
                b.font_size = "10sp"
                actions.add_widget(b)
            card.add_widget(actions)
            self.history_list.add_widget(card)

    def open_saved_chat(self, chat):
        self._persist_chat()
        self.current_chat_id = chat.get("id") or datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.current_messages = list(chat.get("messages", []))
        self.show_chat()

    def rename_saved_chat(self, chat):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        title = chat.get("title") or next((str(m.get("content", ""))[:42] for m in chat.get("messages", []) if m.get("role") == "user"), "Untitled chat")
        field = self.input_box("Conversation title", title, height=44)
        box.add_widget(field)
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        save = NeonButton(text="SAVE TITLE")
        cancel = NeonButton(text="CANCEL", accent="purple")
        actions.add_widget(save); actions.add_widget(cancel); box.add_widget(actions)
        pop = Popup(title="RENAME CHAT", content=box, size_hint=(0.9, 0.34), title_color=CYAN)
        def commit(*_):
            chat["title"] = field.text.strip()[:80] or "Untitled chat"
            save_json(CHATS_FILE, self.chats)
            pop.dismiss(); self._render_chat_history()
        save.bind(on_release=commit); cancel.bind(on_release=pop.dismiss); pop.open()

    def export_saved_chat(self, chat):
        try:
            title = chat.get("title") or "TITAN chat"
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:45] or "titan_chat"
            path = DATA_DIR / (safe_title.replace(" ", "_") + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")
            lines = [title, "=" * min(60, max(8, len(title))), ""]
            for msg in chat.get("messages", []):
                lines.extend([( "TITAN" if msg.get("role") == "assistant" else "YOU") + ":", str(msg.get("content", "")), ""])
            path.write_text("\n".join(lines), encoding="utf-8")
            self.popup("CHAT EXPORTED", "Saved to app data folder:\n" + str(path))
        except Exception as exc:
            self.popup("EXPORT FAILED", str(exc)[:250])

    def show_health_center(self, *_):
        """Local diagnostics that do not expose API keys."""
        self.page = "HEALTH"
        self.set_page("SYSTEM HEALTH", "LOCAL DIAGNOSTICS • SAFE CHECKS")
        self.health_report = self.label("Preparing diagnostics...", 11, WHITE, 150)
        self.root_box.add_widget(self.health_report)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(7))
        run = NeonButton(text="RUN CHECKS")
        run.bind(on_release=self.run_health_checks)
        test = NeonButton(text="TEST CHAT API", accent="purple")
        test.bind(on_release=self.test_connection)
        row.add_widget(run); row.add_widget(test)
        self.root_box.add_widget(row)
        self.root_box.add_widget(self.label("API keys are never shown here. Video and audio billing depend on provider account/model access.", 10, MUTED, 50))
        self.run_health_checks()
        self.add_status()

    def run_health_checks(self, *_):
        try:
            total = 0
            file_count = 0
            for folder in (DATA_DIR, MEDIA_DIR):
                if folder.exists():
                    for path in folder.rglob("*"):
                        if path.is_file():
                            try: total += path.stat().st_size; file_count += 1
                            except OSError: pass
            groq = "CONFIGURED" if self.settings.get("groq_key", "").strip() else "MISSING"
            poll = "CONFIGURED" if self.settings.get("pollinations_key", "").strip() else "MISSING"
            data_writable = os.access(DATA_DIR, os.W_OK)
            report = [
                "TITAN LOCAL HEALTH REPORT",
                f"Chat API key: {groq}",
                f"Media API key: {poll}",
                f"Data folder writable: {'YES' if data_writable else 'NO'}",
                f"Files in data/gallery: {file_count}",
                f"App data size: {total / (1024 * 1024):.2f} MB",
                f"Chat records: {len(self.chats)}  |  Notes: {len(self.notes)}  |  Memories: {len(self.memories)}",
                f"Projects: {len(getattr(self, 'projects', []))}  |  Saved prompts: {len(getattr(self, 'prompts', []))}",
                f"Chat model: {self.settings.get('model', DEFAULT_MODEL)}",
                f"Video model: {self.settings.get('video_model', 'not set')}",
                "Network/API status: run TEST CHAT API to verify the configured chat endpoint.",
            ]
            if hasattr(self, "health_report"):
                self.health_report.text = "\n".join(report)
                self.health_report.height = dp(max(190, len(report) * 23))
        except Exception as exc:
            if hasattr(self, "health_report"):
                self.health_report.text = "Diagnostics failed: " + str(exc)[:220]

    def show_studio(self, *_):
        self.page = "STUDIO"
        self.set_page("TITAN STUDIO", "GENERATE • CHOOSE • ANALYZE")
        self.root_box.add_widget(self.label("Describe the image you want TITAN to create.", 13, WHITE, 36))
        self.prompt_input = self.input_box("Example: neon cyberpunk city in the rain...", multiline=True, height=100)
        self.root_box.add_widget(self.prompt_input)
        generate = NeonButton(text="GENERATE IMAGE", accent="purple")
        generate.bind(on_release=self.generate_image)
        self.root_box.add_widget(generate)
        choose = NeonButton(text="CHOOSE PHOTO FROM DEVICE")
        choose.bind(on_release=self.choose_photo)
        self.root_box.add_widget(choose)
        self.root_box.add_widget(self.label("Images are saved in titan_neon_data/gallery.", 11, MUTED, 36))
        self.studio_status = self.label("", 11, GREEN, 44)
        self.root_box.add_widget(self.studio_status)
        self.add_status()

    def generate_image(self, *_):
        prompt = self.prompt_input.text.strip()
        key = self.settings.get("pollinations_key", "").strip()
        if not prompt:
            self.studio_status.text = "Enter an image prompt first."
            return
        if not key:
            self.popup("IMAGE KEY NEEDED", "Add your Pollinations API key in SETTINGS.")
            return
        self.studio_status.text = "Generating image… please wait."
        threading.Thread(target=self._image_worker, args=(prompt, key), daemon=True).start()

    def _image_worker(self, prompt, key):
        try:
            url = POLLINATIONS_URL + urllib.parse.quote(prompt, safe="")
            response = requests.get(url, headers={"Authorization": "Bearer " + key},
                                    params={"model": "flux", "width": 768, "height": 768, "nologo": "true"},
                                    timeout=(20, 180))
            if response.status_code >= 400:
                raise RuntimeError(f"Pollinations HTTP {response.status_code}: {response.text[:250]}")
            if "image" not in response.headers.get("Content-Type", "").lower():
                raise RuntimeError("The API did not return an image. Check the key and model access.")
            suffix = ".png" if "png" in response.headers.get("Content-Type", "").lower() else ".jpg"
            filename = MEDIA_DIR / ("titan_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + suffix)
            filename.write_bytes(response.content)
            Clock.schedule_once(lambda dt: self._image_done(str(filename)), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self._image_error(error), 0)

    def _image_done(self, path):
        self.status_text = "IMAGE SAVED"
        if self.page == "STUDIO":
            self.studio_status.text = "Saved: " + Path(path).name
            self.show_studio_result(path)
        self.popup("IMAGE SAVED", path)

    def _image_error(self, error):
        if self.page == "STUDIO" and hasattr(self, "studio_status"):
            self.studio_status.text = error[:180]
        self.status_text = "IMAGE ERROR"
        self.popup("IMAGE ERROR", error[:600])

    def show_studio_result(self, path):
        self.root_box.add_widget(AsyncImage(source=path, size_hint_y=None, height=dp(260)))

    def show_video_lab(self, *_):
        """Text-to-video generation using Pollinations' unified media endpoint."""
        self.page = "VIDEO"
        self.set_page("AI VIDEO LAB", "TEXT → CINEMATIC VIDEO")
        self.root_box.add_widget(self.label("Describe the scene, camera movement, lighting, and mood.", 13, WHITE, 42))
        self.video_prompt = self.input_box(
            "Example: A futuristic city at night, glowing cyan rain, slow cinematic camera push-in...",
            multiline=True, height=110
        )
        self.root_box.add_widget(self.video_prompt)
        self.root_box.add_widget(self.label("VIDEO MODEL", 11, CYAN, 22, True))
        self.video_model_input = self.input_box(
            "google/veo-3.1-fast", self.settings.get("video_model", "google/veo-3.1-fast"), height=46
        )
        self.root_box.add_widget(self.video_model_input)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.root_box.add_widget(self.label("DURATION (SECONDS)", 11, PURPLE, 22, True))
        self.video_duration_input = self.input_box("4", "4", height=46)
        self.root_box.add_widget(self.video_duration_input)
        generate = NeonButton(text="GENERATE AI VIDEO", accent="purple")
        generate.bind(on_release=self.generate_video)
        self.root_box.add_widget(generate)
        self.video_status = self.label("Generated MP4 clips are saved in the TITAN gallery folder.", 11, MUTED, 44)
        self.root_box.add_widget(self.video_status)
        self.add_status()

    def generate_video(self, *_):
        # Avoid duplicate paid requests while one is already in progress.
        if getattr(self, "video_request_running", False):
            if hasattr(self, "video_status"):
                self.video_status.text = "A video request is already running. Please wait."
            return
        prompt = self.video_prompt.text.strip()
        key = self.settings.get("pollinations_key", "").strip()
        if not prompt:
            self.video_status.text = "Write a video prompt first."
            return
        if not key:
            self.popup("API KEY NEEDED", "Add your Pollinations API key in SETTINGS.")
            return
        try:
            duration = int(self.video_duration_input.text.strip() or "4")
            if duration < 3 or duration > 15:
                raise ValueError
        except ValueError:
            self.video_status.text = "Choose a duration from 3 to 15 seconds."
            return
        model = self.video_model_input.text.strip() or "google/veo-3.1-fast"
        self.settings["video_model"] = model
        save_json(SETTINGS_FILE, self.settings)
        self.video_request_running = True
        self.video_status.text = "Rendering video… this can take a few minutes."
        threading.Thread(target=self._video_worker, args=(prompt, key, model, duration), daemon=True).start()

    def _video_worker(self, prompt, key, model, duration):
        try:
            url = POLLINATIONS_VIDEO_URL + urllib.parse.quote(prompt, safe="")
            response = requests.get(
                url,
                headers={"Authorization": "Bearer " + key},
                params={"model": model, "duration": duration},
                timeout=(25, 300),
            )
            if response.status_code >= 400:
                # Convert provider JSON into a short, user-friendly error.
                try:
                    payload = response.json()
                    err = payload.get("error", {})
                    if isinstance(err, dict):
                        detail = err.get("message", "")
                        code = err.get("code", "")
                    else:
                        detail, code = str(err), ""
                except Exception:
                    detail, code = response.text[:160], ""
                if response.status_code == 402 or "INSUFFICIENT_BALANCE" in str(code).upper() or "insufficient balance" in str(detail).lower():
                    raise RuntimeError("BALANCE_REQUIRED")
                if response.status_code in (401, 403):
                    raise RuntimeError("KEY_OR_MODEL_ACCESS")
                if response.status_code == 429:
                    raise RuntimeError("RATE_LIMIT")
                raise RuntimeError(f"HTTP_{response.status_code}")
            content_type = response.headers.get("Content-Type", "").lower()
            filename = MEDIA_DIR / ("titan_video_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".mp4")
            if "video/" in content_type or response.content[:4] == b"\x00\x00\x00\x18" or response.content[:3] == b"ID3":
                filename.write_bytes(response.content)
            else:
                # Some providers return JSON containing a public video URL.
                data = response.json()
                video_url = data.get("url") or (data.get("data") or [{}])[0].get("url")
                if not video_url:
                    raise RuntimeError("The API response did not contain a video file.")
                media = requests.get(video_url, timeout=(20, 180))
                media.raise_for_status()
                if len(media.content) > 20 * 1024 * 1024:
                    raise RuntimeError("Video exceeds the 20 MB download limit.")
                filename.write_bytes(media.content)
            if not filename.exists() or filename.stat().st_size < 1024:
                raise RuntimeError("The returned video file was empty or incomplete.")
            Clock.schedule_once(lambda dt: self._video_done(str(filename)), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self._video_error(error), 0)

    def _video_done(self, path):
        self.video_request_running = False
        self.status_text = "VIDEO SAVED"
        if self.page == "VIDEO" and hasattr(self, "video_status"):
            self.video_status.text = "Saved: " + Path(path).name
            self.show_video_result(path)
        self.popup("VIDEO READY", "Saved to gallery:\n" + Path(path).name)

    def _video_error(self, error):
        self.video_request_running = False
        self.status_text = "VIDEO UNAVAILABLE"
        if error == "BALANCE_REQUIRED":
            message = ("Your Pollinations balance is too low for this video.\n\n"
                       "No video was generated. Check your account balance and pricing, "
                       "or choose another provider. This app cannot bypass billing.")
            status = "Balance required. Check Pollinations credits before retrying."
        elif error == "KEY_OR_MODEL_ACCESS":
            message = "The API key is invalid, or this model is not available to your account. Check Settings and model access."
            status = "Check API key and model access in Settings."
        elif error == "RATE_LIMIT":
            message = "The video service is receiving too many requests. Wait a little before trying again."
            status = "Rate limited. Please wait before retrying."
        else:
            message = "The video service could not complete the request. Check your internet connection and model settings, then try again later."
            status = "Video service unavailable. Check connection and settings."
        if self.page == "VIDEO" and hasattr(self, "video_status"):
            self.video_status.text = status
        self.popup("VIDEO NOT GENERATED", message)

    def show_video_result(self, path):
        try:
            player = Video(source=path, state="stop", options={"eos": "stop"},
                           size_hint_y=None, height=dp(250))
            self.root_box.add_widget(player)
            controls = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            play = NeonButton(text="PLAY VIDEO")
            play.bind(on_release=lambda *_: setattr(player, "state", "play"))
            pause = NeonButton(text="PAUSE VIDEO")
            pause.bind(on_release=lambda *_: setattr(player, "state", "pause"))
            controls.add_widget(play)
            controls.add_widget(pause)
            self.root_box.add_widget(controls)
        except Exception:
            self.root_box.add_widget(self.label("Video saved. Use a device video player if preview is unavailable.", 12, MUTED, 42))

    def show_voice_lab(self, *_):
        self.page = "VOICE"
        self.set_page("VOICE LAB", "GIVE TITAN A VOICE")
        self.root_box.add_widget(self.label("Create spoken audio with a selectable voice, or use Android's built-in speech.", 13, WHITE, 48))
        self.voice_text_input = self.input_box("Type something for TITAN to say...", multiline=True, height=110)
        self.root_box.add_widget(self.voice_text_input)
        self.root_box.add_widget(self.label("AI VOICE", 11, CYAN, 22, True))
        from kivy.uix.spinner import Spinner
        self.voice_spinner = Spinner(
            text=self.settings.get("voice", "nova"),
            values=("alloy", "echo", "fable", "onyx", "nova", "shimmer"),
            size_hint_y=None, height=dp(46),
            background_normal="", background_color=PANEL2, color=WHITE
        )
        self.root_box.add_widget(self.voice_spinner)
        online = NeonButton(text="GENERATE VOICE AUDIO")
        online.bind(on_release=self.generate_speech_audio)
        self.root_box.add_widget(online)
        local = NeonButton(text="SPEAK WITH DEVICE VOICE", accent="purple")
        local.bind(on_release=lambda *_: self.speak_text(self.voice_text_input.text.strip()))
        self.root_box.add_widget(local)
        self.voice_status = self.label("AI voice audio needs a Pollinations key. Device speech uses Android TTS.", 11, MUTED, 44)
        self.root_box.add_widget(self.voice_status)
        self.add_status()

    def speak_text(self, text):
        """Speak text using Plyer when available, with Android native TTS fallback."""
        text = (text or "").strip()
        if not text:
            self.popup("VOICE", "There is no text to speak.")
            return

        # First choice: Plyer, if it is installed and has a working Android bridge.
        try:
            from plyer import tts
            tts.speak(text[:3500])
            self.status_text = "SPEAKING"
            if hasattr(self, "voice_status"):
                self.voice_status.text = "Speaking with device voice."
            return
        except Exception:
            pass

        # Pydroid/Kivy installations may include PyJNIus even when Plyer is absent.
        # Android TextToSpeech is initialized asynchronously, so speak from onInit.
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
            Locale = autoclass("java.util.Locale")
            activity = PythonActivity.mActivity
            app = self
            spoken_text = text[:3500]

            class TTSInitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    try:
                        if status == TextToSpeech.SUCCESS:
                            tts_engine.setLanguage(Locale.getDefault())
                            # QUEUE_FLUSH = 0; null utterance id is accepted by Android.
                            tts_engine.speak(spoken_text, 0, None)
                            Clock.schedule_once(lambda dt: setattr(app, "status_text", "SPEAKING"), 0)
                        else:
                            Clock.schedule_once(lambda dt: app._device_tts_failed("Android speech engine could not initialize."), 0)
                    except Exception as exc:
                        message = str(exc)[:180]
                        Clock.schedule_once(lambda dt, m=message: app._device_tts_failed(m), 0)

            listener = TTSInitListener()
            tts_engine = TextToSpeech(activity, listener)
            # Keep references alive while Android initializes the speech engine.
            self._titan_tts_listener = listener
            self._titan_tts_engine = tts_engine
            if hasattr(self, "voice_status"):
                self.voice_status.text = "Starting Android text-to-speech..."
            return
        except Exception as exc:
            self._device_tts_failed(
                "Device speech is unavailable. In Pydroid, install the Plyer package, "
                "and make sure Android has a Text-to-speech engine enabled. Details: " + str(exc)[:140]
            )

    def _device_tts_failed(self, message):
        if hasattr(self, "voice_status"):
            self.voice_status.text = message
        self.popup("DEVICE VOICE UNAVAILABLE", message)

    def generate_speech_audio(self, *_):
        text = self.voice_text_input.text.strip()
        key = self.settings.get("pollinations_key", "").strip()
        if not text:
            self.voice_status.text = "Enter text first."
            return
        if not key:
            self.popup("API KEY NEEDED", "Add your Pollinations API key in SETTINGS.")
            return
        voice = self.voice_spinner.text
        self.settings["voice"] = voice
        save_json(SETTINGS_FILE, self.settings)
        self.voice_status.text = "Generating speech audio…"
        threading.Thread(target=self._speech_worker, args=(text, key, voice), daemon=True).start()

    def _speech_worker(self, text, key, voice):
        try:
            url = POLLINATIONS_AUDIO_URL + urllib.parse.quote(text, safe="")
            response = requests.get(
                url, headers={"Authorization": "Bearer " + key},
                params={"voice": voice}, timeout=(20, 180)
            )
            if response.status_code >= 400:
                try:
                    payload = response.json()
                    err = payload.get("error", {})
                    detail = err.get("message", "") if isinstance(err, dict) else str(err)
                    code = err.get("code", "") if isinstance(err, dict) else ""
                except Exception:
                    detail, code = response.text[:160], ""
                if response.status_code == 402 or "INSUFFICIENT_BALANCE" in str(code).upper():
                    raise RuntimeError("BALANCE_REQUIRED")
                if response.status_code == 400 and ("text model" in detail.lower() or "audio endpoint" in detail.lower()):
                    raise RuntimeError("AUDIO_MODEL_MISMATCH")
                if response.status_code in (401, 403):
                    raise RuntimeError("KEY_OR_MODEL_ACCESS")
                if response.status_code == 429:
                    raise RuntimeError("RATE_LIMIT")
                raise RuntimeError(f"AUDIO_HTTP_{response.status_code}")
            if "audio" not in response.headers.get("Content-Type", "").lower() and not response.content[:3] == b"ID3":
                raise RuntimeError("The API did not return audio. Check the selected model/voice.")
            filename = MEDIA_DIR / ("titan_voice_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".mp3")
            filename.write_bytes(response.content)
            Clock.schedule_once(lambda dt: self._speech_done(str(filename)), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self._speech_error(error), 0)

    def _speech_done(self, path):
        if self.page == "VOICE" and hasattr(self, "voice_status"):
            self.voice_status.text = "Audio saved: " + Path(path).name
        self.status_text = "VOICE AUDIO SAVED"
        try:
            sound = SoundLoader.load(path)
            if sound:
                sound.play()
                self._active_sound = sound
        except Exception:
            pass
        self.popup("VOICE AUDIO READY", "Saved: " + Path(path).name)

    def _speech_error(self, error):
        if error == "BALANCE_REQUIRED":
            message = "Your Pollinations balance is too low for AI voice generation. Check your account balance and pricing, or use SPEAK WITH DEVICE VOICE instead."
            status = "Balance required for online voice. Device voice is available below."
        elif error == "AUDIO_MODEL_MISMATCH":
            message = "The online audio service rejected the selected model. The app has been updated to use the audio endpoint without forcing a text-only model. If this persists, use device voice or check the provider's current audio models."
            status = "Online audio model unavailable. Try device voice."
        elif error == "KEY_OR_MODEL_ACCESS":
            message = "Your API key may be invalid, or your account may not have access to this audio service. Check the key in Settings."
            status = "Check API key and audio access in Settings."
        elif error == "RATE_LIMIT":
            message = "The audio service is receiving too many requests. Wait a little and try again."
            status = "Audio rate limit. Please wait before retrying."
        else:
            message = "The online voice request failed. Check your connection, API key, and current provider audio support. You can use SPEAK WITH DEVICE VOICE as an alternative."
            status = "Online voice unavailable. Try device voice."
        if self.page == "VOICE" and hasattr(self, "voice_status"):
            self.voice_status.text = status
        self.popup("VOICE NOT GENERATED", message)

    def choose_photo(self, *_):
        if filechooser is None:
            self.popup("PHOTO PICKER", "Plyer is unavailable. Install it or use the Gallery.")
            return
        try:
            filechooser.open_file(on_selection=self._photo_selected,
                                  filters=[("Images", "*.png", "*.jpg", "*.jpeg", "*.webp")])
        except Exception as exc:
            self.popup("PHOTO PICKER ERROR", str(exc))

    def _photo_selected(self, selection):
        if not selection:
            return
        source = selection[0]
        try:
            target = MEDIA_DIR / (datetime.now().strftime("photo_%Y%m%d_%H%M%S_") + Path(source).name)
            shutil.copy2(source, target)
            Clock.schedule_once(lambda dt: self.popup("PHOTO SAVED", target.name), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self.popup("PHOTO ERROR", error), 0)

    def show_gallery(self, *_):
        self.page = "GALLERY"
        self.set_page("IMAGE GALLERY", "YOUR SAVED IMAGES")
        scroll = ScrollView()
        listing = GridLayout(cols=2, spacing=dp(8), padding=dp(4), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        files = sorted([p for p in MEDIA_DIR.iterdir()
                        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            listing.add_widget(self.label("No images yet. Open PHOTO STUDIO to create one.", 13, MUTED, 100))
        for path in files:
            card = NeonCard(orientation="vertical", size_hint_y=None, height=dp(205))
            card.add_widget(AsyncImage(source=str(path), size_hint_y=None, height=dp(145)))
            card.add_widget(self.label(path.name[:23], 9, WHITE, 24))
            delete = NeonButton(text="DELETE", accent="purple")
            delete.height = dp(34)
            delete.bind(on_release=lambda btn, p=path: self.delete_image(p))
            card.add_widget(delete)
            listing.add_widget(card)
        scroll.add_widget(listing)
        self.root_box.add_widget(scroll)
        self.add_status(f"{len(files)} IMAGE(S)")

    def delete_image(self, path):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.popup("DELETE FAILED", str(exc))
            return
        self.show_gallery()

    def show_projects(self, *_):
        """Lightweight project workspace manager; existing data stays untouched."""
        self.page = "PROJECTS"
        self.set_page("PROJECT WORKSPACES", "GROUP YOUR IDEAS BY PROJECT")
        self.root_box.add_widget(self.label("Active workspace: " + self.active_project, 13, CYAN, 32, True))
        name_input = self.input_box("New project name...", height=44)
        self.root_box.add_widget(name_input)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(7))
        create = NeonButton(text="CREATE PROJECT")
        create.bind(on_release=lambda *_: self._create_project(name_input.text))
        row.add_widget(create)
        row.add_widget(NeonButton(text="OPEN CHAT", accent="purple", on_release=self.show_chat))
        self.root_box.add_widget(row)
        listing = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        for project in self.projects:
            name = str(project.get("name", "General"))
            card = NeonCard(orientation="horizontal", size_hint_y=None, height=dp(54))
            card.add_widget(self.label(("ACTIVE  " if name == self.active_project else "") + name, 12, CYAN if name == self.active_project else WHITE, 35, True))
            choose = NeonButton(text="SELECT", accent="purple")
            choose.size_hint_x = None; choose.width = dp(88)
            choose.bind(on_release=lambda _b, n=name: self._select_project(n))
            card.add_widget(choose); listing.add_widget(card)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(listing)
        self.root_box.add_widget(scroll)
        self.root_box.add_widget(self.label("The active project is added to TITAN's chat context. Your existing chats and notes remain intact.", 10, MUTED, 48))
        self.add_status(f"{len(self.projects)} PROJECT(S)")

    def _create_project(self, name):
        name = str(name).strip()[:60]
        if not name:
            self.popup("PROJECT NAME", "Enter a name for your workspace.")
            return
        if any(str(item.get("name", "")).casefold() == name.casefold() for item in self.projects):
            self.popup("ALREADY EXISTS", "A project with that name already exists.")
            return
        self.projects.append({"name": name, "created": datetime.now().isoformat(timespec="minutes")})
        if not save_json(PROJECTS_FILE, self.projects):
            self.projects.pop()
            self.popup("SAVE FAILED", "Could not save this project.")
            return
        self.active_project = name
        self.show_projects()

    def _select_project(self, name):
        self.active_project = name
        self.show_projects()

    def show_prompt_vault(self, *_):
        """Save and reuse prompt snippets locally."""
        self.page = "PROMPTS"
        self.set_page("PROMPT VAULT", "SAVE • REUSE • BUILD FASTER")
        self.prompt_title = self.input_box("Prompt title", height=42)
        self.prompt_body = self.input_box("Write or paste a reusable prompt...", multiline=True, height=105)
        self.root_box.add_widget(self.prompt_title)
        self.root_box.add_widget(self.prompt_body)
        save = NeonButton(text="SAVE PROMPT")
        save.bind(on_release=self._save_prompt)
        self.root_box.add_widget(save)
        listing = BoxLayout(orientation="vertical", spacing=dp(7), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        for item in reversed(self.prompts):
            card = NeonCard(orientation="vertical", size_hint_y=None, height=dp(106))
            card.add_widget(self.label(item.get("title", "Untitled prompt"), 12, CYAN, 22, True))
            preview = str(item.get("text", "")).replace("\n", " ")[:110]
            card.add_widget(self.label(preview, 10, MUTED, 36))
            actions = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
            use = NeonButton(text="USE IN CHAT")
            use.bind(on_release=lambda _b, value=item.get("text", ""): self._use_prompt(value))
            delete = NeonButton(text="DELETE", accent="purple")
            delete.bind(on_release=lambda _b, value=item: self._delete_prompt(value))
            actions.add_widget(use); actions.add_widget(delete); card.add_widget(actions)
            listing.add_widget(card)
        scroll = ScrollView(do_scroll_x=False); scroll.add_widget(listing)
        self.root_box.add_widget(scroll)
        self.add_status(f"{len(self.prompts)} SAVED PROMPT(S)")

    def _save_prompt(self, *_):
        title = self.prompt_title.text.strip()[:70] or "Untitled prompt"
        value = self.prompt_body.text.strip()
        if not value:
            self.popup("EMPTY PROMPT", "Write a prompt before saving.")
            return
        item = {"title": title, "text": value, "date": datetime.now().isoformat(timespec="minutes")}
        self.prompts.append(item)
        if not save_json(PROMPTS_FILE, self.prompts):
            self.prompts.pop()
            self.popup("SAVE FAILED", "Could not save the prompt.")
            return
        self.show_prompt_vault()

    def _use_prompt(self, value):
        self.show_chat()
        self.chat_input.text = value

    def _delete_prompt(self, item):
        if item in self.prompts:
            self.prompts.remove(item)
            if not save_json(PROMPTS_FILE, self.prompts):
                self.popup("SAVE FAILED", "Could not save prompt changes.")
                return
        self.show_prompt_vault()

    def show_backup_center(self, *_):
        self.page = "BACKUP"
        self.set_page("BACKUP & SECURITY", "LOCAL DATA • KEY-SAFE EXPORT")
        self.root_box.add_widget(self.label("Create a ZIP backup of chats, notes, memories, prompts, projects and gallery media.", 12, WHITE, 66))
        self.root_box.add_widget(self.label("API keys are excluded from backups by default. Keep your original settings.json private.", 10, MUTED, 55))
        export = NeonButton(text="CREATE SAFE BACKUP ZIP")
        export.bind(on_release=self.create_safe_backup)
        self.root_box.add_widget(export)
        self.root_box.add_widget(self.label("Backup files are saved inside the app's titan_neon_data folder. Copy the ZIP somewhere safe using your file manager.", 10, MUTED, 60))
        self.add_status()

    def create_safe_backup(self, *_):
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = DATA_DIR / ("titan_backup_" + stamp + ".zip")
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in (NOTES_FILE, MEMORY_FILE, CHATS_FILE, PROJECTS_FILE, PROMPTS_FILE):
                    if path.is_file():
                        archive.write(path, arcname=path.name)
                if MEDIA_DIR.exists():
                    for path in MEDIA_DIR.rglob("*"):
                        if path.is_file():
                            archive.write(path, arcname=str(Path("gallery") / path.relative_to(MEDIA_DIR)))
                safe_settings = dict(self.settings)
                safe_settings["groq_key"] = ""
                safe_settings["pollinations_key"] = ""
                archive.writestr("settings.template.json", json.dumps(safe_settings, ensure_ascii=False, indent=2))
            self.popup("BACKUP CREATED", "Safe backup saved at:\n" + str(destination) + "\n\nAPI keys were excluded.")
        except Exception as exc:
            self.popup("BACKUP FAILED", str(exc)[:300])

    def show_notes(self, *_):
        self.page = "NOTES"
        self.set_page("TITAN NOTES", "SAVE YOUR IDEAS")
        self.note_input = self.input_box("Write a note...", multiline=True, height=100)
        self.root_box.add_widget(self.note_input)
        save = NeonButton(text="SAVE NOTE")
        save.bind(on_release=self.save_note)
        self.root_box.add_widget(save)
        scroll = ScrollView()
        listing = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        for note in reversed(self.notes):
            card = NeonCard(orientation="vertical", size_hint_y=None, height=dp(100))
            card.add_widget(self.label(note.get("text", ""), 13, WHITE, 54))
            card.add_widget(self.label(note.get("date", ""), 9, MUTED, 18))
            listing.add_widget(card)
        scroll.add_widget(listing)
        self.root_box.add_widget(scroll)
        self.add_status(f"{len(self.notes)} NOTE(S)")

    def save_note(self, *_):
        text = self.note_input.text.strip()
        if not text:
            return
        self.notes.append({"text": text, "date": datetime.now().isoformat(timespec="minutes")})
        if not save_json(NOTES_FILE, self.notes):
            self.popup("SAVE ERROR", "Could not save the note.")
            return
        self.show_notes()

    def show_memory(self, *_):
        self.page = "MEMORY"
        self.set_page("TITAN MEMORY", "INFORMATION YOU CHOOSE TO SAVE")
        self.memory_input = self.input_box("What should TITAN remember?", multiline=True, height=90)
        self.root_box.add_widget(self.memory_input)
        save = NeonButton(text="SAVE MEMORY", accent="purple")
        save.bind(on_release=self.save_memory)
        self.root_box.add_widget(save)
        scroll = ScrollView()
        listing = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        listing.bind(minimum_height=listing.setter("height"))
        for mem in reversed(self.memories):
            card = NeonCard(orientation="vertical", size_hint_y=None, height=dp(78))
            card.add_widget(self.label(mem.get("text", ""), 13, WHITE, 42))
            card.add_widget(self.label(mem.get("date", ""), 9, MUTED, 16))
            listing.add_widget(card)
        scroll.add_widget(listing)
        self.root_box.add_widget(scroll)
        clear = NeonButton(text="CLEAR ALL MEMORY", accent="purple")
        clear.bind(on_release=lambda *_: self.confirm_clear_memory())
        self.root_box.add_widget(clear)
        self.add_status(f"{len(self.memories)} MEMORY ITEM(S)")

    def save_memory(self, *_):
        text = self.memory_input.text.strip()
        if not text:
            return
        self.memories.append({"text": text, "date": datetime.now().isoformat(timespec="minutes")})
        if not save_json(MEMORY_FILE, self.memories):
            self.popup("SAVE ERROR", "Could not save memory.")
            return
        self.show_memory()

    def confirm_clear_memory(self):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        box.add_widget(Label(text="Delete every saved memory?", color=WHITE))
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        pop = Popup(title="CONFIRM CLEAR", content=box, size_hint=(0.85, 0.3),
                    auto_dismiss=False, title_color=CYAN)
        cancel, confirm = NeonButton(text="CANCEL"), NeonButton(text="DELETE", accent="purple")
        cancel.bind(on_release=pop.dismiss)
        def clear(_):
            self.memories = []
            save_json(MEMORY_FILE, self.memories)
            pop.dismiss()
            self.show_memory()
        confirm.bind(on_release=clear)
        row.add_widget(cancel)
        row.add_widget(confirm)
        box.add_widget(row)
        pop.open()

    def show_calculator(self, *_):
        self.page = "CALCULATOR"
        self.set_page("CALCULATOR", "SAFE BASIC MATH")
        self.calc_input = self.input_box("Example: (25 + 5) * 2", height=58)
        self.root_box.add_widget(self.calc_input)
        calc = NeonButton(text="CALCULATE")
        calc.bind(on_release=self.calculate)
        self.root_box.add_widget(calc)
        self.calc_result = self.label("Result appears here.", 18, CYAN, 60, True, "center")
        self.root_box.add_widget(self.calc_result)
        self.root_box.add_widget(self.label("Supports +  -  *  /  //  %  ** and parentheses.", 11, MUTED, 40))
        self.add_status()

    def calculate(self, *_):
        try:
            self.calc_result.text = str(safe_math(self.calc_input.text.strip()))
        except Exception as exc:
            self.calc_result.text = "Error: " + str(exc)

    def show_settings(self, *_):
        self.page = "SETTINGS"
        self.set_page("TITAN SETTINGS", "PERSONALIZE YOUR AI")
        scroll = ScrollView()
        content = BoxLayout(orientation="vertical", spacing=dp(9), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(self.label("GROQ API KEY (CHAT)", 12, CYAN, 24, True))
        self.groq_input = self.input_box("Paste Groq key here", self.settings.get("groq_key", ""), height=52, password=True)
        content.add_widget(self.groq_input)
        content.add_widget(self.label("POLLINATIONS API KEY (IMAGES)", 12, PURPLE, 24, True))
        self.pollinations_input = self.input_box("Paste Pollinations key here", self.settings.get("pollinations_key", ""), height=52, password=True)
        content.add_widget(self.pollinations_input)
        content.add_widget(self.label("CHAT MODEL NAME", 12, CYAN, 24, True))
        self.model_input = self.input_box("openai/gpt-oss-120b", self.settings.get("model", DEFAULT_MODEL), height=48)
        content.add_widget(self.model_input)
        content.add_widget(self.label("VIDEO MODEL", 12, PURPLE, 24, True))
        self.video_model_setting = self.input_box("google/veo-3.1-fast", self.settings.get("video_model", "google/veo-3.1-fast"), height=48)
        content.add_widget(self.video_model_setting)
        content.add_widget(self.label("DEFAULT AI VOICE", 12, CYAN, 24, True))
        from kivy.uix.spinner import Spinner
        self.voice_setting = Spinner(text=self.settings.get("voice", "nova"),
                                     values=("alloy", "echo", "fable", "onyx", "nova", "shimmer"),
                                     size_hint_y=None, height=dp(46),
                                     background_normal="", background_color=PANEL2, color=WHITE)
        content.add_widget(self.voice_setting)
        content.add_widget(self.label("TITAN PERSONALITY", 12, PURPLE, 24, True))
        self.personality_input = self.input_box("Describe how TITAN should talk...",
                                                self.settings.get("personality", ""), multiline=True, height=120)
        content.add_widget(self.personality_input)
        content.add_widget(self.label("APP THEME", 12, CYAN, 24, True))
        from kivy.uix.spinner import Spinner
        self.theme_setting = Spinner(text=self.settings.get("theme", "Dark"),
                                     values=("Light", "Dark"),
                                     size_hint_y=None, height=dp(46),
                                     background_normal="", background_color=PANEL2, color=WHITE)
        content.add_widget(self.theme_setting)
        from kivy.uix.checkbox import CheckBox
        memory_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.memory_enabled_checkbox = CheckBox(active=self.settings.get("memory_enabled", True),
                                                size_hint_x=None, width=dp(44), color=CYAN)
        memory_row.add_widget(self.memory_enabled_checkbox)
        memory_row.add_widget(self.label("USE SAVED MEMORY IN AI CHAT", 11, WHITE, 30, True))
        content.add_widget(memory_row)
        content.add_widget(self.label("Type 'remember that ...' in chat to save a memory. Manage or clear memories in the MEMORY screen.", 10, MUTED, 42))
        content.add_widget(self.label("API keys are stored locally in settings.json. Do not share that file.", 10, MUTED, 48))
        save = NeonButton(text="SAVE SETTINGS")
        save.bind(on_release=self.save_settings)
        content.add_widget(save)
        test = NeonButton(text="TEST CHAT CONNECTION")
        test.bind(on_release=self.test_connection)
        content.add_widget(test)
        scroll.add_widget(content)
        self.root_box.add_widget(scroll)
        self.add_status()

    def save_settings(self, *_):
        self.settings.update({
            "groq_key": self.groq_input.text.strip(),
            "pollinations_key": self.pollinations_input.text.strip(),
            "model": self.model_input.text.strip() or DEFAULT_MODEL,
            "video_model": self.video_model_setting.text.strip() or "google/veo-3.1-fast",
            "voice": self.voice_setting.text or "nova",
            "personality": self.personality_input.text.strip() or "You are TITAN, a helpful AI assistant.",
            "memory_enabled": bool(getattr(self, "memory_enabled_checkbox", None) and self.memory_enabled_checkbox.active),
            "theme": getattr(self, "theme_setting", None).text if getattr(self, "theme_setting", None) else self.settings.get("theme", "Dark"),
        })
        if save_json(SETTINGS_FILE, self.settings):
            apply_theme(self.settings.get("theme", "Dark"))
            Window.clearcolor = BG
            # Refresh the active page so every widget adopts the selected palette.
            self.root_box.canvas.before.clear()
            with self.root_box.canvas.before:
                Color(*BG)
                self._root_bg = RoundedRectangle(pos=self.root_box.pos, size=self.root_box.size)
            self.status_text = "SETTINGS SAVED"
            self.show_settings()
            self.popup("THEME UPDATED", f"Settings saved. {self.settings.get('theme', 'Dark')} mode is active.")
        else:
            self.popup("SAVE ERROR", "Could not save settings. Check storage permissions.")

    def test_connection(self, *_):
        key = (self.groq_input.text.strip() if hasattr(self, "groq_input") and self.page == "SETTINGS"
               else self.settings.get("groq_key", "").strip())
        if not key:
            self.popup("MISSING KEY", "Add your Groq API key in SETTINGS first.")
            return
        model = (self.model_input.text.strip() if hasattr(self, "model_input") and self.page == "SETTINGS"
                 else self.settings.get("model", DEFAULT_MODEL)) or DEFAULT_MODEL
        self.popup("TESTING", "Testing Groq connection…")
        threading.Thread(target=self._test_worker, args=(key, model), daemon=True).start()

    def _test_worker(self, key, model):
        try:
            response = requests.post(
                GROQ_URL,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "Reply exactly: TITAN ONLINE"}],
                      "max_tokens": 20},
                timeout=(15, 35),
            )
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:250]}")
            answer = response.json()["choices"][0]["message"]["content"]
            Clock.schedule_once(lambda dt: self.popup("CONNECTION SUCCESS", answer), 0)
        except Exception as exc:
            error = str(exc)
            Clock.schedule_once(lambda dt: self.popup("CONNECTION FAILED", error[:500]), 0)


if __name__ == "__main__":
    TitanApp().run()