"""Deterministic tests for the LangGraph plan-confirmation checkpoint."""
from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_core.messages import AIMessage, HumanMessage

from app.agent import graph as graph_module
from app.models.trip_plan import DateRange, TripPlan, TripStatus


def _plan(_: dict) -> dict:
    return {
        "trip_plan": TripPlan(destination="Da Nang", dates=DateRange(days=3)),
        "intent": "plan_trip",
    }


def _intent(_: dict) -> dict:
    return {"intent": "plan_trip"}


def _weather(state: dict) -> dict:
    return {"travel_context": {**state.get("travel_context", {}), "weather": "clear"}}


def _cost(state: dict) -> dict:
    return {"travel_context": {**state.get("travel_context", {}), "cost_feasibility": "ok"}}


def _itinerary(state: dict) -> dict:
    return {"travel_context": {**state.get("travel_context", {}), "itinerary": "day 1"}}


def _respond(_: dict) -> dict:
    return {"messages": [AIMessage(content="Trip execution completed.")]}


class HumanConfirmationGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_sse_bridge_uses_langgraph_02_stream_updates(self):
        with patch.multiple(
            graph_module,
            intent_node=_intent,
            planner_node=_plan,
            weather_agent_node=_weather,
            cost_agent_node=_cost,
            itinerary_agent_node=_itinerary,
            agent_node=_respond,
        ):
            agent = graph_module.create_travel_agent()
            config = {"configurable": {"thread_id": "sse-bridge-test"}}
            initial = {
                "messages": [HumanMessage(content="plan")],
                "trip_plan": None,
                "intent": None,
                "tools_used": [],
                "travel_context": {},
                "error": None,
            }

            events = [
                event
                async for event in graph_module.stream_graph_events(
                    agent, initial, config=config, version="v2"
                )
            ]

            self.assertTrue(any(event["event"] == "on_chain_start" for event in events))
            self.assertTrue(
                any(
                    event.get("metadata", {}).get("langgraph_node") == "planner"
                    for event in events
                )
            )

    async def test_complete_plan_pauses_then_resumes_same_thread(self):
        with patch.multiple(
            graph_module,
            intent_node=_intent,
            planner_node=_plan,
            weather_agent_node=_weather,
            cost_agent_node=_cost,
            itinerary_agent_node=_itinerary,
            agent_node=_respond,
        ):
            agent = graph_module.create_travel_agent()
            config = {"configurable": {"thread_id": "hitl-test"}}
            initial = {
                "messages": [HumanMessage(content="Lập kế hoạch Đà Nẵng 3 ngày")],
                "trip_plan": None,
                "intent": None,
                "tools_used": [],
                "travel_context": {},
                "error": None,
            }

            await agent.ainvoke(initial, config=config)
            paused = await agent.aget_state(config)
            self.assertEqual(paused.next, ("human_confirm",))
            self.assertEqual(paused.values["trip_plan"].status, TripStatus.DRAFT)

            approved = paused.values["trip_plan"].model_copy(
                update={"status": TripStatus.CONFIRMED}
            )
            await agent.aupdate_state(config, {"trip_plan": approved})
            result = await agent.ainvoke(None, config=config)

            self.assertEqual((await agent.aget_state(config)).next, ())
            self.assertEqual(result["messages"][-1].content, "Trip execution completed.")

    async def test_paused_plan_survives_a_new_sqlite_saver(self):
        with TemporaryDirectory() as directory, patch.multiple(
            graph_module,
            intent_node=_intent,
            planner_node=_plan,
            weather_agent_node=_weather,
            cost_agent_node=_cost,
            itinerary_agent_node=_itinerary,
            agent_node=_respond,
        ):
            database = Path(directory) / "checkpoints.sqlite"
            config = {"configurable": {"thread_id": "durable-hitl-test"}}
            initial = {
                "messages": [HumanMessage(content="plan")],
                "trip_plan": None,
                "intent": None,
                "tools_used": [],
                "travel_context": {},
                "error": None,
            }

            first_connection = sqlite3.connect(database, check_same_thread=False)
            first_saver = SqliteSaver(first_connection)
            first_saver.setup()
            first_agent = graph_module.create_travel_agent(checkpointer=first_saver)
            first_agent.invoke(initial, config=config)
            first_connection.close()

            second_connection = sqlite3.connect(database, check_same_thread=False)
            second_saver = SqliteSaver(second_connection)
            second_saver.setup()
            second_agent = graph_module.create_travel_agent(checkpointer=second_saver)
            paused = second_agent.get_state(config)
            self.assertEqual(paused.next, ("human_confirm",))

            approved = paused.values["trip_plan"].model_copy(
                update={"status": TripStatus.CONFIRMED}
            )
            second_agent.update_state(config, {"trip_plan": approved})
            result = second_agent.invoke(None, config=config)
            second_connection.close()

            self.assertEqual(result["messages"][-1].content, "Trip execution completed.")
