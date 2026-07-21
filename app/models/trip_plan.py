"""
TripPlan – Data Contract chuẩn hóa cho kế hoạch chuyến đi

Đây là schema trung tâm của hệ thống:
- Planner node tạo ra TripPlan từ yêu cầu của người dùng
- Executor nodes dùng TripPlan để biết cần tìm thông tin gì
- Frontend hiển thị TripPlan để người dùng xác nhận/chỉnh sửa

Nguyên tắc: KHÔNG truyền raw API responses vào LLM reasoning.
Tất cả dữ liệu từ bên ngoài phải được normalize qua schema này trước.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────


class TripType(str, Enum):
    """Loại hình chuyến đi"""
    SOLO       = "solo"        # Du lịch một mình
    COUPLE     = "couple"      # Cặp đôi
    FAMILY     = "family"      # Gia đình
    FRIENDS    = "friends"     # Nhóm bạn
    BUSINESS   = "business"    # Công tác


class ComfortLevel(str, Enum):
    """Mức độ thoải mái / chuẩn dịch vụ mong muốn"""
    BUDGET    = "budget"    # Tiết kiệm tối đa (hostel, xe khách)
    MEDIUM    = "medium"    # Tầm trung (khách sạn 3 sao, xe đặt)
    COMFORT   = "comfort"   # Thoải mái (khách sạn 4 sao, bay)
    LUXURY    = "luxury"    # Cao cấp (5 sao, business class)


class TripStatus(str, Enum):
    """Trạng thái của kế hoạch trong luồng xử lý"""
    DRAFT      = "draft"       # AI vừa tạo, chưa xác nhận
    CONFIRMED  = "confirmed"   # Người dùng đã xác nhận → bắt đầu tìm kiếm
    SEARCHING  = "searching"   # Đang gọi provider APIs
    COMPLETED  = "completed"   # Có đủ thông tin, sẵn sàng trả về
    FAILED     = "failed"      # Xảy ra lỗi trong quá trình xử lý


# ── Sub-schemas ────────────────────────────────────────────


class DateRange(BaseModel):
    """Khoảng thời gian của chuyến đi"""
    departure: Optional[str] = Field(
        default=None,
        description="Ngày khởi hành (YYYY-MM-DD). None nếu chưa xác định.",
        examples=["2026-08-10"],
    )
    return_date: Optional[str] = Field(
        default=None,
        description="Ngày về (YYYY-MM-DD). None nếu chưa xác định.",
        examples=["2026-08-14"],
    )
    days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Số ngày chuyến đi (có thể infer từ departure/return_date).",
    )
    nights: Optional[int] = Field(
        default=None,
        ge=0,
        le=364,
        description="Số đêm cần ở khách sạn (thường = days - 1).",
    )

    def infer_days(self) -> Optional[int]:
        """Tính số ngày từ departure và return_date nếu đủ thông tin."""
        if self.departure and self.return_date:
            from datetime import date
            try:
                d1 = date.fromisoformat(self.departure)
                d2 = date.fromisoformat(self.return_date)
                return max((d2 - d1).days, 1)
            except ValueError:
                return self.days
        return self.days


class Budget(BaseModel):
    """Thông tin ngân sách chuyến đi"""
    total: Optional[float] = Field(
        default=None,
        ge=0,
        description="Tổng ngân sách (theo currency). None nếu chưa xác định.",
        examples=[10_000_000],
    )
    per_person: Optional[float] = Field(
        default=None,
        ge=0,
        description="Ngân sách trên mỗi người. None nếu chưa xác định.",
        examples=[5_000_000],
    )
    currency: str = Field(
        default="VND",
        description="Đơn vị tiền tệ.",
        examples=["VND", "USD"],
    )

    def calculate_per_person(self, travelers: int) -> Optional[float]:
        """Tính ngân sách mỗi người từ tổng nếu chưa có."""
        if self.per_person:
            return self.per_person
        if self.total and travelers > 0:
            return self.total / travelers
        return None


# ── Main TripPlan Schema ───────────────────────────────────


class TripPlan(BaseModel):
    """
    Kế hoạch chuyến đi chuẩn hóa – Data Contract trung tâm.

    AI Planner tạo ra TripPlan từ yêu cầu ngôn ngữ tự nhiên.
    Người dùng có thể xem, chỉnh sửa, và xác nhận trước khi
    hệ thống bắt đầu tìm kiếm chuyến bay, khách sạn, thời tiết...

    Chỉ các field có giá trị mới được trả về frontend (exclude_none=True).
    """

    # ── Điểm đến ──────────────────────────────────────────
    origin: Optional[str] = Field(
        default=None,
        description="Điểm khởi hành (thành phố hoặc sân bay).",
        examples=["Hà Nội", "Hồ Chí Minh"],
    )
    destination: str = Field(
        description="Điểm đến chính của chuyến đi.",
        examples=["Đà Nẵng", "Phú Quốc", "Bangkok"],
    )

    # ── Thời gian ──────────────────────────────────────────
    dates: DateRange = Field(
        default_factory=DateRange,
        description="Thông tin ngày đi/về và số ngày.",
    )

    # ── Người đi ───────────────────────────────────────────
    travelers: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Tổng số người đi.",
    )
    trip_type: TripType = Field(
        default=TripType.SOLO,
        description="Loại hình chuyến đi.",
    )

    # ── Tài chính ──────────────────────────────────────────
    budget: Budget = Field(
        default_factory=Budget,
        description="Thông tin ngân sách.",
    )

    # ── Sở thích và yêu cầu ────────────────────────────────
    comfort_level: ComfortLevel = Field(
        default=ComfortLevel.MEDIUM,
        description="Mức độ thoải mái mong muốn.",
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="Danh sách sở thích, phong cách du lịch.",
        examples=[["biển", "ăn hải sản", "không quá bận rộn"]],
    )
    must_have: List[str] = Field(
        default_factory=list,
        description="Các điều bắt buộc phải có trong chuyến đi.",
        examples=[["tắm biển", "check-in Cầu Vàng"]],
    )
    avoid: List[str] = Field(
        default_factory=list,
        description="Các điều muốn tránh.",
        examples=[["leo núi nhiều", "ăn đồ cay"]],
    )
    special_requirements: List[str] = Field(
        default_factory=list,
        description="Yêu cầu đặc biệt (dị ứng, di chuyển khó khăn, trẻ nhỏ...).",
        examples=[["có trẻ em 3 tuổi", "cần phòng không hút thuốc"]],
    )

    # ── Luồng thực thi ────────────────────────────────────
    steps: List[str] = Field(
        default_factory=list,
        description="Các bước tìm kiếm cần thực hiện theo thứ tự.",
        examples=[["find_flights", "find_hotels", "check_weather", "estimate_costs"]],
    )
    status: TripStatus = Field(
        default=TripStatus.DRAFT,
        description="Trạng thái xử lý hiện tại của kế hoạch.",
    )

    # ── Metadata ───────────────────────────────────────────
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Độ tin cậy của AI khi extract thông tin từ hội thoại. "
            "1.0 = chắc chắn hoàn toàn, 0.0 = không chắc chắn."
        ),
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Các trường quan trọng còn thiếu, cần hỏi thêm người dùng.",
        examples=[["budget.total", "dates.departure"]],
    )

    # ── Helpers ────────────────────────────────────────────
    def is_ready_to_search(self) -> bool:
        """
        Kiểm tra xem TripPlan đã đủ thông tin để bắt đầu tìm kiếm chưa.
        Tối thiểu cần: destination, days (hoặc dates), travelers.
        """
        has_destination = bool(self.destination)
        has_time = bool(self.dates.days or self.dates.departure)
        has_travelers = self.travelers > 0
        return has_destination and has_time and has_travelers

    def to_summary(self) -> str:
        """Tóm tắt kế hoạch thành chuỗi văn bản ngắn gọn cho AI đọc."""
        parts = [f"Điểm đến: {self.destination}"]
        if self.origin:
            parts.append(f"Từ: {self.origin}")
        if self.dates.days:
            parts.append(f"Thời gian: {self.dates.days} ngày")
        if self.dates.departure:
            parts.append(f"Ngày đi: {self.dates.departure}")
        # trip_type có thể là enum hoặc str (do use_enum_values=True)
        trip_type_val = self.trip_type if isinstance(self.trip_type, str) else self.trip_type.value
        parts.append(f"Số người: {self.travelers} ({trip_type_val})")
        if self.budget.total:
            parts.append(
                f"Ngân sách: {self.budget.total:,.0f} {self.budget.currency}"
            )
        if self.preferences:
            parts.append(f"Sở thích: {', '.join(self.preferences)}")
        # comfort_level tương tự
        comfort_val = self.comfort_level if isinstance(self.comfort_level, str) else self.comfort_level.value
        parts.append(f"Mức độ thoải mái: {comfort_val}")
        return " | ".join(parts)

    model_config = {"use_enum_values": True}
