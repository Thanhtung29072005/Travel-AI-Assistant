from app.agent.state import TravelAgentState

def supervisor_node(state: TravelAgentState) -> dict:
    """
    Supervisor Node - Chi dong vai tro ghi nhan log trang thai truoc khi dinh tuyen.
    """
    print("[SUPERVISOR] Analyzing travel_context to coordinate sub-agents...")
    return {}


def route_supervisor(state: TravelAgentState) -> str:
    """
    Conditional Edge tu supervisor:
    Dinh tuyen dua tren tinh day du cua du lieu thu thap duoc trong travel_context.
    """
    plan = state.get("trip_plan")
    context = state.get("travel_context", {})
    
    if not plan:
        print("[SUPERVISOR] No plan found, routing to agent.")
        return "agent"

    # 1. Can du lieu thoi tiet?
    if "weather" not in context:
        print("[SUPERVISOR] Routing to: weather_agent")
        return "weather_agent"

    # 2. Can du lieu tham dinh chi phi / rui ro?
    if "cost_feasibility" not in context:
        print("[SUPERVISOR] Routing to: cost_agent")
        return "cost_agent"

    # 3. Can lich trinh chi tiet?
    if "itinerary" not in context:
        print("[SUPERVISOR] Routing to: itinerary_agent")
        return "itinerary_agent"

    # 4. Khi da thu thap du ➔ Chuyen tiep toi Agent chinh (Response Agent) tong hop
    print("[SUPERVISOR] Context complete. Routing to: agent (Consolidator)")
    return "agent"
