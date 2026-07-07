# ✈️ Travel AI Assistant

Trợ lý du lịch thông minh được xây dựng với **LangGraph + Google Gemini + FastAPI**.

## Tính năng

- 🔍 Tìm kiếm khách sạn, vé máy bay
- 📅 Lên lịch trình du lịch theo ngày
- 🗺️ Gợi ý địa điểm, nhà hàng, hoạt động
- 💰 Tính toán ngân sách du lịch

## Kiến trúc

```
travel-ai-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py         # LangGraph workflow
│   │   ├── nodes.py         # Graph nodes (AI logic)
│   │   ├── state.py         # Agent state schema
│   │   └── tools.py         # Tool definitions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini.py        # Google Gemini client
│   │   └── search.py        # Web search service
│   └── models/
│       ├── __init__.py
│       └── schemas.py       # Pydantic models
├── tests/
│   └── test_agent.py
├── .env.example
├── requirements.txt
└── README.md
```

## Cài đặt

```bash
# 1. Tạo môi trường ảo
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Cài đặt dependencies
pip install -r requirements.txt

# 3. Tạo file .env từ .env.example
copy .env.example .env
# Điền GOOGLE_API_KEY vào .env

# 4. Chạy server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/chat` | Gửi tin nhắn tới AI |
| GET  | `/api/health` | Kiểm tra trạng thái |

## Công nghệ

- **LangGraph** - Orchestration AI agent workflow
- **Google Gemini** - LLM (gemini-2.0-flash)
- **FastAPI** - API framework
- **Pydantic** - Data validation
- **Tavily** - Web search API
