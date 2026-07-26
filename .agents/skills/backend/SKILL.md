---
name: backend
description: Work on this Travel AI Agent repo's FastAPI + LangGraph backend. Use when changing src/travel_ai_agent graphs, agents, nodes, state, tools, api routers/services/schemas, HITL resume flow, planner/supervisor/reflection behavior, LLM service setup, or agent state contracts.
---

# Travel LangGraph Backend

## Overview

Use this skill to modify the backend without breaking the current LangGraph multi-agent flow. Keep changes compatible with FastAPI streaming, session IDs, LangGraph checkpointer state, and HITL plan confirmation.

## Workflow

1. Read `references/backend-map.md` first for repo-specific entrypoints and invariants.
2. Trace the request path before editing: frontend API -> `src/travel_ai_agent/api/routers/chat.py` -> `src/travel_ai_agent/api/services/chat_service.py` -> `src/travel_ai_agent/graphs/main_graph.py`.
3. Treat `AgentState.messages` as append-only LangGraph message state. Do not replace it with plain strings.
4. Preserve `thread_id=session_id` behavior in graph config; HITL resume depends on it.
5. Keep planner output structured. If adding trip fields, update schema/state, plan builder, response agent, and frontend payload together.
6. Add deterministic routing before adding LLM decisions when rules are clear.
7. Avoid calling expensive tools for chitchat, out-of-scope, or invalid follow-up requests.

## Backend Rules

- Keep graph node return values partial-state dicts.
- Add new state fields to `src/travel_ai_agent/state/agent_state.py` before using them in nodes.
- Keep external API wrappers inside `src/travel_ai_agent/tools`; keep orchestration in agents/services.
- Surface user-facing failures as assistant messages or structured API errors, not raw tracebacks.
- Preserve SSE event types used by the frontend unless also updating `frontend/src/services/api.js`.

## Validation

Run focused backend checks when possible:

```powershell
python -m compileall src main.py
```
