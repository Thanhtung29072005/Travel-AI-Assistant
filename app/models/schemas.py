"""
Pydantic Schemas - Định nghĩa cấu trúc dữ liệu cho API

Các model này được dùng để:
- Validate request/response data
- Tự động tạo OpenAPI docs
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class MessageRole(str, Enum):
    """Vai trò của người gửi tin nhắn"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Một tin nhắn trong cuộc hội thoại"""
    role: MessageRole = Field(description="Vai trò: user/assistant/system")
    content: str = Field(description="Nội dung tin nhắn")


class ChatRequest(BaseModel):
    """Request body cho endpoint /api/chat"""
    message: str = Field(
        description="Tin nhắn của người dùng",
        min_length=1,
        max_length=2000,
        examples=["Tôi muốn đi du lịch Đà Nẵng 3 ngày với ngân sách 5 triệu"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="ID phiên chat (để duy trì lịch sử hội thoại)"
    )
    conversation_history: Optional[List[Message]] = Field(
        default=[],
        description="Lịch sử hội thoại trước đó"
    )


class ChatResponse(BaseModel):
    """Response body từ endpoint /api/chat"""
    response: str = Field(description="Câu trả lời từ AI")
    session_id: str = Field(description="Session ID của cuộc hội thoại")
    tools_used: List[str] = Field(
        default=[],
        description="Danh sách tool đã được AI sử dụng"
    )


class HealthResponse(BaseModel):
    """Response body từ endpoint /api/health"""
    status: str = Field(description="Trạng thái server: ok/error")
    version: str = Field(description="Phiên bản ứng dụng")
    model: str = Field(description="Model AI đang dùng")
