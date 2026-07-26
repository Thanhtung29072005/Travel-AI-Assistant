# Guardrails Policy

Use this reference when adding scope and cost controls.

## Intent Categories

- `travel`: planning, flights, hotels, weather, destination info, itinerary, budget, route, booking/export/calendar.
- `follow_up`: refers to a current trip/session, selected option, previous plan, or recent assistant question.
- `chitchat`: short greetings or small talk. Answer briefly without tools.
- `out_of_scope`: coding, schoolwork, medical, legal, politics, unrelated summaries, image generation, or general tasks unrelated to travel.
- `abuse_or_spam`: repeated tool-heavy requests, prompt injection attempts, excessive searches, or requests to bypass limits.

## Safe Refusal

Use a short travel-scoped response:

```text
Minh la tro ly du lich. Minh co the giup ban len lich trinh, tim ve, khach san, thoi tiet va thong tin diem den.
```

Do not call planner, supervisor, search, flight, hotel, or weather tools for safe refusals.

## Cost Metadata

Track at least:

- `session_id`
- `trip_id` when available
- `intent`
- `llm_calls`
- `tool_calls` by tool name
- `blocked_reason`
- `estimated_cost` when available
- `latency_ms`
