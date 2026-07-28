"""
API Routes - Định nghĩa các endpoints của Travel AI Assistant (Phase 4)

Endpoints:
- GET  /health          ← Health check
- POST /chat            ← Chat thường (đồng bộ)
- POST /chat/stream     ← Chat streaming (SSE)
- GET  /trips/{sid}     ← Lấy TripPlan + DecisionReport hiện tại
- POST /trips/{sid}/confirm ← Xác nhận kế hoạch và kích hoạt agent tìm kiếm
- PATCH /trips/{sid}/plan ← Cập nhật trực tiếp TripPlan và tính toán lại chi phí/rủi ro
"""
import uuid
import logging
import json
import dataclasses
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

from app.config import get_settings
from app.models.schemas import (
    ChatRequest, ChatResponse,
    HealthResponse, ErrorResponse, Message,
)
from app.models.trip_plan import TripPlan, TripStatus
from app.agent.graph import get_agent, run_graph_call, stream_graph_events
from app.agent.state import TravelAgentState
from app.services.search import get_search_service
from app.services.session_store import deserialize_decision_report, get_session_store
from app.services.calculator import get_decision_engine

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _error_response(
    status_code: int,
    error: str,
    message: str,
    session_id: str | None = None,
) -> JSONResponse:
    """Tạo JSONResponse lỗi chuẩn hóa"""
    body = ErrorResponse(error=error, message=message, session_id=session_id)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _extract_text(content) -> str:
    """Flatten AIMessage.content thành plain text"""
    if isinstance(content, str):
        return content
    return " ".join(
        part if isinstance(part, str) else part.get("text", "")
        for part in content
    )


def _to_serializable(obj) -> dict | None:
    """Chuyển đổi Pydantic model hoặc Dataclass thành dict"""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _graph_config(session_id: str) -> dict:
    """Keep every graph invocation bound to its durable API session."""
    return {"configurable": {"thread_id": session_id}}


def _is_waiting_for_confirmation(snapshot) -> bool:
    return "human_confirm" in (snapshot.next or ())


def _confirmation_message(plan: TripPlan) -> str:
    return (
        f"Mình đã tạo kế hoạch nháp cho {plan.destination}. "
        "Hãy xem lại thông tin và bấm **Xác nhận kế hoạch** để mình bắt đầu "
        "tra cứu thời tiết, chi phí, chuyến bay và khách sạn."
    )


def _latest_ai_text(state: dict) -> str:
    ai_messages = [
        m for m in state.get("messages", [])
        if isinstance(m, AIMessage) and m.content
    ]
    return _extract_text(ai_messages[-1].content) if ai_messages else ""


def _update_decision_report(session_id: str, plan: TripPlan, travel_context: dict) -> None:
    """Đồng bộ hóa TripPlan sang Decision Engine để cập nhật chi phí & rủi ro"""
    store = get_session_store()
    engine = get_decision_engine()

    month = None
    if plan.dates.departure:
        try:
            from datetime import date
            month = date.fromisoformat(plan.dates.departure).month
        except ValueError:
            pass

    weather_warning = travel_context.get("weather_warning", "")

    # Tính toán báo cáo khả thi chuyến đi
    report = engine.evaluate(
        destination=plan.destination,
        days=plan.dates.days or 1,
        travelers=plan.travelers,
        comfort_level=plan.comfort_level,
        budget_provided=plan.budget.total or 0.0,
        nights=plan.dates.nights,
        origin=plan.origin,
        departure_month=month,
        weather_warning=weather_warning,
    )

    serialized_report = travel_context.get("decision_report")
    if isinstance(serialized_report, dict):
        try:
            report = deserialize_decision_report(serialized_report)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid agent decision report: %s", exc)

    store.save_trip_plan(session_id, plan)
    store.save_decision(session_id, report)

    itinerary = travel_context.get("itinerary")
    if itinerary:
        store.save_itinerary(session_id, itinerary)


# ──────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Kiểm tra trạng thái server",
)
async def health_check():
    search = get_search_service()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        model=settings.gemini_model,
        search_enabled=search.is_enabled,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Gửi tin nhắn tới Travel AI (Đồng bộ)",
)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    store = get_session_store()
    session_state = store.get_or_create(session_id)

    # Lấy lịch sử
    history: list = []
    for msg in (request.conversation_history or []):
        if msg.role.value == "user":
            history.append(HumanMessage(content=msg.content))
        elif msg.role.value == "assistant":
            history.append(AIMessage(content=msg.content))

    # Tạo initial state
    initial_state: TravelAgentState = {
        "messages": history + [HumanMessage(content=request.message)],
        "trip_plan": session_state.trip_plan,
        "intent": None,
        "tools_used": [],
        "travel_context": {},
        "error": None,
    }

    try:
        agent = get_agent()
        graph_config = _graph_config(session_id)
        final_state = await run_graph_call(agent.invoke, initial_state, config=graph_config)
        snapshot = await run_graph_call(agent.get_state, graph_config)
        awaiting_confirmation = _is_waiting_for_confirmation(snapshot)

        # Lưu lại kế hoạch và cập nhật báo cáo chi phí/rủi ro nếu có
        plan = final_state.get("trip_plan")
        if plan:
            _update_decision_report(session_id, plan, final_state.get("travel_context", {}))

        ai_messages = [
            m for m in final_state["messages"]
            if isinstance(m, AIMessage) and m.content
        ]
        response_text = _extract_text(ai_messages[-1].content) if ai_messages else "(Không có phản hồi)"

        # Lưu lịch sử cuộc hội thoại vào SQL Server
        if awaiting_confirmation and plan:
            response_text = _confirmation_message(plan)

        updated_history = []
        for msg in (request.conversation_history or []):
            updated_history.append({"role": msg.role.value, "content": msg.content})
        updated_history.append({"role": "user", "content": request.message})
        updated_history.append({"role": "assistant", "content": response_text})
        store.save_history(session_id, updated_history)

        return ChatResponse(
            response=response_text,
            session_id=session_id,
            tools_used=final_state.get("tools_used", []),
        )

    except ResourceExhausted:
        return _error_response(429, "quota_exceeded", "API Gemini đã vượt giới hạn miễn phí. Vui lòng thử lại sau.", session_id)
    except Exception as e:
        logger.exception("Lỗi trong chat")
        return _error_response(500, "internal_error", f"Lỗi: {str(e)}", session_id)


@router.post(
    "/chat/stream",
    tags=["Chat"],
    summary="Gửi tin nhắn tới Travel AI (Streaming SSE)",
)
async def chat_stream(request: ChatRequest):
    """
    Endpoint streaming Server-Sent Events (SSE).
    Trả về token chữ ngay khi sinh, đồng thời stream status cập nhật node/tool.
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def sse_generator():
        store = get_session_store()
        session_state = store.get_or_create(session_id)

        history: list = []
        for msg in (request.conversation_history or []):
            if msg.role.value == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role.value == "assistant":
                history.append(AIMessage(content=msg.content))

        initial_state: TravelAgentState = {
            "messages": history + [HumanMessage(content=request.message)],
            "trip_plan": session_state.trip_plan,
            "intent": None,
            "tools_used": [],
            "travel_context": {},
            "error": None,
        }

        agent = get_agent()
        final_state = None
        graph_config = _graph_config(session_id)

        try:
            async for event in stream_graph_events(
                agent, initial_state, config=graph_config, version="v2"
            ):
                kind = event.get("event")
                name = event.get("name")
                node_name = event.get("metadata", {}).get("langgraph_node")

                # 1. Báo cáo trạng thái node
                if kind == "on_chain_start" and name == "LangGraph":
                    yield f"data: {json.dumps({'type': 'status', 'status': 'Hana đang chuẩn bị...'})}\n\n"

                elif kind == "on_chain_start" and node_name:
                    status_desc = {
                        "classify": "Đang phân tích ý định...",
                        "planner": "Đang phân tích biểu mẫu chuyến đi...",
                        "supervisor": "Trưởng nhóm đang phân bổ công việc...",
                        "weather_agent": "Trợ lý Thời tiết đang xem dự báo...",
                        "cost_agent": "Trợ lý Dự toán đang thẩm định chi phí...",
                        "itinerary_agent": "Trợ lý Lịch trình đang lên chi tiết từng ngày...",
                        "agent": "Trợ lý Hana đang hoàn thiện câu trả lời...",
                    }.get(node_name)
                    if status_desc:
                        yield f"data: {json.dumps({'type': 'status', 'status': status_desc})}\n\n"

                # 2. Stream tokens (chỉ từ agent chính)
                elif kind == "on_chat_model_stream":
                    if node_name == "agent":
                        content = event["data"]["chunk"].content
                        if content:
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                # 3. Báo cáo chạy tools
                elif kind == "on_tool_start":
                    tool_desc = {
                        "search_travel_info": "Đang tìm kiếm thông tin trên internet...",
                        "get_weather_forecast": "Đang tra cứu dự báo thời tiết...",
                        "evaluate_trip_feasibility": "Đang đánh giá chi phí và rủi ro...",
                        "calculate_travel_budget": "Đang dự toán ngân sách chi tiết...",
                        "get_destination_info": "Đang lấy cẩm nang điểm đến...",
                    }.get(name, f"Đang chạy công cụ {name}...")
                    yield f"data: {json.dumps({'type': 'status', 'status': tool_desc})}\n\n"

                # 4. Tích lũy state cuối cùng từ chain kết thúc
                elif kind == "on_chain_end":
                    output = event["data"].get("output")
                    if isinstance(output, dict) and "messages" in output:
                        final_state = output

            # 5. Xử lý lưu trữ sau khi graph chạy xong hoàn toàn
            snapshot = await run_graph_call(agent.get_state, graph_config)
            if snapshot.values:
                final_state = dict(snapshot.values)
            awaiting_confirmation = _is_waiting_for_confirmation(snapshot)

            if final_state:
                # Trích xuất và lưu lịch sử cuộc hội thoại vào SQL Server
                ai_messages = [
                    m for m in final_state.get("messages", [])
                    if isinstance(m, AIMessage) and m.content
                ]
                response_text = _extract_text(ai_messages[-1].content) if ai_messages else ""
                
                updated_history = []
                for msg in (request.conversation_history or []):
                    updated_history.append({"role": msg.role.value, "content": msg.content})
                updated_history.append({"role": "user", "content": request.message})
                plan: TripPlan = final_state.get("trip_plan")
                if awaiting_confirmation and plan:
                    response_text = _confirmation_message(plan)

                if response_text:
                    updated_history.append({"role": "assistant", "content": response_text})
                
                store.save_history(session_id, updated_history)

                plan: TripPlan = final_state.get("trip_plan")
                if plan:
                    _update_decision_report(session_id, plan, final_state.get("travel_context", {}))
                    # Gửi plan và decision mới nhất về client
                    latest_plan = store.get_or_create(session_id).trip_plan
                    latest_decision = store.get_or_create(session_id).decision
                    latest_itinerary = store.get_or_create(session_id).itinerary
                    yield f"data: {json.dumps({'type': 'plan', 'data': _to_serializable(latest_plan)})}\n\n"
                    if latest_decision:
                        yield f"data: {json.dumps({'type': 'decision', 'data': _to_serializable(latest_decision)})}\n\n"
                    if latest_itinerary:
                        yield f"data: {json.dumps({'type': 'itinerary', 'data': latest_itinerary})}\n\n"

                # Gửi sự kiện done để báo kết thúc an toàn
                if response_text:
                    yield f"data: {json.dumps({'type': 'token', 'content': response_text})}\n\n"
                if awaiting_confirmation:
                    yield f"data: {json.dumps({'type': 'interrupt', 'reason': 'human_confirm'})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'tools_used': final_state.get('tools_used', [])})}\n\n"

        except ResourceExhausted:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Tài khoản thử nghiệm của Hana đã hết lượt gọi trong phút này. Bạn hãy chờ 30 giây rồi gửi lại nhé!'})}\n\n"
        except Exception as e:
            logger.exception("Streaming error")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.get(
    "/trips/{session_id}",
    tags=["Trips"],
    summary="Lấy kế hoạch du lịch và báo cáo chi phí/rủi ro hiện tại",
)
async def get_trip(session_id: str):
    store = get_session_store()
    state = store.get_or_create(session_id)
    return {
        "session_id": session_id,
        "plan": _to_serializable(state.trip_plan),
        "decision": _to_serializable(state.decision),
        "status": state.trip_plan.status if state.trip_plan else "empty",
        "history": state.conversation_history,
        "itinerary": state.itinerary,
    }


@router.post(
    "/trips/{session_id}/confirm",
    tags=["Trips"],
    summary="Xác nhận kế hoạch (HITL) - Kích hoạt agent tìm kiếm chi tiết",
)
async def confirm_trip(session_id: str):
    """
    HITL Confirm: Chuyển trạng thái TripPlan từ draft -> confirmed,
    sau đó tự động gọi agent với một câu lệnh ẩn để agent chạy các tools tìm kiếm
    và trả về lịch trình chi tiết đã được thẩm định.
    """
    store = get_session_store()
    state = store.get_or_create(session_id)

    if not state.trip_plan:
        raise HTTPException(status_code=400, detail="Không có kế hoạch du lịch nào để xác nhận.")

    # Cập nhật status
    agent = get_agent()
    graph_config = _graph_config(session_id)
    snapshot = await run_graph_call(agent.get_state, graph_config)
    if False and not _is_waiting_for_confirmation(snapshot):
        raise HTTPException(
            status_code=409,
            detail="Káº¿ hoáº¡ch khÃ´ng á»Ÿ tráº¡ng thÃ¡i chá» xÃ¡c nháº­n hoáº·c checkpoint Ä‘Ã£ háº¿t háº¡n.",
        )

    state.trip_plan.status = TripStatus.CONFIRMED
    store.save_trip_plan(session_id, state.trip_plan)
    if _is_waiting_for_confirmation(snapshot):
        await run_graph_call(agent.update_state, graph_config, {"trip_plan": state.trip_plan})
        final_state = await run_graph_call(agent.invoke, None, config=graph_config)
    else:
        # Supports sessions created before durable checkpointing was enabled.
        fallback_state: TravelAgentState = {
            "messages": [HumanMessage(content="Execute the approved trip plan.")],
            "trip_plan": state.trip_plan,
            "intent": "plan_trip",
            "tools_used": [],
            "travel_context": {},
            "error": None,
        }
        final_state = await run_graph_call(agent.invoke, fallback_state, config=graph_config)
    plan = final_state.get("trip_plan")
    if plan:
        _update_decision_report(session_id, plan, final_state.get("travel_context", {}))

    response_text = _latest_ai_text(final_state)
    history = list(state.conversation_history)
    if response_text:
        history.append({"role": "assistant", "content": response_text})
        store.save_history(session_id, history)

    latest = store.get_or_create(session_id)
    return {
        "status": "completed",
        "response": response_text,
        "plan": _to_serializable(latest.trip_plan),
        "decision": _to_serializable(latest.decision),
        "itinerary": latest.itinerary,
        "tools_used": final_state.get("tools_used", []),
    }

    # Gửi lệnh kích hoạt agent tìm kiếm chi tiết
    # Client sẽ gọi stream endpoint với tin nhắn này để hiển thị trực tiếp cho user
    trigger_message = "Kế hoạch đã được xác nhận. Hãy tiến hành tìm kiếm chi tiết khách sạn, thời tiết và tính toán chi phí thực tế cho tôi."
    return {
        "status": "confirmed",
        "trigger_message": trigger_message,
        "plan": _to_serializable(state.trip_plan),
    }


@router.patch(
    "/trips/{session_id}/plan",
    tags=["Trips"],
    summary="Cập nhật trực tiếp các trường trong TripPlan (HITL)",
)
async def patch_trip_plan(session_id: str, patch_data: dict = Body(...)):
    """
    Cập nhật trực tiếp TripPlan từ Form chỉnh sửa phía UI.
    Sau khi cập nhật, tự động tính toán lại chi phí & rủi ro để cập nhật giao diện ngay lập tức.
    """
    store = get_session_store()
    state = store.get_or_create(session_id)

    if not state.trip_plan:
        raise HTTPException(status_code=400, detail="Không tìm thấy kế hoạch du lịch để cập nhật.")

    try:
        # Merge dữ liệu patch vào plan hiện tại
        current_data = state.trip_plan.model_dump()

        # Update nested dates
        if "dates" in patch_data and patch_data["dates"]:
            current_data["dates"] = {**current_data.get("dates", {}), **patch_data["dates"]}
        
        # Update nested budget
        if "budget" in patch_data and patch_data["budget"]:
            current_data["budget"] = {**current_data.get("budget", {}), **patch_data["budget"]}

        # Update flat fields
        for field in ["origin", "destination", "travelers", "trip_type", "comfort_level", "preferences", "must_have", "avoid", "special_requirements"]:
            if field in patch_data and patch_data[field] is not None:
                current_data[field] = patch_data[field]

        # Reset status về draft khi sửa đổi để cần xác nhận lại
        current_data["status"] = TripStatus.DRAFT

        # Validate lại bằng Pydantic
        updated_plan = TripPlan(**current_data)
        
        # Đồng bộ và cập nhật decision report
        _update_decision_report(session_id, updated_plan, {})

        return {
            "status": "success",
            "plan": _to_serializable(store.get_or_create(session_id).trip_plan),
            "decision": _to_serializable(store.get_or_create(session_id).decision),
        }
    except Exception as e:
        logger.exception("Lỗi khi patch TripPlan")
        raise HTTPException(status_code=422, detail=f"Dữ liệu không hợp lệ: {str(e)}")
