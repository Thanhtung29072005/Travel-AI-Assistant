"""
API Routes - Định nghĩa các endpoints của Travel AI Assistant
"""
import uuid
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

from app.config import get_settings
from app.models.schemas import (
    ChatRequest, ChatResponse,
    HealthResponse, ErrorResponse,
)
from app.agent.graph import get_agent
from app.agent.state import TravelAgentState
from app.services.search import get_search_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ──────────────────────────────────────────
# Exception handlers (dùng trong routes)
# ──────────────────────────────────────────

def _error_response(
    status_code: int,
    error: str,
    message: str,
    session_id: str | None = None,
) -> JSONResponse:
    """Tạo JSONResponse lỗi chuẩn hóa"""
    body = ErrorResponse(error=error, message=message, session_id=session_id)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _extract_text(content) -> str:
    """Flatten AIMessage.content (str hoặc list block) thành plain text"""
    if isinstance(content, str):
        return content
    return " ".join(
        part if isinstance(part, str) else part.get("text", "")
        for part in content
    )


# ──────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Kiểm tra trạng thái server",
)
async def health_check():
    """
    Trả về trạng thái hoạt động của server,
    phiên bản model AI đang dùng,
    và Tavily search có được bật không.
    """
    search = get_search_service()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        model=settings.gemini_model,
        search_enabled=search.is_enabled,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Request không hợp lệ"},
        408: {"model": ErrorResponse, "description": "Agent xử lý quá lâu (timeout)"},
        429: {"model": ErrorResponse, "description": "Vượt quota API Gemini"},
        500: {"model": ErrorResponse, "description": "Lỗi server nội bộ"},
    },
    tags=["Chat"],
    summary="Gửi tin nhắn tới Travel AI",
)
async def chat(request: ChatRequest):
    """
    Gửi tin nhắn tới **Travel AI Assistant** (Hana).

    - Hana sẽ tự động chọn tool phù hợp (tìm kiếm, tính ngân sách, v.v.).
    - Truyền `conversation_history` để duy trì ngữ cảnh hội thoại.
    - `session_id` được tạo tự động nếu không truyền vào.
    """
    session_id = request.session_id or str(uuid.uuid4())

    # ── Chuyển đổi lịch sử hội thoại ──
    history: list = []
    for msg in (request.conversation_history or []):
        if msg.role.value == "user":
            history.append(HumanMessage(content=msg.content))
        elif msg.role.value == "assistant":
            history.append(AIMessage(content=msg.content))

    initial_state: TravelAgentState = {
        "messages": history + [HumanMessage(content=request.message)],
        "tools_used": [],
        "travel_context": {},
        "error": None,
    }

    # ── Gọi LangGraph agent ──
    try:
        agent = get_agent()
        final_state = await agent.ainvoke(initial_state)

    except ResourceExhausted as e:
        # Gemini API quota vượt giới hạn (429)
        logger.warning("Gemini quota exceeded: %s", e)
        return _error_response(
            429,
            error="quota_exceeded",
            message=(
                "API Gemini đã vượt giới hạn miễn phí. "
                "Vui lòng thử lại sau vài phút hoặc nâng cấp gói."
            ),
            session_id=session_id,
        )

    except TimeoutError as e:
        logger.warning("Agent timeout: %s", e)
        return _error_response(
            408,
            error="agent_timeout",
            message="Trợ lý đang xử lý quá lâu, vui lòng thử lại.",
            session_id=session_id,
        )

    except GoogleAPIError as e:
        logger.error("Google API error: %s", e)
        return _error_response(
            502,
            error="upstream_error",
            message=f"Lỗi từ Google API: {str(e)[:120]}",
            session_id=session_id,
        )

    except Exception as e:
        logger.exception("Unexpected error in /chat")
        return _error_response(
            500,
            error="internal_error",
            message=f"Lỗi nội bộ: {str(e)[:200]}",
            session_id=session_id,
        )

    # ── Lấy câu trả lời cuối ──
    ai_messages = [
        m for m in final_state["messages"]
        if isinstance(m, AIMessage) and m.content
    ]

    if not ai_messages:
        return _error_response(
            500,
            error="empty_response",
            message="Agent không trả về câu trả lời. Vui lòng thử lại.",
            session_id=session_id,
        )

    return ChatResponse(
        response=_extract_text(ai_messages[-1].content),
        session_id=session_id,
        tools_used=final_state.get("tools_used", []),
    )
