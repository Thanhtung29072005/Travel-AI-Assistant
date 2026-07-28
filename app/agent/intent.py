"""
Intent Classifier - Nhận diện ý định của người dùng

Dùng heuristic (không gọi LLM) để phân loại intent từ tin nhắn.
Nhanh, không tốn API quota, và đủ chính xác cho 80% trường hợp.

Intent types:
  plan_trip   – Muốn lên kế hoạch / lịch trình chuyến đi
  ask_weather – Hỏi thời tiết tại điểm đến
  ask_info    – Hỏi thông tin cụ thể (địa điểm, giá vé, giờ mở cửa)
  general     – Câu hỏi chung, không liên quan đến lập kế hoạch
"""
from __future__ import annotations

import re
from typing import Literal

IntentType = Literal["plan_trip", "ask_weather", "ask_info", "out_of_scope", "general"]


# ── Keyword sets (chuẩn hóa lowercase, không dấu kết hợp với có dấu) ──────────

_OUT_OF_SCOPE_KEYWORDS = [
    "viet code", "code python", "lap trinh", "viet ham", "thuat toan", "html/css", "javascript", "viet script",
    "giai toan", "bai tap ve nha", "phuong trinh", "benh an", "thuoc tri", "tu van luat", "hien phap", "chinh tri",
    "viet code", "lập trình", "viết hàm", "thuật toán", "giải toán", "bài tập về nhà", "phương trình"
]

_PLAN_KEYWORDS = [
    # Yêu cầu lập kế hoạch / đặt lịch
    "len ke hoach", "lap ke hoach", "ke hoach du lich",
    "lich trinh", "lich di", "lich chuyen", "lich trinh chi tiet",
    "goi y lich", "de xuat lich",
    # Chuyến đi
    "di du lich", "chuyen di", "chuyen du lich", "di choi",
    "muon di", "du dinh di", "co the di",
    "di phuot", "du lich bui", "kham pha",
    # Ngân sách / chi phí
    "ngan sach", "budget", "bao nhieu tien", "chi phi chuyen",
    "ton bao nhieu", "du tru",
    # Nhóm đi
    "cap doi", "gia dinh", "nhom ban", "di mot minh", "solo",
    # Đặt phòng / vé
    "khach san", "nha nghi", "resort", "villa", "homestay",
    "ve may bay", "chuyen bay", "book ve", "dat phong",
    # Số ngày
    "ngay", "dem", "tuan",
]

_WEATHER_KEYWORDS = [
    "thoi tiet", "nhiet do", "du bao thoi tiet",
    "troi mua", "troi nang", "gio lon", "co gio manh", "bao nhiet doi", "lanh lam", "nong buc",
    "mua mua", "mua kho", "mua he", "mua dong",
    "co mua khong", "troi dep khong", "khi hau",
]

_INFO_KEYWORDS = [
    # Giờ giấc / địa điểm
    "gio mo cua", "dia chi", "o dau", "cach di",
    "gia ve vao", "ve vao cua", "bao nhieu", "phi",
    "dac san", "an gi ngon", "quan an", "nha hang",
    "nen di dau", "co gi hay", "diem tham quan",
    "review", "danh gia", "kinh nghiem",
]


import unicodedata


def _remove_accents(text: str) -> str:
    """
    Loại bỏ dấu tiếng Việt dùng unicodedata (stdlib, không cần thư viện ngoài).
    Xử lý đúng tất cả ký tự có dấu của tiếng Việt.
    """
    nfd = unicodedata.normalize("NFD", text)
    # Loại bỏ combining diacritical marks (category Mn)
    # Riêng 'đ'/'Đ' không phân rã qua NFD nên phải xử lý thủ công
    result = "".join(
        c for c in nfd
        if unicodedata.category(c) != "Mn"
    )
    # Chuyển đ → d, Đ → D
    result = result.replace("đ", "d").replace("Đ", "D")
    return result


def _normalize(text: str) -> str:
    """Lowercase, loại bỏ accent để matching."""
    return _remove_accents(text).lower().strip()


def classify_intent(message: str) -> IntentType:
    """
    Phân loại intent từ tin nhắn người dùng dựa trên keyword matching.

    Ưu tiên (priority order):
      1. plan_trip   – intent cốt lõi, cần pipeline đầy đủ nhất
      2. ask_weather – intent đơn lẻ phổ biến
      3. ask_info    – intent đơn lẻ phổ biến
      4. general     – fallback

    Args:
        message: Tin nhắn nguyên bản của người dùng

    Returns:
        IntentType string
    """
    normalized = _normalize(message)

    # Kiểm tra ngoài phạm vi (Ưu tiên cao nhất)
    out_of_scope_score = sum(1 for kw in _OUT_OF_SCOPE_KEYWORDS if kw in normalized)
    if out_of_scope_score >= 1:
        return "out_of_scope"

    # Đếm hits cho từng nhóm
    plan_score = sum(1 for kw in _PLAN_KEYWORDS if kw in normalized)
    weather_score = sum(1 for kw in _WEATHER_KEYWORDS if kw in normalized)
    info_score = sum(1 for kw in _INFO_KEYWORDS if kw in normalized)

    # Heuristic bổ sung: câu có điểm đến + số ngày → rất có khả năng plan_trip
    has_destination_hint = bool(
        re.search(r"\d+\s*(ngày|đêm|tuần)", normalized)
    )
    if has_destination_hint:
        plan_score += 2

    # Quyết định theo priority + score
    if plan_score >= 1:
        return "plan_trip"
    if weather_score >= 1:
        return "ask_weather"
    if info_score >= 1:
        return "ask_info"
    return "general"


def needs_trip_plan(intent: IntentType) -> bool:
    """
    Trả về True nếu intent cần đi qua planner_node để tạo/cập nhật TripPlan.
    """
    return intent == "plan_trip"
