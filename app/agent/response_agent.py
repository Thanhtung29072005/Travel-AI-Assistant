from langchain_core.messages import SystemMessage
from app.agent.state import TravelAgentState
from app.agent.llm import get_llm_with_tools, get_llm_plain
from app.agent.tools import ALL_TOOLS

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

def agent_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node chính (Response Agent/Consolidator):
    Gọi Gemini để trả lời người dùng. Nếu đã confirm kế hoạch, ta không cần dùng tool nữa.
    """
    # Nếu đã có TripPlan, bổ sung vào system context
    trip_plan = state.get("trip_plan")
    
    if trip_plan and trip_plan.status == "confirmed":
        llm = get_llm_plain()
    else:
        llm = get_llm_with_tools(ALL_TOOLS)

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

    # Nạp thông tin thu thập được từ các Agent con (travel_context)
    travel_context = state.get("travel_context", {})
    context_str = ""
    if travel_context.get("weather"):
        context_str += f"\n### Dữ liệu Thời tiết:\n{travel_context['weather']}\n"
    if travel_context.get("flights"):
        flights_list = "\n".join([f"  {f}" for f in travel_context["flights"]])
        context_str += f"\n### Các chuyến bay đề xuất:\n{flights_list}\n"
    if travel_context.get("hotels"):
        hotels_list = "\n".join([f"  {h}" for h in travel_context["hotels"]])
        context_str += f"\n### Các khách sạn đề xuất:\n{hotels_list}\n"
    if travel_context.get("cost_feasibility"):
        context_str += f"\n### Dữ liệu Thẩm định Chi phí & Rủi ro:\n{travel_context['cost_feasibility']}\n"
    if travel_context.get("itinerary"):
        context_str += f"\n### Gợi ý Lịch trình chi tiết:\n{travel_context['itinerary']}\n"

    if context_str:
        system_content += (
            f"\n\n---\n## DỮ LIỆU ĐÃ THU THẬP ĐƯỢC TỪ CÁC AGENT CHUYÊN TRÁCH:\n{context_str}\n---\n"
            "Nhiệm vụ của bạn: Hãy tổng hợp toàn bộ dữ liệu trên thành một câu trả lời hoàn chỉnh, "
            "chi tiết, hấp dẫn và gửi tới người dùng. Trình bày lịch trình ngày một cách sinh động, "
            "nêu rõ dự toán chi phí tổng hợp và các cảnh báo rủi ro (nếu có)."
        )

    # Gắn system prompt vào messages
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_content)] + messages
    else:
        messages = [SystemMessage(content=system_content)] + messages[1:]

    # Gọi LLM
    response = llm.invoke(messages)

    return {
        "messages": [response],
        "trip_plan": state.get("trip_plan"),
        "intent": state.get("intent"),
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }
