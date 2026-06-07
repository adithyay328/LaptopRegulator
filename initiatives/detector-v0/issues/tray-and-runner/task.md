---
id: 019ea405-d16a-7b54-9460-f80df43cf398
status: pending
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-06-07T21:38:25.000Z
parent: 019ea3fe-c1ee-7805-9aed-ffa2b2ef1bf2
---

# Tray Icon + Main Runner

Implement the system tray indicator and the main orchestration loop.

## Scope

1. **Tray icon** — cross/plus shape rendered as SVG, displayed via AyatanaAppIndicator3.
   Green = not distracting, red = distracting. Include SVG icon files.
2. **Main loop** — periodically (every ~30s):
   - Capture screenshot
   - Record ~5s of audio
   - Send both to the AI analyzer
   - Update tray icon based on result
3. **Entry point** — `python -m detector_v0` or `python src/detector_v0/main.py`.
4. **Graceful shutdown** on SIGINT/SIGTERM.

## Acceptance Criteria

- [ ] Tray icon shows green cross by default.
- [ ] Tray icon turns red when AI flags content as distracting.
- [ ] Main loop runs continuously with configurable interval.
- [ ] Clean shutdown on Ctrl+C.
