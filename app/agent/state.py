"""
Agent State - Định nghĩa cấu trúc trạng thái của LangGraph agent

State là "bộ nhớ" của agent, được truyền qua tất cả các node trong graph.
Mỗi node có thể đọc và cập nhật state.
"""
from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TravelAgentState(TypedDict):
    """
    Trạng thái của Travel AI Agent
    
    Attributes:
        messages: Lịch sử hội thoại (tự động merge khi cập nhật)
        tools_used: Danh sách tên các tool đã dùng trong phiên này
        travel_context: Thông tin du lịch đã thu thập (destination, dates, budget...)
        error: Lỗi nếu có (None = không có lỗi)
    """
    # Dùng add_messages để tự động append thay vì overwrite
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Theo dõi tool đã sử dụng (để trả về cho frontend)
    tools_used: List[str]
    
    # Context du lịch được extract từ hội thoại
    travel_context: dict
    
    # Lỗi nếu có
    error: Optional[str]
