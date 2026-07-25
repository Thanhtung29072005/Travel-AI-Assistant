"""
LangGraph Graph - Định nghĩa luồng xử lý của Travel AI Agent

Phase 2 Pipeline:
  START
   │
   ▼
  intent_node          ← Heuristic classifier (không gọi LLM)
   │
   ├── "plan_trip" ──► planner_node   ← LLM nhẹ: extract TripPlan
   │                        │
   │                        ▼
   │                   agent_node     ← LLM đầy đủ với TripPlan context
   │
   └── "general"  ────► agent_node
         │
  agent_node
   │
   ├── "tools" ──► tool_node ──► track_tools ──► agent_node (vòng lặp)
   └── "end"   ──► END
"""
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agent.state import TravelAgentState
from app.agent.nodes import (
    intent_node,
    route_by_intent,
    planner_node,
    agent_node,
    tool_node,
    track_tools_node,
    should_continue,
)



def create_travel_agent() -> CompiledStateGraph:
    """
    Tạo và compile LangGraph workflow Phase 2 cho Travel AI Agent.

    Returns:
        Compiled graph sẵn sàng để invoke
    """
    graph = StateGraph(TravelAgentState)

    # ── Đăng ký nodes ─────────────────────────────────────────────
    graph.add_node("classify",    intent_node)       # Phase 2: nhận diện intent
    graph.add_node("planner",     planner_node)      # Phase 2: tạo/cập nhật TripPlan
    graph.add_node("agent",       agent_node)        # Node AI chính (ReAct)
    graph.add_node("tools",       tool_node)         # Node thực thi tools
    graph.add_node("track_tools", track_tools_node)  # Node ghi log tools

    # ── Edges ──────────────────────────────────────────────────────

    # START → classify (bắt đầu luôn từ phân loại intent)
    graph.add_edge(START, "classify")

    # classify → (conditional) → planner HOẶC agent
    graph.add_conditional_edges(
        source="classify",
        path=route_by_intent,
        path_map={
            "planner": "planner",   # plan_trip → qua planner trước
            "agent":   "agent",     # general/ask_* → thẳng vào agent
        },
    )

    # planner → agent (sau khi có TripPlan, AI mới trả lời)
    graph.add_edge("planner", "agent")

    # agent → (conditional) → tools HOẶC END
    graph.add_conditional_edges(
        source="agent",
        path=should_continue,
        path_map={
            "tools": "tools",   # Gọi tool nếu cần
            "end":   END,       # Kết thúc nếu đã có câu trả lời
        },
    )

    # tools → track_tools → agent (vòng lặp ReAct)
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
