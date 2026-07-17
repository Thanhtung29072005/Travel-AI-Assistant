"""
FastAPI Main Application

Entry point của ứng dụng Travel AI Assistant
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from app.config import get_settings
from app.api.routes import router


settings = get_settings()

# Đường dẫn tuyệt đối tới thư mục static
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động và tắt ứng dụng"""
    print(f"Starting {settings.app_name} v{settings.app_version}...")
    print(f"AI Model: {settings.gemini_model}")
    print(f"Frontend: http://{settings.host}:{settings.port}/")
    yield
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

# Đăng ký API routes
app.include_router(router, prefix="/api")

# Phục vụ static files (CSS, JS, images)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Route gốc → trả về frontend HTML
@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Phục vụ giao diện chat của Hana"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"message": f"{settings.app_name} API is running. Frontend not found."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
