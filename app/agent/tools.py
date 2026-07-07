"""
Agent Tools - Các công cụ mà AI có thể sử dụng

Mỗi tool là một function được decorated với @tool từ LangChain.
AI sẽ tự động quyết định khi nào cần dùng tool nào.
"""
from langchain_core.tools import tool
from app.services.search import get_search_service
import json


@tool
def search_travel_info(query: str) -> str:
    """
    Tìm kiếm thông tin du lịch trên internet.

    Dùng khi cần tìm:
    - Thông tin về địa điểm du lịch
    - Giá vé máy bay, khách sạn
    - Hoạt động và điểm tham quan
    - Thời tiết và mùa du lịch tại các nơi

    Args:
        query: Câu hỏi tìm kiếm bằng tiếng Việt hoặc tiếng Anh

    Returns:
        Kết quả tìm kiếm từ internet
    """
    service = get_search_service()
    result = service.search(query=query, max_results=5)
    return result.to_text()


@tool
def create_travel_itinerary(
    destination: str,
    duration_days: int,
    interests: str,
    budget_vnd: int = 0,
) -> str:
    """
    Tạo lịch trình du lịch chi tiết theo ngày.
    
    Dùng khi người dùng muốn:
    - Lên kế hoạch chuyến đi cụ thể
    - Biết nên đi đâu, làm gì mỗi ngày
    
    Args:
        destination: Địa điểm du lịch (VD: "Đà Nẵng", "Hội An")
        duration_days: Số ngày du lịch
        interests: Sở thích (VD: "biển, ẩm thực, văn hóa")
        budget_vnd: Ngân sách (VND), 0 = không giới hạn
        
    Returns:
        Lịch trình du lịch chi tiết dạng JSON string
    """
    # Tool này trả về cấu trúc để AI điền nội dung
    itinerary_template = {
        "destination": destination,
        "duration": f"{duration_days} ngày",
        "budget": f"{budget_vnd:,} VND" if budget_vnd > 0 else "Linh hoạt",
        "interests": interests,
        "note": f"Đây là template lịch trình {duration_days} ngày tại {destination}. AI sẽ điền chi tiết dựa trên sở thích: {interests}",
    }
    return json.dumps(itinerary_template, ensure_ascii=False, indent=2)


@tool
def calculate_travel_budget(
    destination: str,
    duration_days: int,
    num_people: int = 1,
    accommodation_level: str = "mid-range",
) -> str:
    """
    Ước tính ngân sách du lịch.
    
    Dùng khi người dùng hỏi về:
    - Chi phí chuyến đi
    - Cần bao nhiêu tiền
    - Breakdown các khoản chi
    
    Args:
        destination: Địa điểm du lịch
        duration_days: Số ngày
        num_people: Số người đi
        accommodation_level: Mức khách sạn ("budget", "mid-range", "luxury")
        
    Returns:
        Ước tính ngân sách theo từng hạng mục
    """
    # Giá tham khảo (VND/người/ngày) cho các điểm phổ biến ở Việt Nam
    accommodation_costs = {
        "budget": 200_000,      # Hostel/homestay giá rẻ
        "mid-range": 600_000,   # Khách sạn 3 sao
        "luxury": 2_000_000,    # Khách sạn 4-5 sao
    }
    
    food_per_day = 300_000       # Ăn uống TB/người/ngày
    transport_per_day = 150_000  # Di chuyển TB/người/ngày
    activities_per_day = 200_000 # Tham quan/giải trí TB/người/ngày
    
    hotel_cost = accommodation_costs.get(accommodation_level, 600_000)
    
    daily_cost = hotel_cost + food_per_day + transport_per_day + activities_per_day
    total_per_person = daily_cost * duration_days
    total_all = total_per_person * num_people
    
    budget_breakdown = {
        "destination": destination,
        "duration": f"{duration_days} ngày",
        "num_people": num_people,
        "accommodation_level": accommodation_level,
        "breakdown_per_person_per_day": {
            "accommodation": f"{hotel_cost:,} VND",
            "food": f"{food_per_day:,} VND",
            "transport": f"{transport_per_day:,} VND",
            "activities": f"{activities_per_day:,} VND",
            "total_per_day": f"{daily_cost:,} VND",
        },
        "total_per_person": f"{total_per_person:,} VND",
        "total_all_people": f"{total_all:,} VND",
        "note": "Chi phí chưa bao gồm vé máy bay. Giá mang tính tham khảo.",
    }
    
    return json.dumps(budget_breakdown, ensure_ascii=False, indent=2)


@tool
def get_destination_info(destination: str) -> str:
    """
    Lấy thông tin tổng quan về điểm đến.
    
    Dùng khi người dùng hỏi về:
    - Địa điểm du lịch nên đi
    - Thời điểm tốt nhất để đến
    - Đặc sản, văn hóa địa phương
    
    Args:
        destination: Tên địa điểm du lịch
        
    Returns:
        Thông tin tổng quan về điểm đến
    """
    # Dữ liệu offline cho các điểm phổ biến ở Việt Nam
    destinations_db = {
        "đà nẵng": {
            "best_time": "Tháng 2-8 (khô ráo, ít mưa)",
            "highlights": ["Bãi biển Mỹ Khê", "Bà Nà Hills", "Ngũ Hành Sơn", "Cầu Vàng"],
            "cuisine": ["Mì Quảng", "Bánh mì Đà Nẵng", "Hải sản tươi sống", "Bún chả cá"],
            "avg_temp": "27-30°C",
            "currency": "VND",
        },
        "hà nội": {
            "best_time": "Tháng 9-11 và 3-4 (thu & xuân)",
            "highlights": ["Hồ Hoàn Kiếm", "Văn Miếu", "Phố cổ 36 phường", "Lăng Bác"],
            "cuisine": ["Phở", "Bún chả", "Chả cá Lã Vọng", "Bánh cuốn"],
            "avg_temp": "17-28°C (theo mùa)",
            "currency": "VND",
        },
        "hội an": {
            "best_time": "Tháng 2-7 (mùa khô)",
            "highlights": ["Phố cổ Hội An", "Làng rau Trà Quế", "Cù Lao Chàm", "Chùa Cầu"],
            "cuisine": ["Cao lầu", "Mì Quảng", "White rose (bánh vạc)", "Cơm gà"],
            "avg_temp": "25-35°C",
            "currency": "VND",
        },
        "hồ chí minh": {
            "best_time": "Tháng 12-4 (mùa khô)",
            "highlights": ["Bến Nghé", "Dinh Độc Lập", "Chợ Bến Thành", "Địa đạo Củ Chi"],
            "cuisine": ["Hủ tiếu Nam Vang", "Bánh mì Sài Gòn", "Cơm tấm", "Bánh xèo"],
            "avg_temp": "25-35°C",
            "currency": "VND",
        },
        "phú quốc": {
            "best_time": "Tháng 11-3 (mùa khô)",
            "highlights": ["Bãi Sao", "Vinpearl Safari", "Chợ đêm Phú Quốc", "Grand World"],
            "cuisine": ["Hải sản", "Nước mắm Phú Quốc", "Gỏi cá trích", "Bún quậy"],
            "avg_temp": "27-33°C",
            "currency": "VND",
        },
    }
    
    # Tìm kiếm không phân biệt hoa thường
    key = destination.lower().strip()
    info = destinations_db.get(key)
    
    if info:
        result = {
            "destination": destination,
            **info,
            "source": "Local database",
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    else:
        return f"Không có thông tin offline cho '{destination}'. Hãy dùng tool search_travel_info để tìm kiếm trực tuyến."


# Danh sách tất cả tools để đăng ký với LLM
ALL_TOOLS = [
    search_travel_info,
    create_travel_itinerary,
    calculate_travel_budget,
    get_destination_info,
]
