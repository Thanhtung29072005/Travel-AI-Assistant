from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings

settings = get_settings()

def get_llm_plain() -> ChatGoogleGenerativeAI:
    """Khởi tạo LLM không ràng buộc tools (cho planner và specialized agents)"""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=0.0,
        google_api_key=settings.google_api_key,
    )

def get_llm_with_tools(tools: list) -> ChatGoogleGenerativeAI:
    """Khởi tạo LLM có ràng buộc tools (cho ReAct Agent loop)"""
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.temperature,
        google_api_key=settings.google_api_key,
    )
    return llm.bind_tools(tools)
