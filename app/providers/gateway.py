from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date, timedelta
import re
from typing import Generic, List, TypeVar

import httpx

from app.config import get_settings
from app.providers.normalizers import FlightOption, HotelOption, normalize_flights, normalize_hotels


T = TypeVar("T")
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class ProviderMetadata:
    provider: str
    data_mode: str
    retrieved_at: str
    fallback_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    items: List[T]
    metadata: ProviderMetadata


class ProviderError(RuntimeError):
    """A live travel provider did not return usable search results."""


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _search_serpapi(params: dict, api_key: str) -> dict:
    response = httpx.get(
        SERPAPI_SEARCH_URL,
        params={**params, "api_key": api_key},
        timeout=12.0,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ProviderError(str(payload["error"]))
    return payload


def _digits(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    number = re.sub(r"[^0-9.]", "", str(value).replace(",", ""))
    return float(number) if number else 0.0

# ============================================================
# API Mock Data Fixtures for Vietnam Destinations
# ============================================================

MOCK_FLIGHT_FIXTURES = {
    # HAN -> DAD (Hà Nội -> Đà Nẵng)
    ("HAN", "DAD"): [
        {"airline": "Vietjet Air", "price": 1250000, "total_duration": 80, "stops": 0, "departure_time": "08:15", "arrival_time": "09:35", "booking_url": "https://www.vietjetair.com"},
        {"airline": "Bamboo Airways", "price": 1650000, "total_duration": 75, "stops": 0, "departure_time": "11:30", "arrival_time": "12:45", "booking_url": "https://www.bambooairways.com"},
        {"airline": "Vietnam Airlines", "price": 2100000, "total_duration": 80, "stops": 0, "departure_time": "14:00", "arrival_time": "15:20", "booking_url": "https://www.vietnamairlines.com"},
    ],
    # HAN -> PQC (Hà Nội -> Phú Quốc)
    ("HAN", "PQC"): [
        {"airline": "Vietjet Air", "price": 1850000, "total_duration": 125, "stops": 0, "departure_time": "07:00", "arrival_time": "09:05", "booking_url": "https://www.vietjetair.com"},
        {"airline": "Bamboo Airways", "price": 2450000, "total_duration": 120, "stops": 0, "departure_time": "10:15", "arrival_time": "12:15", "booking_url": "https://www.bambooairways.com"},
        {"airline": "Vietnam Airlines", "price": 3200000, "total_duration": 120, "stops": 0, "departure_time": "13:30", "arrival_time": "15:30", "booking_url": "https://www.vietnamairlines.com"},
    ],
    # SGN -> DAD (Hồ Chí Minh -> Đà Nẵng)
    ("SGN", "DAD"): [
        {"airline": "Vietjet Air", "price": 1150000, "total_duration": 80, "stops": 0, "departure_time": "06:15", "arrival_time": "07:35", "booking_url": "https://www.vietjetair.com"},
        {"airline": "Bamboo Airways", "price": 1550000, "total_duration": 75, "stops": 0, "departure_time": "09:30", "arrival_time": "10:45", "booking_url": "https://www.bambooairways.com"},
        {"airline": "Vietnam Airlines", "price": 1950000, "total_duration": 80, "stops": 0, "departure_time": "15:00", "arrival_time": "16:20", "booking_url": "https://www.vietnamairlines.com"},
    ],
    # SGN -> PQC (Hồ Chí Minh -> Phú Quốc)
    ("SGN", "PQC"): [
        {"airline": "Vietjet Air", "price": 950000, "total_duration": 60, "stops": 0, "departure_time": "08:00", "arrival_time": "09:00", "booking_url": "https://www.vietjetair.com"},
        {"airline": "Bamboo Airways", "price": 1350000, "total_duration": 55, "stops": 0, "departure_time": "12:15", "arrival_time": "13:10", "booking_url": "https://www.bambooairways.com"},
        {"airline": "Vietnam Airlines", "price": 1750000, "total_duration": 60, "stops": 0, "departure_time": "16:30", "arrival_time": "17:30", "booking_url": "https://www.vietnamairlines.com"},
    ],
}

MOCK_HOTEL_FIXTURES = {
    "Da Nang": {
        "budget": [
            {"name": "Danang Backpackers Hostel", "location": "Quận Hải Châu", "price": 150000, "rating": 4.1, "reviews": 120, "amenities": ["Wifi miễn phí", "Điều hòa", "Bể bơi tập thể"]},
            {"name": "Haian Riverfront Hotel Annex", "location": "Đường Bạch Đằng", "price": 450000, "rating": 4.3, "reviews": 98, "amenities": ["Wifi miễn phí", "Điều hòa", "Gần trung tâm"]},
        ],
        "medium": [
            {"name": "Vanda Hotel Da Nang", "location": "Quận Hải Châu", "price": 950000, "rating": 4.4, "reviews": 512, "amenities": ["Bể bơi trong nhà", "Spa", "Nhà hàng", "Phòng gym"]},
            {"name": "Sala Danang Beach Hotel", "location": "Bãi biển Mỹ Khê", "price": 1350000, "rating": 4.6, "reviews": 840, "amenities": ["Bể bơi vô cực", "Sát biển", "Quầy bar tầng thượng"]},
        ],
        "comfort": [
            {"name": "Novotel Danang Premier Han River", "location": "Quận Hải Châu", "price": 280000, "rating": 4.7, "reviews": 1420, "amenities": ["Sky Bar", "Bể bơi ngoài trời", "Dịch vụ phòng 24/7"]},
            {"name": "Furama Resort Da Nang", "location": "Đường Võ Nguyên Giáp", "price": 4200000, "rating": 4.8, "reviews": 2100, "amenities": ["Resort sát biển", "Hồ bơi rừng nhiệt đới", "Ẩm thực 5 sao"]},
        ],
        "luxury": [
            {"name": "InterContinental Danang Sun Peninsula Resort", "location": "Bán đảo Sơn Trà", "price": 11500000, "rating": 4.9, "reviews": 980, "amenities": ["Resort biệt lập", "Bãi biển riêng", "Nhà hàng Michelin", "Spa sang trọng"]},
        ]
    },
    "Phu Quoc": {
        "budget": [
            {"name": "Phu Quoc Valley Resort Annex", "location": "Thị trấn Dương Đông", "price": 250000, "rating": 4.0, "reviews": 75, "amenities": ["Wifi miễn phí", "Thuê xe máy", "Phòng đơn"]},
            {"name": "Langchia Home Phu Quoc", "location": "Đường Trần Hưng Đạo", "price": 480000, "rating": 4.2, "reviews": 110, "amenities": ["Wifi miễn phí", "Gần biển", "Sân vườn"]},
        ],
        "medium": [
            {"name": "L'Azure Resort & Spa Phu Quoc", "location": "Thị trấn Dương Đông", "price": 1450000, "rating": 4.5, "reviews": 620, "amenities": ["Bãi biển riêng", "Spa ngoài trời", "Bữa sáng miễn phí"]},
            {"name": "Lahana Resort Phu Quoc", "location": "Thị trấn Dương Đông", "price": 1650000, "rating": 4.6, "reviews": 750, "amenities": ["Bể bơi vô cực sườn đồi", "Resort sinh thái", "Nhà hàng"]},
        ],
        "comfort": [
            {"name": "Pullman Phu Quoc Beach Resort", "location": "Đường Bào, Dương Tơ", "price": 3100000, "rating": 4.7, "reviews": 1250, "amenities": ["Bể bơi lớn nhất đảo", "Kid Club", "Pool Bar", "Sân Tennis"]},
            {"name": "InterContinental Phu Quoc Long Beach Resort", "location": "Bãi Trường", "price": 4800000, "rating": 4.8, "reviews": 1820, "amenities": ["Sky Bar Ink 360", "Hồ bơi sát biển", "Trượt nước trẻ em"]},
        ],
        "luxury": [
            {"name": "JW Marriott Phu Quoc Emerald Bay Resort & Spa", "location": "Bãi Khem", "price": 8500000, "rating": 4.9, "reviews": 1440, "amenities": ["Kiến trúc cổ điển", "Bãi biển riêng", "Spa đoạt giải thưởng", "Hồ bơi hình con sò"]},
        ]
    }
}

# ============================================================
# Core Translation & Fetch Functions
# ============================================================

def _map_city_to_iata(city_name: str) -> str:
    """Chuyển đổi tên thành phố tiếng Việt sang mã sân bay IATA tương ứng"""
    if not city_name:
        return "HAN"
    
    val = city_name.strip().lower()
    if any(x in val for x in ["hà nội", "ha noi", "noi bai", "nội bài", "han"]):
        return "HAN"
    if any(x in val for x in ["hồ chí minh", "ho chi minh", "sài gòn", "sai gon", "tân sơn nhất", "tan son nhat", "sgn"]):
        return "SGN"
    if any(x in val for x in ["đà nẵng", "da nang", "dad"]):
        return "DAD"
    if any(x in val for x in ["phú quốc", "phu quoc", "pqc"]):
        return "PQC"
    if any(x in val for x in ["nha trang", "cam ranh", "cxr"]):
        return "CXR"
    if any(x in val for x in ["đà lạt", "da lat", "liên khương", "lien khuong", "dli"]):
        return "DLI"
    
    return "HAN"  # Fallback mặc định

def _fetch_fixture_flights(origin: str, destination: str, departure_date: str, return_date: str | None = None) -> List[FlightOption]:
    """Tìm kiếm chuyến bay (hiện tại trả về dữ liệu mock chất lượng cao)"""
    ori_iata = _map_city_to_iata(origin)
    dest_iata = _map_city_to_iata(destination)
    
    # Tìm kiếm một chiều
    outbound_key = (ori_iata, dest_iata)
    outbound_data = MOCK_FLIGHT_FIXTURES.get(outbound_key, [])
    
    # Nếu không tìm thấy chặng bay cụ thể, sinh dữ liệu tự động dựa trên khoảng cách giả định
    if not outbound_data:
        outbound_data = [
            {"airline": "Vietjet Air (Fixture)", "price": 1450000, "total_duration": 90, "stops": 0, "departure_time": "09:00", "arrival_time": "10:30"},
            {"airline": "Vietnam Airlines (Fixture)", "price": 2250000, "total_duration": 95, "stops": 0, "departure_time": "13:00", "arrival_time": "14:35"}
        ]

    # Đưa vào list kết quả
    items = []
    for f in outbound_data:
        item = f.copy()
        item["data_mode"] = "fixture"
        items.append(item)

    # Nếu khứ hồi, thêm chặng về
    if return_date:
        return_key = (dest_iata, ori_iata)
        return_data = MOCK_FLIGHT_FIXTURES.get(return_key, [])
        if not return_data:
            return_data = [
                {"airline": "Vietjet Air (Fixture)", "price": 1450000, "total_duration": 90, "stops": 0, "departure_time": "16:00", "arrival_time": "17:30"},
                {"airline": "Vietnam Airlines (Fixture)", "price": 2250000, "total_duration": 95, "stops": 0, "departure_time": "20:00", "arrival_time": "21:35"}
            ]
        for f in return_data:
            item = f.copy()
            item["airline"] = f"{f['airline']} (Chiều về)"
            item["data_mode"] = "fixture"
            items.append(item)

    return normalize_flights(items, data_mode="fixture")

def _fetch_fixture_hotels(destination: str, comfort_level: str = "medium") -> List[HotelOption]:
    """Tìm kiếm khách sạn tại điểm đến dựa trên mức độ thoải mái mong muốn"""
    # Chuẩn hóa tên điểm đến
    dest_key = "Da Nang"
    val = destination.strip().lower()
    if any(x in val for x in ["phú quốc", "phu quoc", "pqc"]):
        dest_key = "Phu Quoc"
    
    # Khớp comfort level
    comfort = comfort_level.strip().lower()
    if comfort not in ["budget", "medium", "comfort", "luxury"]:
        comfort = "medium"

    dest_hotels = MOCK_HOTEL_FIXTURES.get(dest_key, {})
    hotel_list = dest_hotels.get(comfort, [])
    
    # Fallback nếu không khớp được địa danh
    if not hotel_list:
        hotel_list = [
            {"name": f"Comfort Hotel {destination}", "location": "Trung tâm thành phố", "price": 850000, "rating": 4.3, "reviews": 150, "amenities": ["Wifi miễn phí", "Điều hòa"]},
            {"name": f"Grand Plaza Resort {destination}", "location": "Gần bãi biển", "price": 1750000, "rating": 4.6, "reviews": 320, "amenities": ["Bể bơi", "Spa", "Nhà hàng"]}
        ]

    items = []
    for h in hotel_list:
        item = h.copy()
        item["data_mode"] = "fixture"
        items.append(item)

    return normalize_hotels(items, data_mode="fixture")


def _live_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    api_key: str,
) -> List[FlightOption]:
    payload = _search_serpapi(
        {
            "engine": "google_flights",
            "departure_id": _map_city_to_iata(origin),
            "arrival_id": _map_city_to_iata(destination),
            "outbound_date": departure_date,
            "return_date": return_date,
            "type": 1 if return_date else 2,
            "adults": 1,
            "currency": "VND",
            "hl": "en",
            "gl": "vn",
        },
        api_key,
    )
    raw_items = []
    for itinerary in (payload.get("best_flights", []) + payload.get("other_flights", []))[:8]:
        legs = itinerary.get("flights", [])
        if not legs or not itinerary.get("price"):
            continue
        first, last = legs[0], legs[-1]
        raw_items.append(
            {
                "airline": first.get("airline"),
                "departure_time": str(first.get("departure_airport", {}).get("time", "")).split(" ")[-1],
                "arrival_time": str(last.get("arrival_airport", {}).get("time", "")).split(" ")[-1],
                "total_duration": itinerary.get("total_duration") or sum(leg.get("duration", 0) for leg in legs),
                "stops": max(len(legs) - 1, 0),
                "price": itinerary["price"],
                "price_scope": "round_trip_per_traveler" if return_date else "one_way_per_traveler",
                "currency": payload.get("search_parameters", {}).get("currency", "VND"),
                "booking_url": None,
                "data_mode": "live",
            }
        )
    options = normalize_flights(raw_items, data_mode="live")
    if not options:
        raise ProviderError("Google Flights returned no priced itineraries")
    return options


def _live_hotels(
    destination: str,
    check_in_date: str,
    check_out_date: str,
    travelers: int,
    api_key: str,
) -> List[HotelOption]:
    payload = _search_serpapi(
        {
            "engine": "google_hotels",
            "q": f"{destination} hotels",
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "adults": max(travelers, 1),
            "currency": "VND",
            "hl": "en",
            "gl": "vn",
        },
        api_key,
    )
    raw_items = []
    for property_ in payload.get("properties", [])[:8]:
        rate = property_.get("rate_per_night", {})
        price = _digits(rate.get("extracted_lowest") or rate.get("lowest") or property_.get("extracted_price"))
        if not price:
            continue
        raw_items.append(
            {
                "name": property_.get("name"),
                "location": property_.get("neighborhood") or property_.get("description", ""),
                "price": price,
                "rating": property_.get("overall_rating"),
                "reviews": property_.get("reviews"),
                "booking_url": property_.get("link"),
                "amenities": property_.get("amenities", []),
                "data_mode": "live",
            }
        )
    options = normalize_hotels(raw_items, data_mode="live")
    if not options:
        raise ProviderError("Google Hotels returned no nightly prices")
    return options


def _fallback_metadata(provider: str, reason: str) -> ProviderMetadata:
    return ProviderMetadata(
        provider=provider,
        data_mode="fixture",
        retrieved_at=_now_iso(),
        fallback_reason=reason,
    )


def fetch_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
) -> ProviderResult[FlightOption]:
    """Return live SerpApi/Google Flights results, or explicitly marked fixtures."""
    api_key = get_settings().serpapi_api_key.strip()
    if not api_key:
        return ProviderResult(
            _fetch_fixture_flights(origin, destination, departure_date, return_date),
            _fallback_metadata("Fixture flight catalog", "SERPAPI_API_KEY is not configured"),
        )
    try:
        return ProviderResult(
            _live_flights(origin, destination, departure_date, return_date, api_key),
            ProviderMetadata("SerpApi / Google Flights", "live", _now_iso()),
        )
    except (httpx.HTTPError, ProviderError, ValueError) as exc:
        return ProviderResult(
            _fetch_fixture_flights(origin, destination, departure_date, return_date),
            _fallback_metadata("Fixture flight catalog", f"Live provider unavailable ({type(exc).__name__})"),
        )


def fetch_hotels(
    destination: str,
    comfort_level: str = "medium",
    check_in_date: str | None = None,
    check_out_date: str | None = None,
    travelers: int = 1,
) -> ProviderResult[HotelOption]:
    """Return live SerpApi/Google Hotels results, or explicitly marked fixtures."""
    check_in = check_in_date or (date.today() + timedelta(days=14)).isoformat()
    try:
        default_check_out = (date.fromisoformat(check_in) + timedelta(days=1)).isoformat()
    except ValueError:
        check_in = (date.today() + timedelta(days=14)).isoformat()
        default_check_out = (date.today() + timedelta(days=15)).isoformat()
    check_out = check_out_date or default_check_out
    api_key = get_settings().serpapi_api_key.strip()
    if not api_key:
        return ProviderResult(
            _fetch_fixture_hotels(destination, comfort_level),
            _fallback_metadata("Fixture hotel catalog", "SERPAPI_API_KEY is not configured"),
        )
    try:
        return ProviderResult(
            _live_hotels(destination, check_in, check_out, travelers, api_key),
            ProviderMetadata("SerpApi / Google Hotels", "live", _now_iso()),
        )
    except (httpx.HTTPError, ProviderError, ValueError) as exc:
        return ProviderResult(
            _fetch_fixture_hotels(destination, comfort_level),
            _fallback_metadata("Fixture hotel catalog", f"Live provider unavailable ({type(exc).__name__})"),
        )
