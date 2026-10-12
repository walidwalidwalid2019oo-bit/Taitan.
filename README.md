# TITAN AI Android project

This starter project turns TITAN into a Kivy Android app. It includes:
- Groq chat using the OpenAI-compatible HTTPS endpoint
- Local persistent memory, notes, personality settings, and chat history
- API key entered at runtime and not written to app files
- A GitHub Actions workflow to build a debug APK in the cloud

## Files
- `main.py` — Kivy app
- `buildozer.spec` — Android package settings
- `.github/workflows/build-apk.yml` — cloud APK build

## Build on a phone using GitHub Actions
1. Create a **private** GitHub repository.
2. Upload these files while preserving the `.github/workflows/` folder.
3. Open the repository's Actions tab and enable Actions if prompted.
4. Run **Build TITAN Android APK** using **Run workflow**, or push a change.
5. Open the completed workflow run, find Artifacts, and download `titan-ai-debug-apk`.
6. Extract the ZIP on your phone and install the APK. Android may ask you to allow installs from that browser/file manager.

## Important security notes
- Never put a Groq API key in `main.py`, `buildozer.spec`, GitHub, or screenshots.
- The app asks for the key each time it starts and keeps it in memory only.
- This is appropriate for personal testing, not for distributing to other users. A key used in a mobile app can still be exposed while in use. For a public app, put the Groq key on a backend server you control and have the app call that backend.
- Groq API use requires internet and is subject to account limits/pricing.
- This is a debug APK for testing, not a signed Play Store release.

## Troubleshooting
- If build fails, open the workflow run and copy the first meaningful error section (not secrets).
- Android builds can take several minutes and the first build downloads the Android toolchain.
- If the model is unavailable to your Groq account, update `MODEL` near the top of `main.py` to a currently available model from Groq's official model list.
