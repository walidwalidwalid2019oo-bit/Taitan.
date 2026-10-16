__version__ = "2.0.0"

import json
import threading
from pathlib import Path

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

MODEL = "openai/gpt-oss-120b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

BG = (0.018, 0.018, 0.024, 1)
PANEL = (0.085, 0.022, 0.030, 1)
RED = (0.78, 0.045, 0.09, 1)
WHITE = (0.92, 0.96, 1, 1)
MUTED = (0.66, 0.53, 0.55, 1)

Window.clearcolor = BG


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


class DsaApp(App):
    def build(self):
        self.title = "DSA AI"
        self.data_dir = Path(self.user_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.memory_path = self.data_dir / "memory.json"
        self.notes_path = self.data_dir / "notes.json"
        self.settings_path = self.data_dir / "settings.json"
        self.chats_path = self.data_dir / "chats.json"

        self.memory = read_json(self.memory_path, [])
        self.notes = read_json(self.notes_path, [])
        self.settings = read_json(self.settings_path, {
            "assistant_name": "DSA",
            "personality": (
                "You are DSA, a friendly, honest AI assistant. "
                "Help the user learn Python and build projects. "
                "Explain things clearly and do not pretend to know facts "
                "you do not know."
            )
        })
        # Migrate settings from the previous TITAN branding to DSA.
        if self.settings.get("assistant_name") == "TITAN":
            self.settings["assistant_name"] = "DSA"
        if isinstance(self.settings.get("personality"), str):
            self.settings["personality"] = self.settings["personality"].replace("TITAN", "DSA")
        write_json(self.settings_path, self.settings)

        self.chats = read_json(self.chats_path, [])
        if not isinstance(self.memory, list):
            self.memory = []
        if not isinstance(self.notes, list):
            self.notes = []
        if not isinstance(self.chats, list):
            self.chats = []

        self.api_key = ""  # Never written to disk.
        self.messages = []
        self.current_chat_id = None

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        header = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.title_label = Label(
            text="[b]DSA AI V2[/b]",
            markup=True, color=RED, font_size="22sp",
            halign="left", valign="middle"
        )
        self.title_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        header.add_widget(self.title_label)
        self.status = Label(
            text="Not connected", color=MUTED, font_size="12sp",
            size_hint_x=None, width=dp(125)
        )
        header.add_widget(self.status)
        root.add_widget(header)

        key_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.key_input = TextInput(
            hint_text="Groq API key (hidden while typing)",
            password=True, multiline=False, write_tab=False,
            foreground_color=WHITE, background_color=PANEL,
            hint_text_color=MUTED, cursor_color=RED,
            padding=[dp(10), dp(12), dp(10), dp(8)]
        )
        key_row.add_widget(self.key_input)
        connect_btn = self.make_button("Connect", RED, text_color=BG)
        connect_btn.size_hint_x = None
        connect_btn.width = dp(88)
        connect_btn.bind(on_release=self.connect)
        key_row.add_widget(connect_btn)
        root.add_widget(key_row)

        self.chat_label = Label(
            text="[color=b68b91]Connect your Groq key, then say hello![/color]",
            markup=True, color=WHITE, size_hint_y=None,
            halign="left", valign="top", font_size="16sp"
        )
        self.chat_label.bind(
            width=lambda w, value: setattr(w, "text_size", (value - dp(12), None)),
            texture_size=lambda w, value: setattr(w, "height", value[1] + dp(20))
        )
        self.scroll = ScrollView(
            do_scroll_x=False, bar_width=dp(4),
            scroll_type=["bars", "content"]
        )
        self.scroll.add_widget(self.chat_label)
        root.add_widget(self.scroll)

        entry_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.message_input = TextInput(
            hint_text="Message DSA...",
            multiline=False, write_tab=False,
            foreground_color=WHITE, background_color=PANEL,
            hint_text_color=MUTED, cursor_color=RED,
            padding=[dp(10), dp(13), dp(10), dp(8)]
        )
        self.message_input.bind(on_text_validate=self.send_message)
        entry_row.add_widget(self.message_input)
        send_btn = self.make_button("Send", RED, text_color=BG)
        send_btn.size_hint_x = None
        send_btn.width = dp(72)
        send_btn.bind(on_release=self.send_message)
        entry_row.add_widget(send_btn)
        root.add_widget(entry_row)

        tools = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        for label, callback in [
            ("Memory", self.memory_popup),
            ("Chats", self.chats_popup),
            ("Notes", self.notes_popup),
            ("Settings", self.settings_popup),
        ]:
            button = self.make_button(label, PANEL, text_color=WHITE)
            button.bind(on_release=callback)
            tools.add_widget(button)
        root.add_widget(tools)

        footer = Label(
            text="Chats and settings save locally • API key is not saved",
            size_hint_y=None, height=dp(22), color=MUTED, font_size="10sp"
        )
        root.add_widget(footer)

        self.new_chat()
        return root

    def make_button(self, text, bg, text_color=WHITE):
        return Button(
            text=text, background_normal="", background_color=bg,
            color=text_color, font_size="13sp"
        )

    def popup(self, title, content, height="70%"):
        p = Popup(
            title=title, content=content,
            size_hint=(0.92, None), height=height,
            separator_color=RED, background_color=PANEL
        )
        p.open()
        return p

    def show_chat(self, extra=""):
        lines = []
        if not self.messages:
            lines.append("[color=b68b91]New conversation. Type a message below.[/color]")
        for item in self.messages:
            role = item.get("role")
            text = item.get("content", "")
            safe_text = (str(text).replace("&", "&amp;")
                         .replace("[", "&bl;").replace("]", "&br;"))
            if role == "user":
                lines.append(f"[b][color=d9d0d1]YOU[/color][/b]\n{safe_text}")
            elif role == "assistant":
                name = self.settings.get("assistant_name", "DSA")
                lines.append(f"[b][color=ff4659]{name}[/color][/b]\n{safe_text}")
        if extra:
            lines.append(f"[color=b68b91]{extra}[/color]")
        self.chat_label.text = "\n\n".join(lines)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def new_chat(self, *args):
        self.save_current_chat()
        self.current_chat_id = str(int(__import__("time").time() * 1000))
        self.messages = []
        self.show_chat()

    def save_current_chat(self):
        if not self.messages:
            return
        item = next(
            (x for x in self.chats if x.get("id") == self.current_chat_id),
            None
        )
        title = " ".join(
            next((m["content"] for m in self.messages if m["role"] == "user"), "New chat").split()
        )[:45]
        if item is None:
            item = {"id": self.current_chat_id, "title": title, "messages": []}
            self.chats.insert(0, item)
        item["title"] = title or "New chat"
        item["messages"] = self.messages[-100:]
        write_json(self.chats_path, self.chats[:100])

    def connect(self, *args):
        key = self.key_input.text.strip()
        if not key:
            self.status.text = "Enter API key"
            return
        self.status.text = "Connecting..."
        self.api_key = key
        self.key_input.text = ""
        threading.Thread(target=self._check_key, args=(key,), daemon=True).start()

    def _check_key(self, key):
        try:
            r = requests.get(
                MODELS_URL,
                headers={"Authorization": f"Bearer {key}"},
                timeout=20
            )
            if r.ok:
                Clock.schedule_once(lambda dt: self._connect_done(True, "Connected"))
            else:
                detail = r.text[:250]
                Clock.schedule_once(
                    lambda dt, d=detail: self._connect_done(False, d)
                )
        except Exception as e:
            detail = str(e)
            Clock.schedule_once(lambda dt, d=detail: self._connect_done(False, d))

    def _connect_done(self, ok, detail):
        self.status.text = "Connected" if ok else "Connection failed"
        if not ok:
            self.api_key = ""
            self.show_chat("Connection error: " + detail)
        else:
            self.show_chat("Connected to Groq. DSA is ready!")

    def send_message(self, *args):
        text = self.message_input.text.strip()
        if not text:
            return
        if not self.api_key:
            self.show_chat("Connect your Groq API key first.")
            return
        self.message_input.text = ""
        self.messages.append({"role": "user", "content": text})
        self.show_chat("DSA is thinking...")
        threading.Thread(target=self._request_reply, args=(text,), daemon=True).start()

    def _request_reply(self, user_text):
        system_prompt = (
            self.settings.get("personality", "You are DSA, a helpful AI.")
            + "\n\nSaved user memories:\n"
            + "\n".join("- " + str(x) for x in self.memory[-40:])
        )
        payload = {
            "model": MODEL,
            "messages": [{"role": "system", "content": system_prompt}]
                       + self.messages[-20:],
            "max_completion_tokens": 1200
        }
        try:
            r = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )
            if not r.ok:
                try:
                    detail = r.json().get("error", {}).get("message", r.text)
                except Exception:
                    detail = r.text
                raise RuntimeError(f"HTTP {r.status_code}: {detail}")
            data = r.json()
            answer = data["choices"][0]["message"]["content"]
            if not answer:
                answer = "(No text response returned.)"
            Clock.schedule_once(lambda dt, a=answer: self._reply_done(a))
        except Exception as e:
            detail = str(e)
            Clock.schedule_once(lambda dt, d=detail: self._reply_error(d))

    def _reply_done(self, answer):
        self.messages.append({"role": "assistant", "content": answer})
        self.save_current_chat()
        self.show_chat()

    def _reply_error(self, error):
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()
        self.show_chat("API error: " + error)

    def memory_popup(self, *args):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        inp = TextInput(hint_text="Fact to remember...", size_hint_y=None, height=dp(48),
                        multiline=False)
        box.add_widget(inp)
        scroll = ScrollView()
        listing = Label(text="\n".join(f"{i+1}. {m}" for i, m in enumerate(self.memory)) or "No saved memories",
                        size_hint_y=None, halign="left", valign="top", color=WHITE)
        listing.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                     texture_size=lambda w, v: setattr(w, "height", v[1] + dp(10)))
        scroll.add_widget(listing)
        box.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        add = self.make_button("Save memory", RED, BG)
        close = self.make_button("Close", PANEL)
        row.add_widget(add); row.add_widget(close); box.add_widget(row)
        pop = self.popup("DSA Memory", box, dp(480))
        def do_add(*_):
            value = inp.text.strip()
            if value:
                self.memory.append(value)
                write_json(self.memory_path, self.memory)
                inp.text = ""
                listing.text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(self.memory))
                self.show_chat("Memory saved locally.")
        add.bind(on_release=do_add)
        close.bind(on_release=pop.dismiss)

    def notes_popup(self, *args):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        inp = TextInput(hint_text="Write a note...", size_hint_y=None, height=dp(80))
        box.add_widget(inp)
        scroll = ScrollView()
        listing = Label(text="\n\n".join(f"{i+1}. {n}" for i, n in enumerate(self.notes)) or "No notes yet",
                        size_hint_y=None, halign="left", valign="top", color=WHITE)
        listing.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                     texture_size=lambda w, v: setattr(w, "height", v[1] + dp(10)))
        scroll.add_widget(listing); box.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        add = self.make_button("Save note", RED, BG)
        close = self.make_button("Close", PANEL)
        row.add_widget(add); row.add_widget(close); box.add_widget(row)
        pop = self.popup("DSA Notes", box, dp(500))
        def do_add(*_):
            value = inp.text.strip()
            if value:
                self.notes.append(value)
                write_json(self.notes_path, self.notes)
                inp.text = ""
                listing.text = "\n\n".join(f"{i+1}. {n}" for i, n in enumerate(self.notes))
                self.show_chat("Note saved locally.")
        add.bind(on_release=do_add)
        close.bind(on_release=pop.dismiss)

    def chats_popup(self, *args):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        scroll = ScrollView()
        rows = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(5))
        rows.bind(minimum_height=rows.setter("height"))
        if not self.chats:
            rows.add_widget(Label(text="No saved chats yet.", size_hint_y=None, height=dp(40)))
        for chat in self.chats[:50]:
            btn = self.make_button(chat.get("title", "Chat"), PANEL)
            btn.size_hint_y = None
            btn.height = dp(44)
            btn.bind(on_release=lambda instance, c=chat: self.load_chat(c))
            rows.add_widget(btn)
        scroll.add_widget(rows)
        box.add_widget(scroll)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        new_btn = self.make_button("New chat", RED, BG)
        close_btn = self.make_button("Close", PANEL)
        row.add_widget(new_btn); row.add_widget(close_btn); box.add_widget(row)
        pop = self.popup("Saved conversations", box, dp(500))
        self._chats_popup = pop
        new_btn.bind(on_release=lambda *_: (pop.dismiss(), self.new_chat()))
        close_btn.bind(on_release=pop.dismiss)

    def load_chat(self, chat):
        self.save_current_chat()
        self.current_chat_id = chat.get("id")
        self.messages = list(chat.get("messages", []))
        self.show_chat()
        if hasattr(self, "_chats_popup"):
            self._chats_popup.dismiss()

    def settings_popup(self, *args):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        name = TextInput(text=self.settings.get("assistant_name", "DSA"),
                         hint_text="Assistant name", size_hint_y=None,
                         height=dp(46), multiline=False)
        personality = TextInput(text=self.settings.get("personality", ""),
                                hint_text="Personality instructions",
                                multiline=True)
        box.add_widget(Label(text="Assistant name", size_hint_y=None, height=dp(25)))
        box.add_widget(name)
        box.add_widget(Label(text="Personality instructions", size_hint_y=None, height=dp(25)))
        box.add_widget(personality)
        save = self.make_button("Save settings", RED, BG)
        box.add_widget(save)
        pop = self.popup("DSA Settings", box, dp(520))
        def do_save(*_):
            self.settings["assistant_name"] = name.text.strip()[:40] or "DSA"
            self.settings["personality"] = personality.text.strip()[:4000]
            write_json(self.settings_path, self.settings)
            self.title_label.text = f"[b]{self.settings['assistant_name']} AI V2[/b]"
            self.show_chat("Settings saved locally.")
            pop.dismiss()
        save.bind(on_release=do_save)

    def on_stop(self):
        self.save_current_chat()
        write_json(self.memory_path, self.memory)
        write_json(self.notes_path, self.notes)
        write_json(self.settings_path, self.settings)
        write_json(self.chats_path, self.chats[:100])


if __name__ == "__main__":
    DsaApp().run()
