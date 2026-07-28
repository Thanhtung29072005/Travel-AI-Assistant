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

    # OpenWeatherMap (https://openweathermap.org/api — free tier đủ dùng)
    openweathermap_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # SQL Server Settings
    sql_server: str = ""
    sql_server_host: str = ""
    sql_server_port: int = 1433
    sql_server_database: str = "Travel_AI_ASSISTANT"
    sql_server_user: str = ""
    sql_server_password: str = ""
    sql_username: str = ""
    sql_password: str = ""

    # LLM Settings
    gemini_model: str = "gemini-flash-latest"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Durable LangGraph HITL checkpoints. Relative paths are resolved from the
    # application working directory, e.g. /app/data inside Docker.
    checkpoint_db_path: str = "data/langgraph_checkpoints.sqlite"

    # SerpApi
    serpapi_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Lấy cấu hình ứng dụng (cached - chỉ load 1 lần)
    
    Returns:
        Settings: Object chứa tất cả cấu hình
    """
    return Settings()
