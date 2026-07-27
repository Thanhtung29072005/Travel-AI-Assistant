"""
Cost Calculator & Decision Engine

Ước tính chi phí thực tế và phát hiện rủi ro cho TripPlan.

Design:
- Không gọi LLM, không gọi external API
- Dùng dữ liệu tham khảo offline được cập nhật thủ công theo quý
- Kết quả normalize thành CostEstimate để LLM đọc dễ dàng
- Phát hiện 4 loại rủi ro: ngân sách, lịch trình, thời tiết, mùa vụ

Nguồn giá tham khảo (Q3/2026): khảo sát thực tế + Booking.com + agoda
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "low"    # Không đáng lo ngại
    MEDIUM = "medium" # Cần lưu ý
    HIGH   = "high"   # Cần cân nhắc kỹ hoặc thay đổi kế hoạch


# ── Data schemas ───────────────────────────────────────────────────────────────

@dataclass
class CostBreakdown:
    """Chi tiết ước tính từng khoản chi"""
    flight_per_person: float       # VND
    accommodation_per_night: float # VND (tổng, không phải/người)
    food_per_person_per_day: float # VND
    transport_local_total: float   # VND (taxi, Grab, xe máy thuê)
    activities_total: float        # VND (vé vào cổng, tour, v.v.)
    misc_buffer: float             # VND (10% dự phòng)


@dataclass
class CostEstimate:
    """Kết quả ước tính chi phí chuẩn hóa"""
    destination: str
    travelers: int
    days: int
    comfort_level: str

    breakdown: CostBreakdown

    total_per_person: float        # VND
    total_all_people: float        # VND
    budget_provided: float         # VND (từ TripPlan, 0 nếu không có)
    budget_gap: float              # VND (+= thừa, -= thiếu)
    currency: str = "VND"
    disclaimer: str = "Giá mang tính tham khảo, cập nhật Q3/2026"

    def to_text(self) -> str:
        b = self.breakdown
        gap_note = ""
        if self.budget_provided > 0:
            if self.budget_gap >= 0:
                gap_note = f"\n✅ Ngân sách dư ~{self.budget_gap/1_000_000:.1f} triệu"
            else:
                gap_note = f"\n⚠️ Ngân sách thiếu ~{abs(self.budget_gap)/1_000_000:.1f} triệu"

        return (
            f"Ước tính chi phí {self.destination} ({self.days} ngày, "
            f"{self.travelers} người, chuẩn {self.comfort_level}):\n"
            f"  • Vé máy bay:      {b.flight_per_person/1_000_000:.1f}tr/người\n"
            f"  • Khách sạn:       {b.accommodation_per_night/1_000_000:.1f}tr/đêm\n"
            f"  • Ăn uống:         {b.food_per_person_per_day/1_000:.0f}k/người/ngày\n"
            f"  • Đi lại nội địa:  {b.transport_local_total/1_000_000:.1f}tr (tổng)\n"
            f"  • Tham quan/vui:   {b.activities_total/1_000_000:.1f}tr (tổng)\n"
            f"  • Dự phòng 10%:    {b.misc_buffer/1_000_000:.1f}tr\n"
            f"─────────────────────────────\n"
            f"  Tổng/người:   {self.total_per_person/1_000_000:.1f} triệu VND\n"
            f"  Tổng {self.travelers} người: {self.total_all_people/1_000_000:.1f} triệu VND"
            f"{gap_note}\n"
            f"({self.disclaimer})"
        )


@dataclass
class RiskItem:
    """Một mục rủi ro trong chuyến đi"""
    category: str       # "budget" | "schedule" | "weather" | "season"
    level: RiskLevel
    title: str
    detail: str
    suggestion: str     # Gợi ý cụ thể để giảm thiểu rủi ro


@dataclass
class DecisionReport:
    """Báo cáo tổng hợp từ Decision Engine"""
    cost_estimate: CostEstimate
    risks: list[RiskItem]
    overall_risk: RiskLevel
    recommendation: str     # Tóm tắt khuyến nghị

    def to_text(self) -> str:
        lines = [self.cost_estimate.to_text(), ""]

        if self.risks:
            lines.append("⚡ Rủi ro phát hiện:")
            for r in self.risks:
                icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(r.level, "⚪")
                lines.append(f"  {icon} [{r.category.upper()}] {r.title}")
                lines.append(f"     {r.detail}")
                lines.append(f"     💡 {r.suggestion}")
        else:
            lines.append("✅ Không phát hiện rủi ro đáng lo ngại")

        lines.append(f"\n📋 Đánh giá tổng thể: {self.overall_risk.upper()}")
        lines.append(f"💬 {self.recommendation}")
        return "\n".join(lines)


# ── Price Database (offline, tham khảo Q3/2026) ───────────────────────────────

# Chi phí vé máy bay (VND, khứ hồi/người) theo điểm đến và điểm xuất phát mặc định
# Key: destination (normalized lowercase)
_FLIGHT_COSTS: dict[str, dict[str, float]] = {
    # Từ Hà Nội
    "da nang":    {"hn": 1_500_000, "hcm": 1_200_000, "default": 1_600_000},
    "ho chi minh": {"hn": 1_200_000, "default": 1_200_000},
    "phu quoc":   {"hn": 2_200_000, "hcm": 1_500_000, "default": 2_000_000},
    "nha trang":  {"hn": 1_800_000, "hcm": 1_200_000, "default": 1_600_000},
    "hoi an":     {"hn": 1_500_000, "hcm": 1_200_000, "default": 1_500_000},
    "ha long":    {"hcm": 1_800_000, "default": 500_000},     # từ HN gần, đi xe
    "ha noi":     {"hcm": 1_400_000, "default": 1_400_000},
    "da lat":     {"hn": 1_600_000, "hcm": 900_000,  "default": 1_400_000},
    "sapa":       {"hcm": 1_800_000, "default": 400_000},     # từ HN đi xe/tàu
    # Quốc tế phổ biến (VND)
    "bangkok":    {"default": 3_500_000},
    "singapore":  {"default": 4_500_000},
    "tokyo":      {"default": 9_000_000},
    "seoul":      {"default": 7_000_000},
    "paris":      {"default": 18_000_000},
}

# Chi phí khách sạn (VND/đêm, 1 phòng đôi) theo mức comfort
_HOTEL_COSTS: dict[str, dict[str, float]] = {
    "budget":  {"default": 250_000,  "phu quoc": 400_000,  "tokyo": 800_000, "paris": 1_500_000},
    "medium":  {"default": 700_000,  "phu quoc": 1_200_000, "tokyo": 2_000_000, "paris": 3_500_000},
    "comfort": {"default": 1_500_000,"phu quoc": 2_500_000, "tokyo": 4_000_000, "paris": 7_000_000},
    "luxury":  {"default": 4_000_000,"phu quoc": 7_000_000, "tokyo": 12_000_000,"paris": 20_000_000},
}

# Chi phí ăn uống (VND/người/ngày) theo mức comfort
_FOOD_COSTS: dict[str, float] = {
    "budget":  200_000,
    "medium":  400_000,
    "comfort": 700_000,
    "luxury":  1_500_000,
}

# Chi phí đi lại nội địa (VND, tổng chuyến, chia đầu người sau)
_TRANSPORT_COSTS: dict[str, dict[str, float]] = {
    "budget":  {"default": 300_000},
    "medium":  {"default": 500_000},
    "comfort": {"default": 800_000},
    "luxury":  {"default": 1_500_000},
}

# Chi phí tham quan (VND, tổng chuyến)
_ACTIVITIES_COSTS: dict[str, dict[str, float]] = {
    "budget":  {"default": 200_000,  "phu quoc": 400_000},
    "medium":  {"default": 500_000,  "phu quoc": 800_000,  "tokyo": 2_000_000},
    "comfort": {"default": 1_000_000,"phu quoc": 1_500_000,"tokyo": 3_500_000},
    "luxury":  {"default": 2_500_000,"phu quoc": 4_000_000,"tokyo": 8_000_000},
}

# Mùa du lịch (peak = đắt + đông) theo điểm đến
_PEAK_SEASONS: dict[str, list[int]] = {
    "phu quoc":    [11, 12, 1, 2, 3],
    "da nang":     [6, 7, 8],
    "ha long":     [5, 6, 7, 8],
    "hoi an":      [2, 3, 4, 5, 6, 7],
    "da lat":      [12, 1, 2, 7, 8],
    "ha noi":      [10, 11, 3, 4],
    "ho chi minh": [12, 1, 2],
    "nha trang":   [7, 8],
    "sapa":        [9, 10],
    "bangkok":     [11, 12, 1, 2, 3],
    "tokyo":       [3, 4, 10, 11],
}

# Off-season (giảm giá + ít khách nhưng thời tiết xấu hơn)
_OFF_SEASONS: dict[str, list[int]] = {
    "phu quoc":    [7, 8, 9],  # mùa mưa
    "da nang":     [10, 11, 12],
    "ha long":     [1, 2],
    "hoi an":      [10, 11, 12],
    "nha trang":   [10, 11, 12],
}


# ── Helper functions ───────────────────────────────────────────────────────────

def _lookup(table: dict[str, float], dest: str, fallback_key: str = "default") -> float:
    """Tra cứu giá theo điểm đến, fallback về default."""
    normalized = dest.lower().strip()
    # Tìm key match (partial match)
    for key in table:
        if key in normalized or normalized in key:
            return table.get(key, table.get(fallback_key, 0))
    return table.get(fallback_key, 0)


def _lookup_nested(table: dict[str, dict[str, float]], comfort: str, dest: str) -> float:
    comfort_table = table.get(comfort, table.get("medium", {}))
    return _lookup(comfort_table, dest)


# ── Core Calculator ────────────────────────────────────────────────────────────

class TripCostCalculator:
    """
    Ước tính chi phí chuyến đi từ TripPlan.
    Không cần internet, không gọi API.
    """

    def estimate(
        self,
        destination: str,
        days: int,
        travelers: int,
        comfort_level: str = "medium",
        budget_provided: float = 0.0,
        nights: Optional[int] = None,
        origin: Optional[str] = None,
        has_flight: bool = True,
        flight_options: Optional[list] = None,
        hotel_options: Optional[list] = None,
    ) -> CostEstimate:
        """
        Ước tính chi phí dựa trên TripPlan fields và tùy chọn thực tế từ Gateway.
        """
        nights = nights if nights is not None else max(days - 1, 1)
        dest_key = destination.lower().strip()
        comfort = comfort_level if comfort_level in _HOTEL_COSTS else "medium"

        # --- Vé máy bay ---
        flight_cost_pp = 0.0
        if has_flight:
            if flight_options:
                # Lấy trung bình cộng từ các vé thực tế tìm thấy
                prices = [f.price for f in flight_options if f.price > 0]
                if prices:
                    flight_cost_pp = sum(prices) / len(prices)
            
            if not flight_cost_pp:
                flight_table = _FLIGHT_COSTS.get(
                    next((k for k in _FLIGHT_COSTS if k in dest_key), None),
                    {"default": 2_000_000}
                )
                origin_key = (origin or "").lower().strip()
                if "hà nội" in origin_key or "hanoi" in origin_key or "hn" in origin_key:
                    flight_cost_pp = flight_table.get("hn", flight_table["default"])
                elif "hồ chí minh" in origin_key or "hcm" in origin_key or "saigon" in origin_key:
                    flight_cost_pp = flight_table.get("hcm", flight_table["default"])
                else:
                    flight_cost_pp = flight_table["default"]

        # --- Khách sạn ---
        hotel_night = 0.0
        if hotel_options:
            # Lấy trung bình cộng từ các khách sạn thực tế tìm thấy
            prices = [h.price_per_night for h in hotel_options if h.price_per_night > 0]
            if prices:
                hotel_night = sum(prices) / len(prices)

        if not hotel_night:
            hotel_table = _HOTEL_COSTS.get(comfort, _HOTEL_COSTS["medium"])
            hotel_night = _lookup(hotel_table, dest_key)

        # Điều chỉnh nếu >2 người cùng phòng (chia đôi giá phòng)
        rooms_needed = max(1, travelers // 2)
        hotel_total = hotel_night * nights * rooms_needed

        # --- Ăn uống ---
        food_ppd = _FOOD_COSTS.get(comfort, _FOOD_COSTS["medium"])

        # --- Di chuyển nội địa ---
        transport_ppd = _lookup_nested(_TRANSPORT_COSTS, comfort, dest_key)
        transport_total = transport_ppd * days

        # --- Tham quan ---
        activities_ppd = _lookup_nested(_ACTIVITIES_COSTS, comfort, dest_key)
        activities_total = activities_ppd * days

        # --- Tổng ---
        subtotal_pp = (
            flight_cost_pp
            + hotel_total / travelers
            + food_ppd * days
            + transport_total / travelers
            + activities_total / travelers
        )
        buffer = subtotal_pp * 0.10  # 10% dự phòng
        total_pp = subtotal_pp + buffer
        total_all = total_pp * travelers
        budget_gap = budget_provided - total_all if budget_provided > 0 else 0.0

        breakdown = CostBreakdown(
            flight_per_person=flight_cost_pp,
            accommodation_per_night=hotel_night,
            food_per_person_per_day=food_ppd,
            transport_local_total=transport_total,
            activities_total=activities_total,
            misc_buffer=buffer * travelers,
        )

        return CostEstimate(
            destination=destination,
            travelers=travelers,
            days=days,
            comfort_level=comfort,
            breakdown=breakdown,
            total_per_person=total_pp,
            total_all_people=total_all,
            budget_provided=budget_provided,
            budget_gap=budget_gap,
        )


class RiskAnalyzer:
    """
    Phân tích rủi ro cho chuyến đi.
    Kiểm tra 4 loại: ngân sách, lịch trình, thời tiết, mùa vụ.
    """

    def analyze(
        self,
        destination: str,
        days: int,
        travelers: int,
        cost_estimate: CostEstimate,
        departure_month: Optional[int] = None,
        weather_warning: str = "",
    ) -> list[RiskItem]:
        """
        Phân tích rủi ro từ dữ liệu chuyến đi.

        Returns:
            Danh sách các RiskItem, sắp xếp theo level (HIGH → LOW)
        """
        risks = []

        # 1. Rủi ro ngân sách
        if cost_estimate.budget_provided > 0:
            gap = cost_estimate.budget_gap
            if gap < -cost_estimate.total_all_people * 0.10:
                risks.append(RiskItem(
                    category="budget",
                    level=RiskLevel.HIGH,
                    title="Ngân sách không đủ",
                    detail=f"Thiếu ~{abs(gap)/1_000_000:.1f} triệu VND ({abs(gap)/cost_estimate.total_all_people*100:.0f}%)",
                    suggestion=(
                        "Giảm số đêm khách sạn, chọn mức comfort thấp hơn, "
                        "hoặc tăng ngân sách thêm ~{:.0f}k/người".format(abs(gap)/travelers/1000)
                    ),
                ))
            elif gap < 0:
                risks.append(RiskItem(
                    category="budget",
                    level=RiskLevel.MEDIUM,
                    title="Ngân sách hơi ít",
                    detail=f"Thiếu nhẹ ~{abs(gap)/1_000_000:.1f} triệu — chưa tính phát sinh",
                    suggestion="Dự trù thêm 10-15% cho chi phí phát sinh (quà, thuốc, v.v.)",
                ))

        # 2. Rủi ro lịch trình quá dày
        if days <= 2 and len(destination) > 0:
            risks.append(RiskItem(
                category="schedule",
                level=RiskLevel.MEDIUM,
                title="Lịch trình ngắn",
                detail=f"Chỉ {days} ngày có thể không đủ để trải nghiệm {destination}",
                suggestion=f"Nên ít nhất 3-4 ngày để tránh cảm giác vội vàng",
            ))

        # 3. Rủi ro thời tiết (từ WeatherService)
        if weather_warning:
            level = RiskLevel.HIGH if "lớn" in weather_warning or "bão" in weather_warning else RiskLevel.MEDIUM
            risks.append(RiskItem(
                category="weather",
                level=level,
                title="Thời tiết xấu dự kiến",
                detail=weather_warning,
                suggestion="Chuẩn bị áo mưa, plan B cho các hoạt động ngoài trời",
            ))

        # 4. Rủi ro mùa vụ (đắt + đông)
        if departure_month:
            dest_key = destination.lower().strip()
            peak_key = next((k for k in _PEAK_SEASONS if k in dest_key), None)
            off_key = next((k for k in _OFF_SEASONS if k in dest_key), None)

            if peak_key and departure_month in _PEAK_SEASONS[peak_key]:
                risks.append(RiskItem(
                    category="season",
                    level=RiskLevel.MEDIUM,
                    title="Mùa cao điểm",
                    detail=f"Tháng {departure_month} là peak season tại {destination} — giá cao hơn 20-40%",
                    suggestion="Đặt khách sạn và vé sớm ít nhất 4-6 tuần trước",
                ))
            elif off_key and departure_month in _OFF_SEASONS[off_key]:
                risks.append(RiskItem(
                    category="season",
                    level=RiskLevel.LOW,
                    title="Mùa thấp điểm",
                    detail=f"Tháng {departure_month} là off-season — giá rẻ hơn nhưng thời tiết có thể xấu hơn",
                    suggestion="Kiểm tra dự báo thời tiết trước khi đi",
                ))

        # Sắp xếp HIGH → MEDIUM → LOW
        order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
        risks.sort(key=lambda r: order[r.level])
        return risks


class DecisionEngine:
    """
    Engine tổng hợp: kết hợp cost estimation + risk analysis
    để tạo báo cáo DecisionReport đầy đủ.
    """

    def __init__(self):
        self._calculator = TripCostCalculator()
        self._analyzer = RiskAnalyzer()

    def evaluate(
        self,
        destination: str,
        days: int,
        travelers: int,
        comfort_level: str = "medium",
        budget_provided: float = 0.0,
        nights: Optional[int] = None,
        origin: Optional[str] = None,
        departure_month: Optional[int] = None,
        weather_warning: str = "",
        flight_options: Optional[list] = None,
        hotel_options: Optional[list] = None,
    ) -> DecisionReport:
        """
        Chạy full evaluation cho một chuyến đi.

        Returns:
            DecisionReport với cost estimate + danh sách risk items
        """
        cost = self._calculator.estimate(
            destination=destination,
            days=days,
            travelers=travelers,
            comfort_level=comfort_level,
            budget_provided=budget_provided,
            nights=nights,
            origin=origin,
            flight_options=flight_options,
            hotel_options=hotel_options,
        )

        risks = self._analyzer.analyze(
            destination=destination,
            days=days,
            travelers=travelers,
            cost_estimate=cost,
            departure_month=departure_month,
            weather_warning=weather_warning,
        )

        # Xác định overall risk level
        if any(r.level == RiskLevel.HIGH for r in risks):
            overall = RiskLevel.HIGH
        elif any(r.level == RiskLevel.MEDIUM for r in risks):
            overall = RiskLevel.MEDIUM
        else:
            overall = RiskLevel.LOW

        # Tạo khuyến nghị tổng thể
        if overall == RiskLevel.HIGH:
            recommendation = (
                "Cần điều chỉnh kế hoạch trước khi tiến hành booking. "
                "Xem chi tiết rủi ro và gợi ý bên trên."
            )
        elif overall == RiskLevel.MEDIUM:
            recommendation = (
                "Kế hoạch khả thi nhưng cần lưu ý một số điểm. "
                "Nên giải quyết các rủi ro MEDIUM trước khi đặt."
            )
        else:
            recommendation = (
                "Kế hoạch ổn định! Có thể tiến hành booking. "
                "Nhớ đặt sớm để có giá tốt nhất."
            )

        return DecisionReport(
            cost_estimate=cost,
            risks=risks,
            overall_risk=overall,
            recommendation=recommendation,
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Lấy DecisionEngine instance (singleton)."""
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine
