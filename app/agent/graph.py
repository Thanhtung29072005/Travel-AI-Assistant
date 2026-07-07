"""
LangGraph Graph - Định nghĩa luồng xử lý của Travel AI Agent

Graph là "bản đồ" mô tả cách agent hoạt động:
  START → agent_node → (cần tool?) → tool_node → track_tools → agent_node
                     → (không cần)  → END
"""
from langgraph.graph import StateGraph, START, END

from app.agent.state import TravelAgentState
from app.agent.nodes import (
    agent_node,
    tool_node,
    track_tools_node,
    should_continue,
)


def create_travel_agent() -> StateGraph:
    """
    Tạo và compile LangGraph workflow cho Travel AI Agent.
    
    Returns:
        Compiled graph sẵn sàng để invoke
    """
    # 1. Khởi tạo graph với State schema
    graph = StateGraph(TravelAgentState)
    
    # 2. Thêm các nodes
    graph.add_node("agent", agent_node)        # Node AI chính
    graph.add_node("tools", tool_node)         # Node thực thi tools
    graph.add_node("track_tools", track_tools_node)  # Node ghi log tools
    
    # 3. Định nghĩa luồng (edges)
    # START → agent (bắt đầu từ agent_node)
    graph.add_edge(START, "agent")
    
    # agent → (conditional) → tools HOẶC END
    graph.add_conditional_edges(
        source="agent",
        path=should_continue,
        path_map={
            "tools": "tools",  # Gọi tool nếu cần
            "end": END,        # Kết thúc nếu đã có câu trả lời
        }
    )
    
    # tools → track_tools → agent (vòng lặp: tool xong → AI xử lý kết quả)
    graph.add_edge("tools", "track_tools")
    graph.add_edge("track_tools", "agent")
    
    # 4. Compile graph
    return graph.compile()


# Singleton instance (lazy initialization)
_agent_graph = None


def get_agent() -> StateGraph:
    """
    Lấy agent graph instance (singleton pattern).
    
    Returns:
        Compiled LangGraph agent
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_travel_agent()
    return _agent_graph
