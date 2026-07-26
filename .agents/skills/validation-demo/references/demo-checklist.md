# Demo Checklist

Use this reference when preparing the project for review.

## Employer-Visible Strengths

- Multi-agent LangGraph architecture.
- HITL plan confirmation and resume.
- Streaming FastAPI + React UI.
- Tool integration for flights, hotels, weather, and travel info.
- Clear guardrails and cost-control story.
- Persistent memory/trip state when implemented.
- Tests and reproducible Docker setup.

## Demo Story

1. User asks for a trip plan.
2. Agent creates a structured plan and asks for confirmation.
3. User confirms.
4. Agents fetch flight/hotel/weather/info.
5. App renders results and final recommendation.
6. User asks unrelated question.
7. Guardrail refuses without calling tools.

## Smoke Checks

- Backend Python compile passes.
- Frontend lint/build passes.
- Docker docs are current.
- `.env.example` exists before public sharing.
- README includes setup, architecture, sample prompt, and limitations.
