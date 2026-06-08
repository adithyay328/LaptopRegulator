# Detector V0

Prototype distraction detector for Linux desktops. Periodically captures screen
and audio, sends them to Gemini 3.1 Flash-Lite via Pydantic AI for analysis, and
shows a system tray indicator (cross shape: green = OK, red = distracting).

## Tech Stack

- **Python 3.12+**
- **PipeWire** (`pw-record`) for audio capture
- **grim** for Wayland screenshots (wlroots compositors)
- **Pydantic AI** with `google-gla:gemini-3.1-flash-lite` for multimodal analysis
- **PyGObject + AyatanaAppIndicator3** for the system tray icon
- **Secrets**: `~/.agents/secrets/google_ai_studio` (Gemini API key)

## Structure

```
initiatives/detector-v0/
  AGENTS.md              # This file
  detector.py            # Standalone script — all code in one file
  icons/
    green.svg            # Tray icon: productive
    red.svg              # Tray icon: distracting
  issues/                # Sub-issues for this initiative
```

## Conventions

- All code in `detector.py`.
- Entry point: `python detector.py`.
- No package install needed — just `pip install 'pydantic-ai[google]'` for the dependency.
- Audio: same approach as `../dictate` — subprocess `pw-record` to temp WAV.
- Screenshots: subprocess `grim` writing to temp PNG.
- Analysis loop: capture screenshot + N seconds of audio, send to Gemini, update tray.
- Secrets loaded from `~/.agents/secrets/google_ai_studio`.
- The AI agent has a `flag_distracting` tool it can call to indicate distraction.

## Parent Issue

This initiative implements the top-level distraction-detector issue:
`019ea3fe-c1ee-7805-9aed-ffa2b2ef1bf2`
