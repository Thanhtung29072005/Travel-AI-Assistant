from langchain_core.messages import SystemMessage, HumanMessage
from app.agent.state import TravelAgentState
from app.agent.llm import get_llm_plain


def _fallback_itinerary(destination: str, days: int) -> str:
    """Return a visible, editable daily outline when the itinerary LLM fails."""
    sections = []
    for day in range(1, max(days, 1) + 1):
        if day == 1:
            activities = ["Sáng: đến nơi, nhận phòng và nghỉ ngơi.", "Chiều: khám phá khu vực trung tâm.", "Tối: thưởng thức ẩm thực địa phương."]
        elif day == max(days, 1):
            activities = ["Sáng: tham quan điểm yêu thích gần nơi ở.", "Trưa: trả phòng và chuẩn bị di chuyển.", "Chiều: kết thúc chuyến đi hoặc trở về."]
        else:
            activities = ["Sáng: tham quan điểm nổi bật.", "Chiều: hoạt động theo sở thích.", "Tối: tự do khám phá ẩm thực."]
        sections.append(f"## Ngày {day}: {destination}\n" + "\n".join(f"- {item}" for item in activities))
    return "\n\n".join(sections)

def itinerary_agent_node(state: TravelAgentState) -> dict:
    """
    Itinerary Agent - Tao suon lich trinh chi tiet.
    Goi LLM gon nhe voi system prompt chuyen biet (1 LLM call).
    """
    plan = state.get("trip_plan")
    context = dict(state.get("travel_context", {}))
    tools_used = list(state.get("tools_used", []))

    if plan and plan.destination:
        print("[ITINERARY AGENT] Generating itinerary...")
        
        # Goi model Gemini
        llm = get_llm_plain()
        
        itinerary_prompt = (
            "Bạn là Trợ lý Lập lịch trình Du lịch (Itinerary Agent).\n"
            f"Dựa trên Kế hoạch du lịch (TripPlan):\n{plan.to_summary()}\n\n"
            "Nhiệm vụ của bạn: Hãy lập lịch trình chi tiết từng ngày (ngày 1, ngày 2, ngày 3...) cực kỳ "
            "hấp dẫn, thú vị và hợp lý về địa lý tại điểm đến. Đề xuất các món ăn đặc sản địa phương "
            "cho từng bữa ăn.\n\n"
            "Trình bày cấu trúc Markdown gọn gàng. Chỉ phản hồi nội dung lịch trình lịch trình."
        )

        messages = [
            SystemMessage(content=itinerary_prompt),
            HumanMessage(content=f"Hãy lập lịch trình cho chuyến đi {plan.destination} {plan.dates.days or 3} ngày.")
        ]
        
        try:
            response = llm.invoke(messages)
            context["itinerary"] = response.content or _fallback_itinerary(plan.destination, plan.dates.days or 3)
            tools_used.append("create_travel_itinerary")
        except Exception as e:
            print(f"[ITINERARY AGENT] LLM Call failed: {e}")
            context["itinerary"] = _fallback_itinerary(plan.destination, plan.dates.days or 3)

    return {
        "travel_context": context,
        "tools_used": tools_used,
    }
