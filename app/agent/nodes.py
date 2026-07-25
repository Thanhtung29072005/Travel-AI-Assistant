"""
Agent Nodes - Các bước xử lý trong LangGraph workflow

Mỗi node là một function nhận state, xử lý, và trả về state mới.

Phase 2 Pipeline:
  START → intent_node → (plan_trip?) → planner_node → agent_node → ...
                       → (general)  → agent_node → ...
”"""
from __future__ import annotations

import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langgraph.prebuilt import ToolNode

from app.config import get_settings
from app.agent.state import TravelAgentState
from app.agent.tools import ALL_TOOLS
from app.agent.intent import classify_intent, needs_trip_plan
from app.models.trip_plan import (
    TripPlan, TripType, ComfortLevel, TripStatus, DateRange, Budget,
)

settings = get_settings()

# ============================================================
# System Prompt - "Tính cách" và hướng dẫn của AI Travel Assistant
# ============================================================
SYSTEM_PROMPT = """Bạn là trợ lý du lịch thông minh tên **Hana**, chuyên tư vấn chuyến đi cho người Việt.

## Nhiệm vụ chính:
Giúp người dùng chuyển đổi ý tưởng du lịch mơ hồ thành một kế hoạch **khả thi, rõ ràng, đáng đồng tiền**.
Mục tiêu KHÔNG phải là chatbot du lịch chung chung — mà là trợ lý *quyết định* chuyến đi:
- Kiểm tra lịch trình có quá dày không
- Ước tính tổng chi phí thực tế
- Cảnh báo rủi ro (thời tiết, mùa du lịch, ngân sách không đủ)
- Đề xuất phương án cụ thể để người dùng có thể booking ngay

## Luồng làm việc:
1. **Thu thập thông tin**: Hỏi điểm đến, ngày đi, số người, ngân sách, sở thích
2. **Lập kế hoạch (TripPlan)**: Tổng hợp thông tin thành kế hoạch có cấu trúc
3. **Xác nhận với người dùng**: Trình bày TripPlan và hỏi có cần chỉnh sửa gì không
4. **Tìm kiếm & phân tích**: Dùng tool tìm thông tin thực tế (chuyến bay, khách sạn, thời tiết)
5. **Tổng hợp & khuyến nghị**: Đưa ra gợi ý cụ thể với lý do rõ ràng

## Khi thu thập thông tin, luôn hỏi để rõ:
- Điểm đến và điểm xuất phát
- Thời gian (ngày đi, số ngày)
- Số người và loại nhóm (cặp đôi, gia đình, bạn bè)
- Ngân sách tổng hoặc mỗi người
- Sở thích và mức độ thoải mái (tiết kiệm / tầm trung / cao cấp)

## Nguyên tắc bất biến:
- Dùng tool để lấy thông tin thực tế, KHÔNG đoán mò giá cả
- Khi có TripPlan (xem dưới đây): dùng nó làm nền tảng cho mọi câu trả lời.
- **Quy tắc HITL**: Nếu trạng thái kế hoạch là 'draft' (nháp), hãy liệt kê tóm tắt ngắn gọn và nhắc người dùng xem qua biểu mẫu ở bảng bên phải để kiểm tra thông tin, sau đó bấm nút "Xác nhận & Tìm kiếm" để bắt đầu tìm thông tin chi tiết. Tránh gọi các tool tìm kiếm (như search_travel_info hay evaluate_trip_feasibility) cho đến khi trạng thái chuyển sang 'confirmed'.
- Trình bày lịch trình rõ ràng, có timeline và chi phí ước tính từng mục
"""


# ============================================================
# Planner Prompt - Hướng dẫn LLM extract TripPlan từ hội thoại
# ============================================================
PLANNER_PROMPT = """Bạn là bộ phân tích thông tin chuyến đi. Nhiệm vụ duy nhất:
Từ lịch sử hội thoại, extract các thông tin và trả về JSON hợp lệ.

KHONG trả lời thêm gì khác ngoài JSON. KHONG giải thích.

JSON schema:
{
  "destination": string | null,       // Điểm đến chính
  "origin": string | null,            // Điểm xuất phát
  "days": int | null,                 // Số ngày
  "departure": "YYYY-MM-DD" | null,   // Ngày đi
  "return_date": "YYYY-MM-DD" | null, // Ngày về
  "travelers": int | null,            // Số người
  "trip_type": "solo"|"couple"|"family"|"friends"|"business" | null,
  "budget_total": float | null,       // Tổng ngân sách (VND)
  "budget_per_person": float | null,  // Ngân sách mỗi người
  "currency": "VND" | "USD",
  "comfort_level": "budget"|"medium"|"comfort"|"luxury" | null,
  "preferences": [string],            // Sở thích du lịch
  "must_have": [string],              // Bắt buộc phải có
  "avoid": [string]                   // Muốn tránh
}

Quy tắc:
- Nếu không có thông tin, để null
- Làm lại những gì đã biết từ TripPlan hiện tại (nếu có), không xóa thông tin cũ nếu người dùng không sửa
- "3 triệu / người" → budget_per_person: 3000000
- "cặp đôi", "2 người" → travelers: 2, trip_type: "couple"
"""


def _get_llm():
    """Khởi tạo Gemini LLM với tools"""
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=settings.temperature,
    )
    # Bind tools vào LLM để model biết có thể gọi tool nào
    return llm.bind_tools(ALL_TOOLS)  # type: ignore


def _get_llm_plain():
    """Khởi tạo Gemini LLM không có tools (dùng cho planner)"""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.0,  # Planner cần output deterministic
    )


# ============================================================
# Phase 2: intent_node
# ============================================================

def intent_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node nhận diện ý định (Phase 2).

    Dùng heuristic keyword matching — KHONG gọi LLM.
    Nhanh (~0ms), không tốn quota.

    Đặt state["intent"] cho conditional edge phía sau.
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
        intent = classify_intent(last_human.content)

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

    Returns:
        "planner" nếu intent là plan_trip
        "agent"   cho tất cả các trường hợp khác
    """
    # Nếu kế hoạch đã được xác nhận (confirmed) hoặc tin nhắn chứa trigger từ form,
    # bỏ qua planner_node để tránh bị LLM ghi đè các tham số đã được người dùng chỉnh sửa và phê duyệt.
    trip_plan = state.get("trip_plan")
    if trip_plan and trip_plan.status == "confirmed":
        return "agent"

    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "content") and "Kế hoạch đã được xác nhận" in str(last_msg.content):
            return "agent"

    intent = state.get("intent", "general")
    return "planner" if needs_trip_plan(intent) else "agent"


# ============================================================
# Phase 2: planner_node
# ============================================================

def planner_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node lập kế hoạch (Phase 2).

    Gọi LLM nhẹ (không bind tools) để extract thông tin chuyến đi
    từ hội thoại và tạo/cập nhật TripPlan trong state.

    Sau node này, agent_node sẽ có TripPlan để làm ngữ cảnh.
    """
    llm = _get_llm_plain()
    messages = state["messages"]

    # Xây dựng conversation text cho planner
    conversation_lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            conversation_lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            text = m.content if isinstance(m.content, str) else str(m.content)
            conversation_lines.append(f"Assistant: {text[:300]}")
    conversation_text = "\n".join(conversation_lines[-10:])  # Giới hạn 10 lượt gần nhất

    # Bổ sung TripPlan hiện tại (nếu có) để planner merge thay vì ghi đè
    existing_plan = state.get("trip_plan")
    existing_json = ""
    if existing_plan is not None:
        existing_json = (
            "\n\nTripPlan hiện tại (chỉ cập nhật những gì thay đổi):\n"
            + existing_plan.model_dump_json(exclude_none=True, indent=2)
        )

    planner_messages = [
        SystemMessage(content=PLANNER_PROMPT + existing_json),
        HumanMessage(content=f"Hội thoại:\n{conversation_text}\n\nHãy trả về JSON:"),
    ]

    try:
        response = llm.invoke(planner_messages)
        raw = response.content if isinstance(response.content, str) else str(response.content)

        # Parse JSON từ response
        # Tìm JSON block (có thể bọc trong ```json ... ```)
        json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            # Thử tìm { ... } trực tiếp
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)

        extracted = json.loads(raw)

        # Merge với TripPlan hiện tại hoặc tạo mới
        base = existing_plan.model_dump() if existing_plan else {}

        # Flatten dates từ extracted vào nested DateRange
        date_range = base.get("dates", {}) or {}
        if extracted.get("days") is not None:
            date_range["days"] = extracted.pop("days")
        if extracted.get("departure") is not None:
            date_range["departure"] = extracted.pop("departure")
        if extracted.get("return_date") is not None:
            date_range["return_date"] = extracted.pop("return_date")
        if date_range:
            extracted["dates"] = date_range

        # Flatten budget
        budget = base.get("budget", {}) or {}
        if extracted.get("budget_total") is not None:
            budget["total"] = extracted.pop("budget_total")
        if extracted.get("budget_per_person") is not None:
            budget["per_person"] = extracted.pop("budget_per_person")
        if extracted.get("currency") is not None:
            budget["currency"] = extracted.pop("currency", "VND")
        if budget:
            extracted["budget"] = budget

        # Merge: base ← extracted (chỉ override nếu không null)
        merged = {**base, **{k: v for k, v in extracted.items() if v is not None}}
        merged.pop("status", None)       # Giữ status là DRAFT
        merged.pop("confidence", None)   # Sẽ tính lại dưới
        merged.pop("missing_fields", None)

        # Tạo TripPlan từ merged data
        # Đảm bảo destination có giá trị (required field)
        if not merged.get("destination"):
            # Chưa extract được destination → giữ plan cũ hoặc bỏ qua
            return {
                "messages": [],
                "trip_plan": existing_plan,
                "intent": state.get("intent"),
                "tools_used": state.get("tools_used", []),
                "travel_context": state.get("travel_context", {}),
                "error": None,
            }

        new_plan = TripPlan(**merged)

        # Tính missing_fields
        missing = []
        if not new_plan.dates.days and not new_plan.dates.departure:
            missing.append("dates.days")
        if not new_plan.budget.total and not new_plan.budget.per_person:
            missing.append("budget.total")
        if new_plan.travelers == 1 and new_plan.trip_type == "solo":
            # Có thể chưa hỏi số người
            pass
        new_plan.missing_fields = missing
        new_plan.confidence = 0.9 if not missing else 0.6
        new_plan.status = TripStatus.DRAFT

    except (json.JSONDecodeError, Exception):
        # Parse thất bại → giữ plan cũ, không crash pipeline
        new_plan = existing_plan

    return {
        "messages": [],          # Planner không thêm message vào chat
        "trip_plan": new_plan,
        "intent": state.get("intent"),
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


def agent_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node chính: Gọi Gemini để xử lý tin nhắn và quyết định có dùng tool không.

    Phase 1: Nếu state đã có trip_plan, chèn bản tóm tắt kế hoạch vào
    đầu conversation dưới dạng system context để LLM luôn biết ngữ cảnh.

    Args:
        state: Trạng thái hiện tại của agent

    Returns:
        State mới với response từ AI (có thể là ToolCall hoặc AIMessage)
    """
    llm_with_tools = _get_llm()

    # ── Xây dựng system prompt ────────────────────────────
    system_content = SYSTEM_PROMPT

    # Nếu đã có TripPlan, bổ sung vào system context
    trip_plan = state.get("trip_plan")
    if trip_plan is not None:
        plan_summary = trip_plan.to_summary()
        missing = trip_plan.missing_fields
        missing_note = (
            f"\n- Còn thiếu thông tin: {', '.join(missing)}" if missing else ""
        )
        system_content += (
            f"\n\n---\n## Kế hoạch chuyến đi hiện tại (TripPlan):\n"
            f"{plan_summary}"
            f"\n- Trạng thái: {trip_plan.status}"
            f"{missing_note}"
            f"\n---\n"
            "Hãy dựa trên TripPlan này để trả lời. "
            "Nếu người dùng cung cấp thông tin mới, hãy nhớ cập nhật kế hoạch."
        )

    # ── Gắn system prompt vào messages ───────────────────
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_content)] + messages
    else:
        # Cập nhật system prompt hiện tại (có thể đã thêm trip_plan context)
        messages = [SystemMessage(content=system_content)] + messages[1:]

    # ── Gọi LLM ──────────────────────────────────────────
    response = llm_with_tools.invoke(messages)

    return {
        "messages": [response],
        "trip_plan": state.get("trip_plan"),      # giữ nguyên trip_plan
        "intent": state.get("intent"),             # giữ nguyên intent
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


def should_continue(state: TravelAgentState) -> str:
    """
    Edge function: Quyết định agent nên tiếp tục (gọi tool) hay dừng.
    
    Returns:
        "tools" nếu LLM muốn gọi tool
        "end" nếu LLM đã có câu trả lời cuối
    """
    last_message = state["messages"][-1]
    
    # Nếu message cuối có tool_calls → cần thực thi tool
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


def track_tools_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node theo dõi: Ghi lại tên các tool đã được gọi.

    Node này chạy SAU tool_node, trước khi quay lại agent_node.
    Phase 1: Đảm bảo propagate trip_plan và intent qua vòng lặp.
    """
    tools_used = list(state.get("tools_used", []))

    # Lấy tên tool từ messages (ToolMessage có attribute name)
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


# Tạo ToolNode từ LangGraph (tự động xử lý việc gọi tools)
tool_node = ToolNode(ALL_TOOLS)
