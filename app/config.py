"""
Application Configuration & Settings

Quản lý tất cả cấu hình từ biến môi trường (.env)
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Cấu hình ứng dụng từ file .env"""
    
    # App Info
    app_name: str = "Travel AI Assistant"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Google Gemini
    google_api_key: str
    
    # Tavily Search
    tavily_api_key: str = ""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # LLM Settings
    gemini_model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 4096

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Lấy cấu hình ứng dụng (cached - chỉ load 1 lần)
    
    Returns:
        Settings: Object chứa tất cả cấu hình
    """
    return Settings()
