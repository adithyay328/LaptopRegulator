---
id: 019ea405-d168-7336-bfab-7a98c4a577b1
status: pending
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-06-07T21:38:25.000Z
parent: 019ea3fe-c1ee-7805-9aed-ffa2b2ef1bf2
---

# Capture Pipeline (Screen + Audio)

Implement the data capture layer for the distraction detector.

## Scope

1. **Screen capture** — Use `grim` (wlroots Wayland screenshot tool) via subprocess
   to capture full-screen PNG screenshots. Must work on Wayland without virtual planes.
2. **Audio capture** — Use `pw-record` (PipeWire) via subprocess to record short audio
   clips to WAV files. Same approach as the dictate system.
3. Both modules should provide simple async-friendly functions:
   - `capture_screenshot() -> bytes` — returns PNG bytes
   - `record_audio(duration_secs: float) -> bytes` — returns WAV bytes

## Acceptance Criteria

- [ ] `screen_capture.py` captures a PNG screenshot via `grim`.
- [ ] `audio_capture.py` records N seconds of audio via `pw-record`.
- [ ] Both return raw bytes suitable for sending to Gemini.
- [ ] Temp files are cleaned up after use.
