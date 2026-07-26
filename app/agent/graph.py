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
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agent.state import TravelAgentState

# Core Nodes & Edges
from app.agent.nodes import (
    intent_node,
    route_by_intent,
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


def create_travel_agent() -> CompiledStateGraph:
    """
    Tạo và compile LangGraph workflow Multi-Agent cho Travel AI Agent.

    Returns:
        Compiled graph sẵn sàng để invoke
    """
    graph = StateGraph(TravelAgentState)

    # ── Đăng ký nodes ─────────────────────────────────────────────
    graph.add_node("classify",        intent_node)
    graph.add_node("planner",         planner_node)
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
    graph.add_edge("planner", "agent")

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
    return graph.compile()


# Singleton instance (lazy initialization)
_agent_graph = None


def get_agent() -> CompiledStateGraph:
    """
    Lấy agent graph instance (singleton pattern).

    Returns:
        Compiled LangGraph agent
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_travel_agent()
    return _agent_graph
