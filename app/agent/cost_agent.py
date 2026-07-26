from datetime import date
from app.agent.state import TravelAgentState
from app.services.calculator import get_decision_engine

def cost_agent_node(state: TravelAgentState) -> dict:
    """
    Cost Agent - Tham dinh chi phi va phan tich rui ro ngan sach/mau vu.
    Chay truc tiep DecisionEngine (0 LLM call, 100% chinh xac).
    """
    plan = state.get("trip_plan")
    context = dict(state.get("travel_context", {}))
    tools_used = list(state.get("tools_used", []))

    if plan and plan.destination:
        print("[COST AGENT] Analyzing feasibility and risks...")
        de = get_decision_engine()

        month = None
        if plan.dates.departure:
            try:
                month = date.fromisoformat(plan.dates.departure).month
            except ValueError:
                pass

        weather_warning = context.get("weather_warning", "")
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
        )
        context["cost_feasibility"] = report.to_text()
        tools_used.append("evaluate_trip_feasibility")

    return {
        "travel_context": context,
        "tools_used": tools_used,
    }
