[app]
title = TITAN NEON ULTRA
package.name = titanneonultra
package.domain = org.titanneon
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,svg
version = 1.0.0
requirements = python3,kivy,requests,plyer
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/titan_icon.png
android.permissions = INTERNET,RECORD_AUDIO,READ_MEDIA_IMAGES
android.api = 35
android.minapi = 24
android.archs = arm64-v8a
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
