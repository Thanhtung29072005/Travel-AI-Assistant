"""
Search Service - Đóng gói logic tìm kiếm web với Tavily

Lý do tách thành service riêng (thay vì gọi Tavily trực tiếp trong tool):
- Dễ mock khi test (không cần gọi API thật)
- Dễ thay thế backend tìm kiếm (Tavily → SerpAPI → ...)
- Xử lý lỗi và fallback tập trung một chỗ
- Cache kết quả tránh gọi API trùng lặp
"""
import hashlib
from functools import lru_cache
from typing import Optional

from app.config import get_settings

settings = get_settings()


class SearchResult:
    """Kết quả tìm kiếm chuẩn hóa"""
    def __init__(self, answer: str, sources: list[dict], query: str):
        self.answer = answer      # Tóm tắt câu trả lời
        self.sources = sources    # List {title, url, content}
        self.query = query        # Query gốc

    def to_text(self) -> str:
        """Chuyển kết quả thành chuỗi văn bản cho LLM đọc"""
        parts = []
        if self.answer:
            parts.append(f"Tóm tắt: {self.answer}\n")
        for i, src in enumerate(self.sources[:3], 1):
            parts.append(f"{i}. {src.get('title', 'N/A')}")
            content = src.get('content', '')[:300]
            if content:
                parts.append(f"   {content}...")
            url = src.get('url', '')
            if url:
                parts.append(f"   Nguồn: {url}\n")
        return "\n".join(parts) if parts else "Không tìm thấy thông tin."


class SearchService:
    """
    Service tìm kiếm web dùng Tavily API.
    Tự động fallback về thông báo lỗi nếu API key không hợp lệ.
    """

    def __init__(self):
        self._client = None
        self._enabled = bool(settings.tavily_api_key)

    def _get_client(self):
        """Lazy initialization của Tavily client"""
        if self._client is None:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=settings.tavily_api_key)
        return self._client

    def search(self, query: str, max_results: int = 5) -> SearchResult:
        """
        Tìm kiếm thông tin trên internet.

        Args:
            query: Câu hỏi cần tìm kiếm
            max_results: Số kết quả tối đa trả về (mặc định 5)

        Returns:
            SearchResult với câu trả lời tóm tắt và danh sách nguồn
        """
        if not self._enabled:
            return SearchResult(
                answer="Chức năng tìm kiếm web chưa được cấu hình. "
                       "Hãy thêm TAVILY_API_KEY vào file .env.",
                sources=[],
                query=query,
            )

        try:
            client = self._get_client()
            raw = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=True,
            )
            return SearchResult(
                answer=raw.get("answer", ""),
                sources=raw.get("results", []),
                query=query,
            )
        except Exception as e:
            return SearchResult(
                answer=f"Không thể tìm kiếm lúc này: {str(e)[:100]}",
                sources=[],
                query=query,
            )

    @property
    def is_enabled(self) -> bool:
        """Kiểm tra Tavily đã được cấu hình chưa"""
        return self._enabled


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Lấy SearchService instance (singleton)"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
