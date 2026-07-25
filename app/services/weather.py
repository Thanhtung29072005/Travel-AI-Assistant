"""
Weather Service - Lấy dữ liệu thời tiết thực tế từ OpenWeatherMap

Design:
- Kết quả được normalize vào WeatherData schema trước khi trả về LLM
- Graceful fallback khi không có API key hoặc API lỗi
- Hỗ trợ tìm theo tên thành phố (tiếng Việt → geocoding → weather)

API doc: https://openweathermap.org/api/one-call-3
Free tier: 1,000 calls/day (current weather) — đủ cho MVP
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Data schema (normalized, không trả raw API về LLM) ────────────────────────

@dataclass
class DailyForecast:
    """Dự báo thời tiết 1 ngày"""
    date: str               # "2026-08-10"
    temp_min: float         # °C
    temp_max: float         # °C
    description: str        # "partly cloudy"
    precipitation_mm: float # mm mưa dự kiến
    humidity_pct: int       # % độ ẩm
    wind_kmh: float         # km/h tốc độ gió
    uv_index: float         # UV index (0-11+)
    icon: str               # emoji icon ☀️🌧️⛅

    def to_text(self) -> str:
        return (
            f"{self.date}: {self.icon} {self.description}, "
            f"{self.temp_min:.0f}–{self.temp_max:.0f}°C, "
            f"mưa {self.precipitation_mm:.0f}mm, "
            f"gió {self.wind_kmh:.0f}km/h, UV {self.uv_index:.0f}"
        )


@dataclass
class WeatherData:
    """Kết quả thời tiết chuẩn hóa"""
    city: str
    country: str
    timezone: str
    current_temp: float             # °C
    current_description: str
    current_humidity: int           # %
    forecast: list[DailyForecast]   # Tối đa 7 ngày
    travel_warning: str             # "" = không có cảnh báo
    source: str = "OpenWeatherMap"
    data_mode: str = "live"         # "live" | "fixture" | "missing"

    def to_text(self) -> str:
        """Serialize ra văn bản ngắn gọn cho LLM đọc"""
        lines = [
            f"Thời tiết tại {self.city}, {self.country}:",
            f"Hiện tại: {self.current_description}, {self.current_temp:.0f}°C, "
            f"độ ẩm {self.current_humidity}%",
        ]
        if self.travel_warning:
            lines.append(f"⚠️ Cảnh báo: {self.travel_warning}")
        if self.forecast:
            lines.append("\nDự báo 7 ngày:")
            for day in self.forecast:
                lines.append(f"  {day.to_text()}")
        lines.append(f"\n(Nguồn: {self.source}, chế độ: {self.data_mode})")
        return "\n".join(lines)


# ── Emoji mapping ──────────────────────────────────────────────────────────────

def _weather_icon(description: str, precipitation_mm: float = 0) -> str:
    desc = description.lower()
    if "thunderstorm" in desc:     return "⛈️"
    if "drizzle" in desc:          return "🌦️"
    if "rain" in desc or precipitation_mm > 5: return "🌧️"
    if "snow" in desc:             return "❄️"
    if "fog" in desc or "mist" in desc: return "🌫️"
    if "cloud" in desc:            return "⛅"
    if "clear" in desc:            return "☀️"
    return "🌤️"


# ── Travel risk assessment ─────────────────────────────────────────────────────

def _assess_travel_risk(forecast: list[DailyForecast]) -> str:
    """Phân tích rủi ro thời tiết từ forecast."""
    if not forecast:
        return ""

    heavy_rain_days = [d for d in forecast if d.precipitation_mm > 20]
    very_hot_days = [d for d in forecast if d.temp_max > 38]
    strong_wind_days = [d for d in forecast if d.wind_kmh > 50]
    high_uv_days = [d for d in forecast if d.uv_index >= 8]

    warnings = []
    if heavy_rain_days:
        days_str = ", ".join(d.date for d in heavy_rain_days[:3])
        warnings.append(f"Mưa lớn dự kiến ngày {days_str} (>20mm)")
    if very_hot_days:
        days_str = ", ".join(d.date for d in very_hot_days[:3])
        warnings.append(f"Nắng nóng >38°C ngày {days_str}")
    if strong_wind_days:
        days_str = ", ".join(d.date for d in strong_wind_days[:2])
        warnings.append(f"Gió mạnh >50km/h ngày {days_str}")
    if high_uv_days:
        warnings.append(f"Chỉ số UV cao (≥8) trong {len(high_uv_days)} ngày — cần kem chống nắng")

    return "; ".join(warnings)


# ── Weather Service ────────────────────────────────────────────────────────────

class WeatherService:
    """
    Service lấy thời tiết từ OpenWeatherMap.

    Free tier endpoint (không cần paid plan):
      GET api.openweathermap.org/data/2.5/forecast?q={city}&appid={key}&units=metric
    """

    OWM_BASE = "https://api.openweathermap.org/data/2.5"
    GEO_BASE = "https://api.openweathermap.org/geo/1.0"

    def __init__(self):
        self._api_key = getattr(settings, "openweathermap_api_key", "")
        self._enabled = bool(self._api_key)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def get_weather(
        self,
        city: str,
        days: int = 5,
    ) -> WeatherData:
        """
        Lấy thời tiết hiện tại + dự báo cho một thành phố.

        Args:
            city: Tên thành phố (tiếng Việt OK, API sẽ geocode)
            days: Số ngày dự báo (tối đa 5 với free tier)

        Returns:
            WeatherData đã normalize
        """
        if not self._enabled:
            return self._missing_data(city, reason="OPENWEATHERMAP_API_KEY chưa được cấu hình")

        try:
            import httpx
            return self._fetch_weather(city, min(days, 5))
        except ImportError:
            return self._missing_data(city, reason="httpx chưa được cài (pip install httpx)")
        except Exception as e:
            logger.warning("WeatherService error for %s: %s", city, e)
            return self._missing_data(city, reason=str(e)[:120])

    def _fetch_weather(self, city: str, days: int) -> WeatherData:
        """Gọi OWM API và parse kết quả."""
        import httpx

        with httpx.Client(timeout=10.0) as client:
            # 1. Lấy dữ liệu forecast (5 days / 3 hour steps)
            resp = client.get(
                f"{self.OWM_BASE}/forecast",
                params={
                    "q": city,
                    "appid": self._api_key,
                    "units": "metric",
                    "lang": "vi",
                    "cnt": days * 8,  # 8 bước/ngày (3 tiếng/bước)
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse current conditions từ bước đầu tiên
        first = data["list"][0]
        current_temp = first["main"]["temp"]
        current_desc = first["weather"][0]["description"]
        current_humidity = first["main"]["humidity"]
        city_name = data["city"]["name"]
        country = data["city"]["country"]
        timezone_offset = data["city"].get("timezone", 0)

        # Aggregate forecast theo ngày (lấy max/min trong ngày)
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(seconds=timezone_offset))

        daily: dict[str, dict] = {}
        for entry in data["list"]:
            dt = datetime.fromtimestamp(entry["dt"], tz=tz)
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in daily:
                daily[date_str] = {
                    "temps": [],
                    "descriptions": [],
                    "precip": 0.0,
                    "humidity": [],
                    "wind": [],
                    "uv": [],
                }
            d = daily[date_str]
            d["temps"].append(entry["main"]["temp"])
            d["descriptions"].append(entry["weather"][0]["description"])
            d["precip"] += entry.get("rain", {}).get("3h", 0)
            d["humidity"].append(entry["main"]["humidity"])
            d["wind"].append(entry["wind"]["speed"] * 3.6)  # m/s → km/h
            # UV không có trong forecast free tier → dùng estimate từ nhiệt độ
            temp_max = max(d["temps"]) if d["temps"] else 25
            d["uv"].append(max(0, (temp_max - 15) / 3))  # rough estimate

        forecast = []
        for date_str, d in list(daily.items())[:days]:
            temps = d["temps"]
            desc = max(set(d["descriptions"]), key=d["descriptions"].count)
            precip = d["precip"]
            icon = _weather_icon(desc, precip)
            uv = sum(d["uv"]) / len(d["uv"]) if d["uv"] else 0
            forecast.append(DailyForecast(
                date=date_str,
                temp_min=min(temps),
                temp_max=max(temps),
                description=desc,
                precipitation_mm=precip,
                humidity_pct=int(sum(d["humidity"]) / len(d["humidity"])),
                wind_kmh=max(d["wind"]),
                uv_index=uv,
                icon=icon,
            ))

        travel_warning = _assess_travel_risk(forecast)

        return WeatherData(
            city=city_name,
            country=country,
            timezone=str(tz),
            current_temp=current_temp,
            current_description=current_desc,
            current_humidity=current_humidity,
            forecast=forecast,
            travel_warning=travel_warning,
            data_mode="live",
        )

    @staticmethod
    def _missing_data(city: str, reason: str = "") -> WeatherData:
        """Trả về WeatherData rỗng với lý do thiếu dữ liệu."""
        note = f"Không có dữ liệu thời tiết" + (f": {reason}" if reason else "")
        return WeatherData(
            city=city,
            country="",
            timezone="",
            current_temp=0.0,
            current_description=note,
            current_humidity=0,
            forecast=[],
            travel_warning="",
            source="N/A",
            data_mode="missing",
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Lấy WeatherService instance (singleton)."""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service
