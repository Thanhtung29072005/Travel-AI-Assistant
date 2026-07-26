# Backend Map

Use this reference when changing backend behavior.

## Request Flow

- `src/travel_ai_agent/api/main.py`: FastAPI app factory, CORS, router registration.
- `src/travel_ai_agent/api/routers/chat.py`: sync/SSE chat endpoints and resume endpoints.
- `src/travel_ai_agent/api/services/chat_service.py`: graph invocation, interrupt detection, final message extraction.
- `src/travel_ai_agent/api/services/session_store.py`: in-memory UI message history only.
- `src/travel_ai_agent/graphs/main_graph.py`: LangGraph topology, MemorySaver, HITL `interrupt_before=["human_confirm"]`.

## Agent Flow

- `classify_intent` routes to `planner`, `follow_up`, or `chitchat`.
- `planner` creates `TripPlan` and asks for missing required travel info.
- `human_confirm` is the HITL gate.
- `supervisor` dispatches `flight_agent`, `hotel_agent`, `weather_agent`, `info_agent`, then `reflect` and `respond`.
- Tool wrappers live in `src/travel_ai_agent/tools`.

## Invariants

- Graph config must use `{"configurable": {"thread_id": sid}}`.
- `messages` uses LangGraph `add_messages`; append message objects, do not overwrite with strings.
- Agent nodes return partial state dicts.
- Completed agent names must match graph node names.
- SSE currently emits `session`, `chunk`, `interrupt`, `done`, `error`.
