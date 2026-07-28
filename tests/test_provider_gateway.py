"""Provider gateway tests with mocked SerpApi responses (no network or API key)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.providers import gateway


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class ProviderGatewayTests(unittest.TestCase):
    def test_missing_key_returns_labelled_fixture_results(self):
        with patch.object(gateway, "get_settings", return_value=SimpleNamespace(serpapi_api_key="")):
            result = gateway.fetch_flights("Hanoi", "Da Nang", "2026-08-10")

        self.assertTrue(result.items)
        self.assertEqual(result.metadata.data_mode, "fixture")
        self.assertIn("not configured", result.metadata.fallback_reason)
        self.assertTrue(all(item.data_mode == "fixture" for item in result.items))

    def test_live_flight_response_is_normalized_and_marked_live(self):
        payload = {
            "search_parameters": {"currency": "VND"},
            "best_flights": [{
                "price": 1234000,
                "total_duration": 80,
                "flights": [{
                    "airline": "Example Air",
                    "duration": 80,
                    "departure_airport": {"time": "2026-08-10 08:00"},
                    "arrival_airport": {"time": "2026-08-10 09:20"},
                }],
            }],
        }
        with (
            patch.object(gateway, "get_settings", return_value=SimpleNamespace(serpapi_api_key="live-key")),
            patch.object(gateway.httpx, "get", return_value=_Response(payload)) as request,
        ):
            result = gateway.fetch_flights("Hanoi", "Da Nang", "2026-08-10")

        self.assertEqual(result.metadata.provider, "SerpApi / Google Flights")
        self.assertEqual(result.metadata.data_mode, "live")
        self.assertEqual(result.items[0].airline, "Example Air")
        self.assertEqual(result.items[0].data_mode, "live")
        self.assertEqual(request.call_args.kwargs["params"]["engine"], "google_flights")

    def test_live_provider_error_falls_back_to_fixture(self):
        with (
            patch.object(gateway, "get_settings", return_value=SimpleNamespace(serpapi_api_key="live-key")),
            patch.object(gateway.httpx, "get", side_effect=gateway.httpx.TimeoutException("timeout")),
        ):
            result = gateway.fetch_hotels("Da Nang", check_in_date="2026-08-10")

        self.assertEqual(result.metadata.data_mode, "fixture")
        self.assertIn("unavailable", result.metadata.fallback_reason)
        self.assertTrue(all(item.data_mode == "fixture" for item in result.items))

