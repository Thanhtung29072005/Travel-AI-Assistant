"""
LangGraph Graph - Định nghĩa luồng xử lý của Travel AI Agent (Multi-Agent Architecture)

Luồng hoạt động Multi-Agent Choreography:
  START
   │
   ▼
  classify (intent)
   │
   ├── "planner" ────► planner ──► agent (trả lời kế hoạch nháp)
   │
   ├── "agent" ──────► agent (các câu hỏi thường/chitchat)
   │
   └── "supervisor" ──► supervisor (Kế hoạch đã duyệt)
                         │
                         ├──► weather_agent ──┐
                         ├──► cost_agent    ──┼──► supervisor (quay vòng lặp)
                         ├──► itinerary_agent ┘
                         │
                         └──► agent (Consolidator - tổng hợp phản hồi cuối) ──► END
"""
import asyncio
import sqlite3
import threading
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings
from app.agent.state import TravelAgentState

# Core Nodes & Edges
from app.agent.nodes import (
    intent_node,
    route_by_intent,
    route_after_planner,
    human_confirm_node,
    tool_node,
    track_tools_node,
    should_continue,
)

# Specialized Agents & Supervisor Nodes
from app.agent.planner_agent import planner_node
from app.agent.response_agent import agent_node
from app.agent.supervisor import supervisor_node, route_supervisor
from app.agent.weather_agent import weather_agent_node
from app.agent.cost_agent import cost_agent_node
from app.agent.itinerary_agent import itinerary_agent_node


# Runtime requests use a SQLite-backed saver. Tests can still provide their
# own in-memory saver when creating a graph directly.
_checkpointer: SqliteSaver | None = None
_agent_graph: CompiledStateGraph | None = None
_agent_lock = threading.Lock()
_graph_execution_lock = threading.RLock()


def create_travel_agent(checkpointer=None) -> CompiledStateGraph:
    """
    Tạo và compile LangGraph workflow Multi-Agent cho Travel AI Agent.

    Returns:
        Compiled graph sẵn sàng để invoke
    """
    graph = StateGraph(TravelAgentState)

    # ── Đăng ký nodes ─────────────────────────────────────────────
    graph.add_node("classify",        intent_node)
    graph.add_node("planner",         planner_node)
    graph.add_node("human_confirm",   human_confirm_node)
    graph.add_node("agent",           agent_node)
    graph.add_node("tools",           tool_node)
    graph.add_node("track_tools",     track_tools_node)
    
    # Specialized Sub-Agents & Supervisor
    graph.add_node("supervisor",      supervisor_node)
    graph.add_node("weather_agent",   weather_agent_node)
    graph.add_node("cost_agent",      cost_agent_node)
    graph.add_node("itinerary_agent", itinerary_agent_node)

    # ── Edges ──────────────────────────────────────────────────────

    # START → classify (bắt đầu luôn từ phân loại intent)
    graph.add_edge(START, "classify")

    # classify → (conditional) → planner, agent HOẶC supervisor
    graph.add_conditional_edges(
        source="classify",
        path=route_by_intent,
        path_map={
            "planner": "planner",
            "agent": "agent",
            "supervisor": "supervisor",
        },
    )

    # planner → agent (sau khi có TripPlan nháp, Response Agent trả lời ngay)
    graph.add_conditional_edges(
        source="planner",
        path=route_after_planner,
        path_map={"human_confirm": "human_confirm", "agent": "agent"},
    )
    graph.add_edge("human_confirm", "supervisor")

    # supervisor → (conditional) → điều phối các sub-agents chuyên trách
    graph.add_conditional_edges(
        source="supervisor",
        path=route_supervisor,
        path_map={
            "weather_agent": "weather_agent",
            "cost_agent": "cost_agent",
            "itinerary_agent": "itinerary_agent",
            "agent": "agent",
        },
    )

    # Các Agent con sau khi chạy xong ➔ quay lại supervisor để định tuyến tiếp
    graph.add_edge("weather_agent",   "supervisor")
    graph.add_edge("cost_agent",      "supervisor")
    graph.add_edge("itinerary_agent", "supervisor")

    # agent → (conditional) → tools HOẶC END (vòng lặp ReAct truyền thống cho agent chính)
    graph.add_conditional_edges(
        source="agent",
        path=should_continue,
        path_map={
            "tools": "tools",
            "end":   END,
        },
    )

    # tools → track_tools → agent
    graph.add_edge("tools",       "track_tools")
    graph.add_edge("track_tools", "agent")

    # ── Compile ───────────────────────────────────────────────────
    return graph.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["human_confirm"],
    )


# Singleton instance (lazy initialization)
_agent_graph = None


def _legacy_get_agent() -> CompiledStateGraph:
    """
    Lấy agent graph instance (singleton pattern).

    Returns:
        Compiled LangGraph agent
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_travel_agent()
    return _agent_graph


def get_agent() -> CompiledStateGraph:
    """Return the application graph with a durable SQLite checkpointer."""
    global _agent_graph, _checkpointer, _agent_lock
    if _agent_graph is not None:
        return _agent_graph

    with _agent_lock:
        if _agent_graph is not None:
            return _agent_graph

        db_path = Path(get_settings().checkpoint_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path, check_same_thread=False)
        _checkpointer = SqliteSaver(connection)
        _checkpointer.setup()
        _agent_graph = create_travel_agent(checkpointer=_checkpointer)
        return _agent_graph


async def run_graph_call(method, *args, **kwargs):
    """Run synchronous SQLite-backed graph calls off the FastAPI event loop."""
    def call():
        with _graph_execution_lock:
            return method(*args, **kwargs)

    return await asyncio.to_thread(call)


async def stream_graph_events(agent, *args, **kwargs):
    """Bridge LangGraph 0.2 stream updates to the SSE event contract."""
    event_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    completed = object()

    def produce() -> None:
        try:
            with _graph_execution_lock:
                # LangGraph 0.2 exposes synchronous ``stream`` but not
                # ``stream_events``. Convert node updates to the small event
                # shape consumed by the existing SSE route.
                kwargs.pop("version", None)
                for update in agent.stream(*args, stream_mode="updates", **kwargs):
                    for node_name, output in update.items():
                        metadata = {"langgraph_node": node_name}
                        loop.call_soon_threadsafe(
                            event_queue.put_nowait,
                            {"event": "on_chain_start", "name": node_name, "metadata": metadata},
                        )
                        loop.call_soon_threadsafe(
                            event_queue.put_nowait,
                            {
                                "event": "on_chain_end",
                                "name": node_name,
                                "metadata": metadata,
                                "data": {"output": output},
                            },
                        )
        except BaseException as error:
            loop.call_soon_threadsafe(event_queue.put_nowait, error)
        finally:
            loop.call_soon_threadsafe(event_queue.put_nowait, completed)

    producer = asyncio.create_task(asyncio.to_thread(produce))
    while True:
        item = await event_queue.get()
        if item is completed:
            break
        if isinstance(item, BaseException):
            await producer
            raise item
        yield item
    await producer


def close_agent() -> None:
    """Close the database connection without deleting durable checkpoints."""
    global _agent_graph, _checkpointer, _agent_lock
    if _checkpointer is not None:
        _checkpointer.conn.close()
    _agent_graph = None
    _checkpointer = None
