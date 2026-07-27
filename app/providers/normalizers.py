from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class FlightOption(BaseModel):
    id: str
    airline: str
    departure_time: str = ""
    arrival_time: str = ""
    duration_minutes: int = Field(default=0, ge=0)
    stops: int = Field(default=0, ge=0)
    price: float = Field(ge=0, description="Price per traveler")
    price_scope: str = "one_way_per_traveler"
    currency: str = "VND"
    booking_url: Optional[str] = None
    data_mode: str = "live"

    def to_text(self) -> str:
        stops_text = "Thẳng" if self.stops == 0 else f"{self.stops} dừng"
        dur_hrs = self.duration_minutes // 60
        dur_mins = self.duration_minutes % 60
        dur_text = f"{dur_hrs}h {dur_mins}m" if dur_hrs > 0 else f"{dur_mins}m"
        return (
            f"[{self.airline}] Vé bay: {self.price:,.0f} {self.currency}/người "
            f"({self.departure_time} - {self.arrival_time}, {dur_text}, {stops_text})"
        )

class HotelOption(BaseModel):
    id: str
    name: str
    area: str = ""
    price_per_night: float = Field(ge=0)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: int = Field(default=0, ge=0)
    booking_url: Optional[str] = None
    amenities: List[str] = Field(default_factory=list)
    data_mode: str = "live"

    def to_text(self) -> str:
        rating_text = f"{self.rating}★ ({self.review_count} reviews)" if self.rating else "Chưa xếp hạng"
        amenities_text = f", Tiện ích: {', '.join(self.amenities[:3])}" if self.amenities else ""
        return (
            f"[{self.name}] {self.area} - {self.price_per_night:,.0f} VND/đêm "
            f"({rating_text}{amenities_text})"
        )

def normalize_flights(items: List[dict], data_mode: str = "live") -> List[FlightOption]:
    """Chuẩn hóa dữ liệu chuyến bay từ JSON thô"""
    options = []
    for index, item in enumerate(items, 1):
        options.append(FlightOption(
            id=f"flight_{index}",
            airline=item.get("airline") or "Unknown Airline",
            departure_time=item.get("departure_time") or "",
            arrival_time=item.get("arrival_time") or "",
            duration_minutes=item.get("total_duration") or item.get("duration_minutes") or 0,
            stops=item.get("stops", 0),
            price=float(item.get("price") or 0),
            price_scope=item.get("price_scope") or "one_way_per_traveler",
            currency=item.get("currency") or "VND",
            booking_url=item.get("booking_url"),
            data_mode=item.get("data_mode") or data_mode
        ))
    return options

def normalize_hotels(items: List[dict], data_mode: str = "live") -> List[HotelOption]:
    """Chuẩn hóa dữ liệu khách sạn từ JSON thô"""
    options = []
    for index, item in enumerate(items, 1):
        options.append(HotelOption(
            id=f"hotel_{index}",
            name=item.get("name") or "Unknown Hotel",
            area=item.get("location") or item.get("area") or "",
            price_per_night=float(item.get("price") or item.get("price_per_night") or 0),
            rating=item.get("rating"),
            review_count=item.get("reviews") or item.get("review_count") or 0,
            booking_url=item.get("booking_url"),
            amenities=item.get("amenities") or [],
            data_mode=item.get("data_mode") or data_mode
        ))
    return options
