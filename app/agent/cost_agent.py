from datetime import date
from app.agent.state import TravelAgentState
from app.services.calculator import get_decision_engine
from app.providers.gateway import fetch_flights, fetch_hotels

def cost_agent_node(state: TravelAgentState) -> dict:
    """
    Cost Agent - Tham dinh chi phi va phan tich rui ro dua tren du lieu Gateway.
    """
    plan = state.get("trip_plan")
    context = dict(state.get("travel_context", {}))
    tools_used = list(state.get("tools_used", []))

    if plan and plan.destination:
        print("[COST AGENT] Fetching flight and hotel options from Gateway...")
        
        # 1. Tra cứu vé máy bay thực tế/mock từ Gateway
        flights = fetch_flights(
            origin=plan.origin or "Hà Nội",
            destination=plan.destination,
            departure_date=plan.dates.departure or "2026-08-10",
            return_date=plan.dates.return_date
        )
        
        # 2. Tra cứu khách sạn thực tế/mock từ Gateway
        hotels = fetch_hotels(
            destination=plan.destination,
            comfort_level=plan.comfort_level or "medium"
        )
        
        # 3. Lưu trữ kết quả tìm kiếm vào travel_context dưới dạng text để Response Agent hiển thị
        context["flights"] = [f.to_text() for f in flights]
        context["hotels"] = [h.to_text() for h in hotels]
        
        print("[COST AGENT] Analyzing feasibility and risks based on fetched options...")
        de = get_decision_engine()

        month = None
        if plan.dates.departure:
            try:
                month = date.fromisoformat(plan.dates.departure).month
            except ValueError:
                pass

        weather_warning = context.get("weather_warning", "")
        
        # Thẩm định chi phí thực tế dựa trên danh sách chuyến bay & khách sạn tìm được
        report = de.evaluate(
            destination=plan.destination,
            days=plan.dates.days or 1,
            travelers=plan.travelers,
            comfort_level=plan.comfort_level,
            budget_provided=plan.budget.total or 0.0,
            nights=plan.dates.nights,
            origin=plan.origin,
            departure_month=month,
            weather_warning=weather_warning,
            flight_options=flights,
            hotel_options=hotels
        )
        context["cost_feasibility"] = report.to_text()
        tools_used.append("evaluate_trip_feasibility")

    return {
        "travel_context": context,
        "tools_used": tools_used,
    }
