"""
Test Agent - Script kiểm tra agent hoạt động đúng không

Chạy: python tests/test_agent.py
(Cần có .env với GOOGLE_API_KEY hợp lệ)
"""
import asyncio
import sys
import os

# Thêm root vào path để import được các module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from app.agent.graph import create_travel_agent
from app.agent.state import TravelAgentState


async def test_basic_chat():
    """Test: Hỏi thông tin cơ bản (không cần tool)"""
    print("\n" + "="*60)
    print("TEST 1: Hỏi cơ bản")
    print("="*60)
    
    agent = create_travel_agent()
    
    state: TravelAgentState = {
        "messages": [HumanMessage(content="Xin chào! Bạn có thể giúp gì cho tôi?")],
        "tools_used": [],
        "travel_context": {},
        "error": None,
    }
    
    result = await agent.ainvoke(state)
    
    print(f"✅ Response: {result['messages'][-1].content[:200]}...")
    print(f"🔧 Tools used: {result['tools_used']}")


async def test_destination_info():
    """Test: Hỏi thông tin địa điểm (dùng tool get_destination_info)"""
    print("\n" + "="*60)
    print("TEST 2: Thông tin địa điểm")
    print("="*60)
    
    agent = create_travel_agent()
    
    state: TravelAgentState = {
        "messages": [HumanMessage(content="Cho tôi biết thông tin về du lịch Đà Nẵng")],
        "tools_used": [],
        "travel_context": {},
        "error": None,
    }
    
    result = await agent.ainvoke(state)
    
    print(f"✅ Response: {result['messages'][-1].content[:300]}...")
    print(f"🔧 Tools used: {result['tools_used']}")


async def test_budget_calculation():
    """Test: Tính ngân sách (dùng tool calculate_travel_budget)"""
    print("\n" + "="*60)
    print("TEST 3: Tính ngân sách")
    print("="*60)
    
    agent = create_travel_agent()
    
    state: TravelAgentState = {
        "messages": [HumanMessage(
            content="Đi Hội An 3 ngày 2 người, khách sạn 3 sao thì tốn bao nhiêu tiền?"
        )],
        "tools_used": [],
        "travel_context": {},
        "error": None,
    }
    
    result = await agent.ainvoke(state)
    
    print(f"✅ Response: {result['messages'][-1].content[:400]}...")
    print(f"🔧 Tools used: {result['tools_used']}")


async def main():
    print("🚀 Bắt đầu test Travel AI Agent...")
    
    try:
        await test_basic_chat()
        await test_destination_info()
        await test_budget_calculation()
        print("\n✅ Tất cả tests đã chạy xong!")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        print("Hãy kiểm tra:")
        print("  1. File .env có GOOGLE_API_KEY chưa?")
        print("  2. API key có hợp lệ không?")


if __name__ == "__main__":
    asyncio.run(main())
