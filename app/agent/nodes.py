from __future__ import annotations

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.agent.state import TravelAgentState
from app.agent.tools import ALL_TOOLS
from app.agent.intent import classify_intent, needs_trip_plan


def intent_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node nhận diện ý định (Phase 2).
    Dùng heuristic keyword matching — KHONG gọi LLM.
    Nhanh (~0ms), không tốn quota.
    """
    messages = state["messages"]

    # Lấy tin nhắn user gần nhất
    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)),
        None,
    )

    if last_human is None:
        intent = "general"
    else:
        intent = classify_intent(str(last_human.content))

    return {
        "messages": [],          # Không thêm message mới
        "intent": intent,
        "trip_plan": state.get("trip_plan"),
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


def route_by_intent(state: TravelAgentState) -> str:
    """
    Conditional edge sau intent_node.
    """
    # Nếu kế hoạch đã được xác nhận (confirmed) hoặc tin nhắn chứa trigger từ form,
    # bỏ qua planner_node để hướng tới supervisor_node điều phối các Agent con.
    trip_plan = state.get("trip_plan")
    if trip_plan and trip_plan.status == "confirmed":
        return "supervisor"

    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "content") and "Kế hoạch đã được xác nhận" in str(last_msg.content):
            return "supervisor"

    intent = state.get("intent", "general")
    return "planner" if needs_trip_plan(intent) else "agent"


def route_after_planner(state: TravelAgentState) -> str:
    """Pause only when the extracted plan has enough information to execute."""
    plan = state.get("trip_plan")
    if plan and plan.is_ready_to_search():
        return "human_confirm"
    return "agent"


def human_confirm_node(state: TravelAgentState) -> dict:
    """No-op human gate; LangGraph interrupts immediately before this node."""
    return {}


def should_continue(state: TravelAgentState) -> str:
    """
    Edge function: Quyết định agent nên tiếp tục (gọi tool) hay dừng.
    """
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


def track_tools_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node theo dõi: Ghi lại tên các tool đã được gọi.
    Node này chạy SAU tool_node, trước khi quay lại agent_node.
    """
    tools_used = list(state.get("tools_used", []))

    for message in state["messages"]:
        if isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", None)
            if tool_name and tool_name not in tools_used:
                tools_used.append(tool_name)

    return {
        "messages": [],                              # Không thêm message mới
        "trip_plan": state.get("trip_plan"),         # propagate trip_plan
        "intent": state.get("intent"),               # propagate intent
        "tools_used": tools_used,
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


# Tạo ToolNode từ LangGraph
tool_node = ToolNode(ALL_TOOLS)
