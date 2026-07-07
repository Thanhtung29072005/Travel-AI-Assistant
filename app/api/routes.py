"""
API Routes - Định nghĩa các endpoints của Travel AI Assistant
"""
import uuid
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from app.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse
from app.agent.graph import get_agent
from app.agent.state import TravelAgentState

settings = get_settings()

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Kiểm tra trạng thái hoạt động của server
    
    Returns:
        HealthResponse: Trạng thái server và thông tin model
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        model=settings.gemini_model,
    )


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Gửi tin nhắn tới Travel AI Assistant (powered by LangGraph + Gemini)
    
    Args:
        request: ChatRequest với nội dung tin nhắn và lịch sử hội thoại
        
    Returns:
        ChatResponse: Câu trả lời từ AI và danh sách tool đã dùng
    """
    # Tạo session_id nếu chưa có
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        agent = get_agent()
        
        # Chuyển đổi lịch sử hội thoại sang LangChain message format
        history_messages = []
        for msg in (request.conversation_history or []):
            if msg.role.value == "user":
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role.value == "assistant":
                history_messages.append(AIMessage(content=msg.content))
        
        # Tạo initial state
        initial_state: TravelAgentState = {
            "messages": history_messages + [HumanMessage(content=request.message)],
            "tools_used": [],
            "travel_context": {},
            "error": None,
        }
        
        # Chạy LangGraph agent
        final_state = await agent.ainvoke(initial_state)
        
        # Lấy response cuối từ messages
        ai_messages = [
            msg for msg in final_state["messages"]
            if isinstance(msg, AIMessage) and msg.content
        ]
        
        if not ai_messages:
            raise ValueError("Agent không trả về câu trả lời")
        
        raw_content = ai_messages[-1].content
        # AIMessage.content can be `str` or `list[dict | str]` (multi-modal blocks).
        # Flatten it to a plain string for the API response.
        if isinstance(raw_content, str):
            response_text = raw_content
        else:
            response_text = " ".join(
                part if isinstance(part, str) else part.get("text", "")
                for part in raw_content
            )
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            tools_used=final_state.get("tools_used", []),
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý yêu cầu: {str(e)}"
        )
