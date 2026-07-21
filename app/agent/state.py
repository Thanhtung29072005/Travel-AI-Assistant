"""
Agent State - Định nghĩa cấu trúc trạng thái của LangGraph agent

State là "bộ nhớ" của agent, được truyền qua tất cả các node trong graph.
Mỗi node có thể đọc và cập nhật state.

Thay đổi so với phiên bản cũ:
- Thêm `trip_plan`: Optional[TripPlan] để giữ kế hoạch chuyến đi đã chuẩn hóa
- Thêm `intent`: nhận diện ý định của người dùng (lên lịch, hỏi thời tiết, ...)
- Giữ nguyên `travel_context` (dict) cho dữ liệu tạm thời chưa được normalize
"""
from __future__ import annotations

from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.models.trip_plan import TripPlan


class TravelAgentState(TypedDict):
    """
    Trạng thái của Travel AI Agent.

    Attributes:
        messages:       Lịch sử hội thoại (tự động merge khi cập nhật)
        trip_plan:      Kế hoạch chuyến đi đã chuẩn hóa (None nếu chưa có)
        intent:         Ý định của người dùng được nhận diện gần nhất
        tools_used:     Danh sách tên các tool đã dùng trong phiên này
        travel_context: Dữ liệu thô/tạm thời chưa normalize (dict tự do)
        error:          Lỗi nếu có (None = không có lỗi)
    """

    # Lịch sử hội thoại – dùng add_messages để tự động append thay vì overwrite
    messages: Annotated[List[BaseMessage], add_messages]

    # Kế hoạch chuyến đi chuẩn hóa.
    # None khi phiên mới bắt đầu.
    # Được tạo/cập nhật bởi planner_node (Phase 2).
    trip_plan: Optional[TripPlan]

    # Ý định nhận diện: "plan_trip" | "ask_weather" | "ask_info" | "general"
    # Được set bởi intent_node (Phase 2).
    intent: Optional[str]

    # Tên các tool đã được gọi (để trả về frontend hiển thị)
    tools_used: List[str]

    # Context du lịch dạng dict tự do – dùng để lưu dữ liệu tạm thời
    # trước khi được normalize vào TripPlan hoặc response
    travel_context: dict

    # Lỗi nếu có
    error: Optional[str]
