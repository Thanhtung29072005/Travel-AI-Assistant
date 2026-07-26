from app.agent.state import TravelAgentState
from app.services.weather import get_weather_service

def weather_agent_node(state: TravelAgentState) -> dict:
    """
    Weather Agent - Tra cuu du bao thoi tiet tai diem den.
    Chay truc tiep WeatherService (0 LLM call, 100% chinh xac).
    """
    plan = state.get("trip_plan")
    context = dict(state.get("travel_context", {}))
    tools_used = list(state.get("tools_used", []))

    if plan and plan.destination:
        print("[WEATHER AGENT] Fetching weather...")
        ws = get_weather_service()
        # Mac dinh lay du bao 5 ngay hoac theo so ngay di
        weather = ws.get_weather(plan.destination, plan.dates.days or 5)
        context["weather"] = weather.to_text()
        tools_used.append("get_weather_forecast")

    return {
        "travel_context": context,
        "tools_used": tools_used,
    }
