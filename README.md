# TITAN NEON ULTRA

A clean Android/Kivy project using the Obsidian Gold visual identity.

## Features in the source

- AI chat using a user-supplied Groq-compatible API key
- Image, video, and voice generation endpoints with user-supplied provider credentials
- Local chat history, notes, memories, prompt vault, and project workspaces
- Image gallery and calculator
- System health, backup, and settings screens
- Black-and-gold UI and a custom vector logo

Provider features require valid API credentials and service access. API keys are entered by the user in the app; do not commit keys to the repository.

## Build with GitHub Actions

1. Open the Actions tab.
2. Select TITAN NEON ULTRA Android APK.
3. Open the run started by the clean-project branch push.
4. When it finishes successfully, open the run and download the TITAN-NEON-ULTRA-debug-apk artifact.
5. Extract the artifact ZIP to get the APK.

The workflow runs a Python syntax check and branding check before invoking Buildozer. A successful source commit is not the same as a successful APK build; use the Actions run status and artifact list to verify the result.

## Local build

Install Buildozer, Java 17, Android SDK/NDK dependencies, and librsvg2-bin, then run:

    rsvg-convert -w 1024 -h 1024 titan_logo.svg -o titan_logo.png
    rsvg-convert -w 512 -h 512 titan_logo.svg -o titan_icon.png
    buildozer android debug
