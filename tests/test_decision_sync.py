"""Ensure the panel persists the exact priced report used by the cost agent."""
from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.api import routes
from app.models.trip_plan import DateRange, TripPlan
from app.providers.normalizers import FlightOption, HotelOption
from app.services.calculator import get_decision_engine


class _Store:
    def __init__(self):
        self.plan = None
        self.decision = None

    def save_trip_plan(self, _session_id, plan):
        self.plan = plan

    def save_decision(self, _session_id, decision):
        self.decision = decision

    def save_itinerary(self, _session_id, _itinerary):
        pass


class DecisionSyncTests(unittest.TestCase):
    def test_persisted_panel_report_uses_agent_priced_options(self):
        engine = get_decision_engine()
        plan = TripPlan(destination="Da Nang", dates=DateRange(days=3), travelers=2)
        live_report = engine.evaluate(
            destination=plan.destination,
            days=3,
            travelers=2,
            flight_options=[FlightOption(id="f1", airline="A", price=900000)],
            hotel_options=[HotelOption(id="h1", name="H", price_per_night=400000)],
        )
        default_report = engine.evaluate(destination=plan.destination, days=3, travelers=2)
        store = _Store()

        with (
            patch.object(routes, "get_session_store", return_value=store),
            patch.object(routes, "get_decision_engine", return_value=SimpleNamespace(evaluate=lambda **_: default_report)),
        ):
            routes._update_decision_report(
                "session-1", plan, {"decision_report": asdict(live_report)}
            )

        self.assertEqual(
            store.decision.cost_estimate.total_all_people,
            live_report.cost_estimate.total_all_people,
        )
        self.assertNotEqual(
            store.decision.cost_estimate.total_all_people,
            default_report.cost_estimate.total_all_people,
        )

