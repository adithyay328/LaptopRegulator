---
id: 019e93f8-f9b6-7c81-886b-6e68a73cc118
status: pending
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-06-04T18:50:28.893Z
---

# Enforce Concise, Structured Agent Responses

## Problem

Right now, the agent tends to ramble in its responses to the user. Long, unstructured paragraphs make it harder to scan answers and increase cognitive load.

## Goal

Update the agent’s system prompt (or other canonical instructions) so that, by default, it responds in **bullet points** or a **very concise structured format** — unless the user explicitly asks for a longer explanation. The aim is to eliminate rambling and keep outputs tight and scannable.

## Acceptance Criteria

- [ ] Identify where the agent’s general response-style instructions live (e.g., system prompt, `AGENTS.md`, or a dedicated style doc).
- [ ] Add a clear instruction: *“When responding to the user, use bullet points or a very concise structured format. Avoid rambling.”* (or equivalent).
- [ ] Ensure the instruction is loaded into the agent’s context (system prompt, skill, or other) so it is respected in all turns.
- [ ] Verify that the linter passes and the cache is rebuilt after any file changes.
