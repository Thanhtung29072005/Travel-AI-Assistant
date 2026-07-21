"""
Agent Nodes - Các bước xử lý trong LangGraph workflow

Mỗi node là một function nhận state, xử lý, và trả về state mới.
Flow: agent_node → (nếu cần tool) → tool_node → track_tools → agent_node → END

Phase 1 changes:
- agent_node giờ tự động chèn TripPlan summary vào context nếu đã có kế hoạch
- track_tools_node propagate trip_plan và intent qua các lần lặp
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.config import get_settings
from app.agent.state import TravelAgentState
from app.agent.tools import ALL_TOOLS

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
- Luôn trả lời bằng tiếng Việt, thân thiện, cụ thể
- Dùng tool để lấy thông tin thực tế, KHÔNG đoán mò giá cả
- Khi có TripPlan (xem dưới đây): dùng nó làm nền tảng cho mọi câu trả lời
- Trình bày lịch trình rõ ràng, có timeline và chi phí ước tính từng mục
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
