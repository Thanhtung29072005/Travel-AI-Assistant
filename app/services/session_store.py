"""
Session Store - Quản lý lưu trữ trạng thái phiên chat (TripPlan & Decision Report)
Lưu trữ trong bộ nhớ (In-memory) đơn giản, sẵn sàng cho việc mở rộng sang Redis/DB sau này.
"""
from __future__ import annotations

from typing import Dict, Optional, Any
from app.models.trip_plan import TripPlan
from app.services.calculator import DecisionReport


class SessionState:
    """Trạng thái đầy đủ của một phiên chat"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.trip_plan: Optional[TripPlan] = None
        self.decision: Optional[DecisionReport] = None
        self.conversation_history: list = []


class SessionStore:
    """In-memory Session Store (Singleton)"""
    def __init__(self):
        self._states: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._states:
            self._states[session_id] = SessionState(session_id)
        return self._states[session_id]

    def save_trip_plan(self, session_id: str, plan: TripPlan) -> None:
        state = self.get_or_create(session_id)
        state.trip_plan = plan

    def save_decision(self, session_id: str, decision: DecisionReport) -> None:
        state = self.get_or_create(session_id)
        state.decision = decision

    def clear(self, session_id: str) -> None:
        if session_id in self._states:
            del self._states[session_id]


# Singleton instance
_session_store = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
