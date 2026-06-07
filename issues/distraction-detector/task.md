---
id: 019ea3fe-c1ee-7805-9aed-ffa2b2ef1bf2
status: in_progress
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-06-07T10:00:00.000Z
---

# Distraction Detector System

Create a system that monitors screen and audio to detect distracting content.

### Objectives
- Discover all physical devices (bypassing Wayland virtual planes).
- Integrate audio recording using the existing `../dictate` system.
- Use Gemini 3.1 Flash-Lite via Pydantic AI to analyze captured data for distracting content.
- Implement a tray icon indicator (cross shape, green for OK, red for distracting).
- Use Google AI Studio and the secrets management system.
- Define a "flag distracting" tool call for the AI.
- Provide a standalone Python script to run the system and tray indicator.
