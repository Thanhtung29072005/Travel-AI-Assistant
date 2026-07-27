"""
Session Store - Quản lý lưu trữ trạng thái phiên chat (TripPlan & Decision Report)
Lưu trữ trên cơ sở dữ liệu Microsoft SQL Server chuyên nghiệp.
"""
from __future__ import annotations

import json
import logging
import threading
import dataclasses
from typing import Optional, Any

from app.models.trip_plan import TripPlan
from app.services.calculator import DecisionReport, CostEstimate, CostBreakdown, RiskItem, RiskLevel
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class SessionState:
    """Trạng thái đầy đủ của một phiên chat"""
    def __init__(self, session_id: str, trip_plan: Optional[TripPlan] = None, decision: Optional[DecisionReport] = None):
        self.session_id = session_id
        self.trip_plan = trip_plan
        self.decision = decision
        self.conversation_history: list = []  # Phục vụ lưu vết chat tạm thời nếu cần


def _deserialize_decision_report(data_dict: dict) -> DecisionReport:
    """Khôi phục đối tượng dataclass DecisionReport từ dictionary JSON"""
    # 1. Khôi phục Breakdown
    b = data_dict["cost_estimate"]["breakdown"]
    breakdown = CostBreakdown(
        flight_per_person=float(b.get("flight_per_person", 0)),
        accommodation_per_night=float(b.get("accommodation_per_night", 0)),
        food_per_person_per_day=float(b.get("food_per_person_per_day", 0)),
        transport_local_total=float(b.get("transport_local_total", 0)),
        activities_total=float(b.get("activities_total", 0)),
        misc_buffer=float(b.get("misc_buffer", 0))
    )
    
    # 2. Khôi phục CostEstimate
    ce = data_dict["cost_estimate"]
    cost_estimate = CostEstimate(
        destination=ce.get("destination", ""),
        travelers=int(ce.get("travelers", 1)),
        days=int(ce.get("days", 1)),
        comfort_level=ce.get("comfort_level", "medium"),
        breakdown=breakdown,
        total_per_person=float(ce.get("total_per_person", 0)),
        total_all_people=float(ce.get("total_all_people", 0)),
        budget_provided=float(ce.get("budget_provided", 0)),
        budget_gap=float(ce.get("budget_gap", 0)),
        currency=ce.get("currency", "VND"),
        disclaimer=ce.get("disclaimer", "")
    )
    
    # 3. Khôi phục danh sách Risks
    risks = []
    for r in data_dict.get("risks", []):
        risks.append(RiskItem(
            category=r.get("category", "budget"),
            level=RiskLevel(r.get("level", "low")),
            title=r.get("title", ""),
            detail=r.get("detail", ""),
            suggestion=r.get("suggestion", "")
        ))
        
    return DecisionReport(
        cost_estimate=cost_estimate,
        risks=risks,
        overall_risk=RiskLevel(data_dict.get("overall_risk", "low")),
        recommendation=data_dict.get("recommendation", "")
    )


class SessionStore:
    """SQL Server Session Store (Singleton)"""
    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False

    def _get_connection(self):
        """Khởi tạo kết nối trực tiếp đến SQL Server bằng pymssql với phân tích động tham số"""
        import pymssql
        
        server_str = settings.sql_server or settings.sql_server_host or "localhost"
        host = "localhost"
        port = settings.sql_server_port or 1433
        
        # Hỗ trợ định dạng "host.docker.internal,1433"
        if "," in server_str:
            parts = server_str.split(",", 1)
            host = parts[0].strip()
            try:
                port = int(parts[1].strip())
            except ValueError:
                pass
        else:
            host = server_str
            
        user = settings.sql_username or settings.sql_server_user or "sa"
        password = settings.sql_password or settings.sql_server_password or ""
        
        # Khử dấu ngoặc kép bọc chuỗi (nếu có từ file .env)
        if isinstance(host, str) and host.startswith('"') and host.endswith('"'):
            host = host[1:-1]
        if isinstance(user, str) and user.startswith('"') and user.endswith('"'):
            user = user[1:-1]
        if isinstance(password, str) and password.startswith('"') and password.endswith('"'):
            password = password[1:-1]
            
        return pymssql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=settings.sql_server_database,
            autocommit=True
        )

    def _initialize_db(self) -> None:
        """Tự động kiểm tra, khởi tạo Database và cấu trúc bảng trên SQL Server"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return
            
            import pymssql
            
            # Bước 1: Kết nối cơ sở dữ liệu hệ thống (master) để tạo database nếu chưa có
            try:
                master_conn = pymssql.connect(
                    host=settings.sql_server_host,
                    port=settings.sql_server_port,
                    user=settings.sql_server_user,
                    password=settings.sql_server_password,
                    database="master",
                    autocommit=True
                )
                with master_conn.cursor() as cursor:
                    # Kiểm tra sự tồn tại của database
                    cursor.execute(
                        "SELECT database_id FROM sys.databases WHERE name = %s",
                        (settings.sql_server_database,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        logger.info(f"[DB INIT] Database '{settings.sql_server_database}' does not exist. Creating...")
                        cursor.execute(f"CREATE DATABASE [{settings.sql_server_database}]")
                master_conn.close()
            except Exception as e:
                logger.warning(f"[DB INIT] Could not verify database existence from master: {e}. Will try direct connection.")

            # Bước 2: Kết nối database mục tiêu để tạo bảng lưu trữ
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("""
                        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='sessions' AND xtype='U')
                        BEGIN
                            CREATE TABLE sessions (
                                session_id VARCHAR(100) PRIMARY KEY,
                                trip_plan_json NVARCHAR(MAX) NULL,
                                decision_json NVARCHAR(MAX) NULL,
                                history_json NVARCHAR(MAX) NULL,
                                created_at DATETIME NOT NULL DEFAULT GETDATE(),
                                updated_at DATETIME NOT NULL DEFAULT GETDATE()
                            );
                        END
                        ELSE
                        BEGIN
                            IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('sessions') AND name = 'history_json')
                            BEGIN
                                ALTER TABLE sessions ADD history_json NVARCHAR(MAX) NULL;
                            END
                        END
                    """)
                conn.close()
                self._initialized = True
                logger.info("[DB INIT] SQL Server persistence initialized successfully.")
            except Exception as e:
                logger.error(f"[DB INIT] Failed to initialize tables on SQL Server: {e}")
                raise e

    def get_or_create(self, session_id: str) -> SessionState:
        """Lấy trạng thái phiên làm việc hiện tại từ SQL Server hoặc tạo mới nếu chưa có"""
        self._initialize_db()
        conn = self._get_connection()
        state = SessionState(session_id)
        
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT trip_plan_json, decision_json, history_json FROM sessions WHERE session_id = %s",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                plan_json, decision_json, history_json = row[0], row[1], row[2]
                if plan_json:
                    state.trip_plan = TripPlan.model_validate_json(plan_json)
                if decision_json:
                    state.decision = _deserialize_decision_report(json.loads(decision_json))
                if history_json:
                    try:
                        state.conversation_history = json.loads(history_json)
                    except Exception:
                        state.conversation_history = []
            else:
                # Tạo mới dòng trạng thái
                cursor.execute(
                    "INSERT INTO sessions (session_id, trip_plan_json, decision_json, history_json) VALUES (%s, NULL, NULL, NULL)",
                    (session_id,)
                )
        conn.close()
        return state

    def save_trip_plan(self, session_id: str, plan: TripPlan) -> None:
        """Ghi đè/cập nhật kế hoạch TripPlan vào SQL Server"""
        self._initialize_db()
        conn = self._get_connection()
        plan_json = plan.model_dump_json()
        
        with conn.cursor() as cursor:
            cursor.execute("""
                MERGE INTO sessions AS target
                USING (SELECT %s AS session_id) AS source
                ON target.session_id = source.session_id
                WHEN MATCHED THEN
                    UPDATE SET trip_plan_json = %s, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (session_id, trip_plan_json, decision_json)
                    VALUES (source.session_id, %s, NULL);
            """, (session_id, plan_json, plan_json))
        conn.close()

    def save_decision(self, session_id: str, decision: DecisionReport) -> None:
        """Ghi đè/cập nhật DecisionReport thẩm định vào SQL Server"""
        self._initialize_db()
        conn = self._get_connection()
        decision_json = json.dumps(dataclasses.asdict(decision), ensure_ascii=False)
        
        with conn.cursor() as cursor:
            cursor.execute("""
                MERGE INTO sessions AS target
                USING (SELECT %s AS session_id) AS source
                ON target.session_id = source.session_id
                WHEN MATCHED THEN
                    UPDATE SET decision_json = %s, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (session_id, trip_plan_json, decision_json)
                    VALUES (source.session_id, NULL, %s);
            """, (session_id, decision_json, decision_json))
        conn.close()

    def save_history(self, session_id: str, history: list[dict]) -> None:
        """Ghi đè/cập nhật lịch sử chat (list of dicts) vào SQL Server"""
        self._initialize_db()
        conn = self._get_connection()
        history_json = json.dumps(history, ensure_ascii=False)
        
        with conn.cursor() as cursor:
            cursor.execute("""
                MERGE INTO sessions AS target
                USING (SELECT %s AS session_id) AS source
                ON target.session_id = source.session_id
                WHEN MATCHED THEN
                    UPDATE SET history_json = %s, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (session_id, trip_plan_json, decision_json, history_json)
                    VALUES (source.session_id, NULL, NULL, %s);
            """, (session_id, history_json, history_json))
        conn.close()

    def clear(self, session_id: str) -> None:
        """Xóa sạch dữ liệu phiên làm việc khỏi SQL Server"""
        self._initialize_db()
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        conn.close()


# Singleton instance
_session_store = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
