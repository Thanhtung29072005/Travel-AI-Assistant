---
name: frontend
description: Build and refine this Travel AI Agent repo's React/Vite frontend. Use when changing frontend/src pages, components, API streaming client, chat UI, HITL confirmation, flight/hotel cards, itinerary timeline, budget panel, or interactive trip workspace behavior.
---

# Travel Frontend Workspace

## Overview

Use this skill to turn the existing chat UI into an interactive travel planning workspace while preserving streaming chat and HITL behavior.

## Workflow

1. Read `references/frontend-map.md` before editing.
2. Preserve current SSE handling in `frontend/src/services/api.js` unless backend event types change too.
3. Keep chat input disabled during streaming or interrupt confirmation.
4. Render structured trip payloads as UI components instead of converting everything to long text.
5. Keep interaction payloads explicit: action type, trip id/session id, selected option id, and payload.
6. Prefer small domain components over growing `ChatPage.jsx`.

## UI Rules

- Keep chat available as the command surface, but make trip state visible through cards/timeline.
- Add states for loading, empty, selected, disabled, and error.
- Use stable dimensions for option cards and timeline items to avoid layout shift.
- Keep buttons action-oriented: select, replace, optimize, export, confirm.
- Avoid marketing-style landing pages; the first screen should remain the usable app.

## Validation

Run:

```powershell
Set-Location frontend
npm run lint
npm run build
```
