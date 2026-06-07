---
id: 019ea405-d169-72a5-a1fc-be54df6f7282
status: pending
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-06-07T21:38:25.000Z
parent: 019ea3fe-c1ee-7805-9aed-ffa2b2ef1bf2
---

# AI Analysis Module (Pydantic AI + Gemini)

Implement the AI analysis layer that determines whether captured content is distracting.

## Scope

1. **Pydantic AI agent** using `google-gla:gemini-3.1-flash-lite`.
2. **Multimodal input** — send screenshot (PNG) and audio (WAV) to Gemini.
3. **Tool definition** — define a `flag_distracting` tool the agent can call with
   a reason string. If the tool is called, the content is distracting.
4. **Structured result** — return whether content is distracting + the reason.
5. **Secrets** — load Gemini API key from `~/.agents/secrets/google_ai_studio`.

## Acceptance Criteria

- [ ] Pydantic AI agent configured with Gemini 3.1 Flash-Lite.
- [ ] Agent accepts screenshot bytes and audio bytes as input.
- [ ] `flag_distracting` tool defined and callable by the agent.
- [ ] Returns a clear distracting/not-distracting result with reason.
