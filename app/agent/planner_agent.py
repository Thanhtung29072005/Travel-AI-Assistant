import re
import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agent.state import TravelAgentState
from app.agent.llm import get_llm_plain
from app.models.trip_plan import TripPlan, TripStatus

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

def planner_node(state: TravelAgentState) -> dict:
    """
    Node lập kế hoạch (Phase 2).
    Gọi LLM nhẹ (không bind tools) để extract thông tin chuyến đi
    từ hội thoại và tạo/cập nhật TripPlan trong state.
    """
    llm = get_llm_plain()
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
        json_match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
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
        if not merged.get("destination"):
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
        new_plan.missing_fields = missing
        new_plan.confidence = 0.9 if not missing else 0.6
        new_plan.status = TripStatus.DRAFT

    except (json.JSONDecodeError, Exception):
        new_plan = existing_plan

    return {
        "messages": [],
        "trip_plan": new_plan,
        "intent": state.get("intent"),
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }
