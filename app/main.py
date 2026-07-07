"""
FastAPI Main Application

Entry point của ứng dụng Travel AI Assistant
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.api.routes import router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động và tắt ứng dụng"""
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}...")
    print(f"AI Model: {settings.gemini_model}")
    yield
    # Shutdown
    print("Server shutting down...")


# Khởi tạo FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Trợ lý du lịch thông minh powered by Google Gemini + LangGraph",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware (cho phép frontend kết nối)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production, chỉ định domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký routes
app.include_router(router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
