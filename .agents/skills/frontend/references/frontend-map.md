# Frontend Map

Use this reference when changing frontend behavior.

## Current Structure

- `frontend/src/pages/ChatPage.jsx`: main stateful chat page, session loading, SSE callbacks, interrupt handling.
- `frontend/src/services/api.js`: streaming fetch client for chat and resume.
- `frontend/src/components/ChatBubble.jsx`: assistant/user messages and interrupt bubble.
- `frontend/src/components/ChatInput.jsx`: message composer.
- `frontend/src/components/Sidebar.jsx`: sessions list.
- `frontend/src/index.css`: app styling.

## Extension Points

- Add option cards as separate components, not inside `ChatBubble`.
- Add itinerary timeline as a reusable component that receives structured trip data.
- Add action dispatcher in `ChatPage.jsx` or a dedicated hook when backend supports `trip actions`.
- Keep `session_id` propagation intact for chat continuity.
