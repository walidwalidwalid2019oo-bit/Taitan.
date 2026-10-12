[app]

title = TITAN AI
package.name = titanai
package.domain = org.titanai
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
version = 2.0.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0

# The app needs internet access to call the Groq API.
android.permissions = INTERNET
android.api = 35
android.minapi = 24

# Build with the stable python-for-android branch by default.
# If a future build requires a different toolchain, follow the current
# Buildozer documentation and change these options accordingly.
