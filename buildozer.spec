[app]

title = Taitan Prum
package.name = dsaai
package.domain = org.dsaai
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
version = 2.0.0
requirements = python3,kivy,requests,charset-normalizer==3.4.3
orientation = portrait
fullscreen = 0

# The app needs internet access to call the Groq API.
android.permissions = INTERNET
android.api = 35
android.minapi = 24

# Pin python-for-android to a stable release using Python 3.11 recipes.
# This avoids a newer Python 3.14 Android wheel compatibility failure.
p4a.branch = v2024.01.21

# Use the modern Android SDK installed by GitHub Actions.
android.sdk_path = /usr/local/lib/android/sdk
