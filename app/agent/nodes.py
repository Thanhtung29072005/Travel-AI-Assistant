"""
Agent Nodes - Các bước xử lý trong LangGraph workflow

Mỗi node là một function nhận state, xử lý, và trả về state mới.
Flow: agent_node → (nếu cần tool) → tool_node → agent_node → END
"""
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from app.config import get_settings
from app.agent.state import TravelAgentState
from app.agent.tools import ALL_TOOLS

settings = get_settings()

# ============================================================
# System Prompt - "Tính cách" của AI Travel Assistant
# ============================================================
SYSTEM_PROMPT = """Bạn là một trợ lý du lịch thông minh và nhiệt tình tên là **Hana** 🌸.
Bạn giúp người dùng lên kế hoạch du lịch hoàn hảo tại Việt Nam và quốc tế.

## Khả năng của bạn:
- 🔍 Tìm kiếm thông tin khách sạn, vé máy bay, địa điểm
- 📅 Lên lịch trình du lịch chi tiết theo từng ngày
- 🗺️ Gợi ý địa điểm tham quan, nhà hàng, hoạt động
- 💰 Tính toán và tư vấn ngân sách du lịch

## Nguyên tắc:
- Luôn trả lời bằng tiếng Việt, thân thiện và nhiệt tình
- Hỏi thêm thông tin khi cần (điểm đến, ngày đi, ngân sách, sở thích)
- Dùng tool để tra cứu thông tin thực tế, không đoán mò
- Trình bày lịch trình rõ ràng, dễ đọc với emoji
- Luôn đề xuất các lựa chọn dự phòng

## Phong cách:
- Thân thiện, vui vẻ như người bạn đồng hành đáng tin cậy
- Cụ thể và thực tế, không chung chung
- Proactive: gợi ý những điều người dùng chưa nghĩ tới
"""


def _get_llm():
    """Khởi tạo Gemini LLM với tools"""
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=settings.temperature,
    )
    # Bind tools vào LLM để model biết có thể gọi tool nào
    return llm.bind_tools(ALL_TOOLS)


def agent_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node chính: Gọi Gemini để xử lý tin nhắn và quyết định có dùng tool không.
    
    Args:
        state: Trạng thái hiện tại của agent
        
    Returns:
        State mới với response từ AI (có thể là ToolCall hoặc AIMessage)
    """
    llm_with_tools = _get_llm()
    
    # Thêm system prompt vào đầu messages nếu chưa có
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
    
    # Gọi LLM
    response = llm_with_tools.invoke(messages)
    
    return {
        "messages": [response],
        "tools_used": state.get("tools_used", []),
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


def should_continue(state: TravelAgentState) -> str:
    """
    Edge function: Quyết định agent nên tiếp tục (gọi tool) hay dừng.
    
    Returns:
        "tools" nếu LLM muốn gọi tool
        "end" nếu LLM đã có câu trả lời cuối
    """
    last_message = state["messages"][-1]
    
    # Nếu message cuối có tool_calls → cần thực thi tool
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


def track_tools_node(state: TravelAgentState) -> TravelAgentState:
    """
    Node theo dõi: Ghi lại tên các tool đã được gọi.
    
    Node này chạy SAU tool_node, trước khi quay lại agent_node.
    """
    tools_used = list(state.get("tools_used", []))
    
    # Lấy tên tool từ messages (ToolMessage có attribute name)
    for message in state["messages"]:
        if isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", None)
            if tool_name and tool_name not in tools_used:
                tools_used.append(tool_name)
    
    return {
        "messages": [],  # Không thêm message mới
        "tools_used": tools_used,
        "travel_context": state.get("travel_context", {}),
        "error": None,
    }


# Tạo ToolNode từ LangGraph (tự động xử lý việc gọi tools)
tool_node = ToolNode(ALL_TOOLS)
