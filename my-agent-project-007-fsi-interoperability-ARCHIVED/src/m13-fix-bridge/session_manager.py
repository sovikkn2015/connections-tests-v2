"""
M13 FIX Bridge — Session Manager.

Stateful FIX 4.2 session lifecycle with sequence number tracking.
In-memory store for dev/test. Production uses postgresql backend.

State transitions:
  DISCONNECTED → CONNECTING → LOGGED_ON → ACTIVE → LOGGED_OUT
  Any state → ERROR (on failure)
  LOGGED_ON/ACTIVE → RESENDING (gap-fill recovery)

No cross-module imports. No credentials in code.

Backends:
  In-memory (default) for dev/test.
  PostgreSQL for production (FIX_SESSION_BACKEND=postgresql, FIX_SESSION_DB_URL).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from .models import (
        ExecutionReport,
        FIXBridgeConfig,
        FIXSession,
        FIXSessionState,
        NewOrderSingle,
        OrderCancelRequest,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("fix_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ExecutionReport = _mod.ExecutionReport
    FIXBridgeConfig = _mod.FIXBridgeConfig
    FIXSession = _mod.FIXSession
    FIXSessionState = _mod.FIXSessionState
    NewOrderSingle = _mod.NewOrderSingle
    OrderCancelRequest = _mod.OrderCancelRequest

logger = logging.getLogger("m13_fix_bridge.session_manager")


# ── Session Store Backends ───────────────────────────────────────


class InMemoryFIXSessionStore:
    """In-memory FIX session store. Default for dev/test."""

    def __init__(self) -> None:
        self._sessions: dict[str, FIXSession] = {}
        self._execution_reports: dict[str, list[ExecutionReport]] = {}

    def put_session(self, session: FIXSession) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[FIXSession]:
        return self._sessions.get(session_id)

    def put_execution_report(self, cl_ord_id: str, report: ExecutionReport) -> None:
        if cl_ord_id not in self._execution_reports:
            self._execution_reports[cl_ord_id] = []
        self._execution_reports[cl_ord_id].append(report)

    def get_execution_reports(self, cl_ord_id: str) -> list[ExecutionReport]:
        return self._execution_reports.get(cl_ord_id, [])


class PostgresSessionStore:
    """
    PostgreSQL-backed FIX session store for production.

    Activated when FIX_SESSION_BACKEND=postgresql and FIX_SESSION_DB_URL is set.
    Uses asyncpg for async connection pooling. Schema auto-created on init.

    Rule 20: No credentials in code — connection string from env var only.
    Rule 11: M13 is stateful (StatefulSet + PersistentVolume).

    Falls back to in-memory on connection failure.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._fallback: InMemoryFIXSessionStore | None = None
        logger.info("PostgresSessionStore initialized")

    @classmethod
    async def create(cls, database_url: str) -> "PostgresSessionStore":
        """Factory: create pool + ensure schema exists."""
        try:
            import asyncpg
        except ImportError:
            raise RuntimeError(
                "asyncpg is required for PostgreSQL FIX session store. "
                "Install with: pip install asyncpg"
            )
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        instance = cls(pool)
        await instance._ensure_schema()
        return instance

    async def _ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS fix_sessions (
                    session_id   TEXT PRIMARY KEY,
                    session_json JSONB NOT NULL,
                    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS fix_execution_reports (
                    cl_ord_id    TEXT NOT NULL,
                    exec_id      TEXT NOT NULL,
                    report_json  JSONB NOT NULL,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (cl_ord_id, exec_id)
                )
            """)

    def _get_fallback(self) -> InMemoryFIXSessionStore:
        if self._fallback is None:
            self._fallback = InMemoryFIXSessionStore()
            logger.warning("PostgresSessionStore: activated in-memory fallback")
        return self._fallback

    def put_session(self, session: FIXSession) -> None:
        """Synchronous put — schedules async write."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._put_session_async(session))
        except RuntimeError:
            try:
                asyncio.run(self._put_session_async(session))
            except Exception as exc:
                logger.error("PostgreSQL put_session failed: %s. Using fallback.", exc)
                self._get_fallback().put_session(session)

    async def _put_session_async(self, session: FIXSession) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO fix_sessions (session_id, session_json, updated_at)
                    VALUES ($1, $2, now())
                    ON CONFLICT (session_id) DO UPDATE
                    SET session_json = $2, updated_at = now()
                    """,
                    session.session_id,
                    session.model_dump_json(),
                )
        except Exception as exc:
            logger.error("PostgreSQL put_session async failed: %s. Using fallback.", exc)
            self._get_fallback().put_session(session)

    def get_session(self, session_id: str) -> Optional[FIXSession]:
        """Synchronous get."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._get_session_async(session_id))
                return future.result()
        except RuntimeError:
            try:
                return asyncio.run(self._get_session_async(session_id))
            except Exception as exc:
                logger.error("PostgreSQL get_session failed: %s. Using fallback.", exc)
                return self._get_fallback().get_session(session_id)

    async def _get_session_async(self, session_id: str) -> Optional[FIXSession]:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT session_json FROM fix_sessions WHERE session_id = $1",
                    session_id,
                )
                if row is None:
                    if self._fallback:
                        return self._fallback.get_session(session_id)
                    return None
                return FIXSession.model_validate_json(row["session_json"])
        except Exception as exc:
            logger.error("PostgreSQL get_session async failed: %s. Using fallback.", exc)
            return self._get_fallback().get_session(session_id)

    def put_execution_report(self, cl_ord_id: str, report: ExecutionReport) -> None:
        """Synchronous put for execution report."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._put_report_async(cl_ord_id, report))
        except RuntimeError:
            try:
                asyncio.run(self._put_report_async(cl_ord_id, report))
            except Exception as exc:
                logger.error("PostgreSQL put_execution_report failed: %s. Using fallback.", exc)
                self._get_fallback().put_execution_report(cl_ord_id, report)

    async def _put_report_async(self, cl_ord_id: str, report: ExecutionReport) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO fix_execution_reports (cl_ord_id, exec_id, report_json)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (cl_ord_id, exec_id) DO NOTHING
                    """,
                    cl_ord_id,
                    report.exec_id,
                    report.model_dump_json(),
                )
        except Exception as exc:
            logger.error("PostgreSQL put_report async failed: %s. Using fallback.", exc)
            self._get_fallback().put_execution_report(cl_ord_id, report)

    def get_execution_reports(self, cl_ord_id: str) -> list[ExecutionReport]:
        """Synchronous get for execution reports."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._get_reports_async(cl_ord_id))
                return future.result()
        except RuntimeError:
            try:
                return asyncio.run(self._get_reports_async(cl_ord_id))
            except Exception as exc:
                logger.error("PostgreSQL get_execution_reports failed: %s. Using fallback.", exc)
                return self._get_fallback().get_execution_reports(cl_ord_id)

    async def _get_reports_async(self, cl_ord_id: str) -> list[ExecutionReport]:
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT report_json FROM fix_execution_reports WHERE cl_ord_id = $1 ORDER BY created_at",
                    cl_ord_id,
                )
                reports = [ExecutionReport.model_validate_json(row["report_json"]) for row in rows]
                if not reports and self._fallback:
                    return self._fallback.get_execution_reports(cl_ord_id)
                return reports
        except Exception as exc:
            logger.error("PostgreSQL get_reports async failed: %s. Using fallback.", exc)
            return self._get_fallback().get_execution_reports(cl_ord_id)


def create_fix_session_store() -> InMemoryFIXSessionStore | PostgresSessionStore:
    """
    Factory: select FIX session store backend based on env var.

    FIX_SESSION_BACKEND: "memory" (default) or "postgresql"
    FIX_SESSION_DB_URL: PostgreSQL connection string (required for postgresql)

    Note: PostgreSQL backend requires async init — use create_fix_session_store_async()
    for full async initialization. This sync factory returns in-memory as placeholder
    when postgresql is selected.
    """
    backend = os.environ.get("FIX_SESSION_BACKEND", "memory").lower()
    if backend == "postgresql":
        db_url = os.environ.get("FIX_SESSION_DB_URL")
        if not db_url:
            logger.warning(
                "FIX_SESSION_BACKEND=postgresql but FIX_SESSION_DB_URL not set. "
                "Falling back to in-memory session store."
            )
            return InMemoryFIXSessionStore()
        logger.info(
            "FIX session store backend: postgresql (async init required — "
            "call create_fix_session_store_async())"
        )
        return InMemoryFIXSessionStore()
    logger.info("FIX session store backend: memory")
    return InMemoryFIXSessionStore()


async def create_fix_session_store_async() -> InMemoryFIXSessionStore | PostgresSessionStore:
    """
    Async factory: select FIX session store backend based on env var.

    FIX_SESSION_BACKEND: "memory" (default) or "postgresql"
    FIX_SESSION_DB_URL: PostgreSQL connection string (required for postgresql)
    """
    backend = os.environ.get("FIX_SESSION_BACKEND", "memory").lower()
    if backend == "postgresql":
        db_url = os.environ.get("FIX_SESSION_DB_URL")
        if not db_url:
            logger.warning(
                "FIX_SESSION_BACKEND=postgresql but FIX_SESSION_DB_URL not set. "
                "Falling back to in-memory session store."
            )
            return InMemoryFIXSessionStore()
        try:
            store = await PostgresSessionStore.create(db_url)
            logger.info("FIX session store backend: postgresql (connected)")
            return store
        except Exception as exc:
            logger.error(
                "Failed to connect to PostgreSQL for FIX sessions: %s. "
                "Falling back to in-memory.",
                exc,
            )
            return InMemoryFIXSessionStore()
    logger.info("FIX session store backend: memory")
    return InMemoryFIXSessionStore()


class FIXSessionManager:
    """Manages FIX sessions with stateful sequence number tracking."""

    def __init__(self, store: InMemoryFIXSessionStore | PostgresSessionStore | None = None) -> None:
        self._store = store or InMemoryFIXSessionStore()

    # ── Session lifecycle ────────────────────────────────────────

    def _get_session_or_raise(self, session_id: str) -> FIXSession:
        """Retrieve session or raise ValueError."""
        session = self._store.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        return session

    def _require_state(self, session: FIXSession, *allowed: FIXSessionState) -> None:
        """Raise if session is not in one of the allowed states."""
        if session.state not in allowed:
            allowed_names = ", ".join(s.value for s in allowed)
            raise ValueError(
                f"Session {session.session_id} is in {session.state.value}, "
                f"expected one of: {allowed_names}"
            )

    def create_session(self, config: FIXBridgeConfig) -> FIXSession:
        """Create a new FIX session in DISCONNECTED state."""
        session = FIXSession(
            sender_comp_id=config.sender_comp_id,
            target_comp_id=config.target_comp_id,
            state=FIXSessionState.DISCONNECTED,
            broker_name=f"{config.broker_host}:{config.broker_port}",
        )
        self._store.put_session(session)
        logger.info("Session created: %s → %s", session.session_id, session.broker_name)
        return session

    def connect(self, session_id: str) -> FIXSession:
        """Connect session: DISCONNECTED → CONNECTING → LOGGED_ON.

        Increments seq_num_out for the Logon message.
        """
        session = self._get_session_or_raise(session_id)
        self._require_state(session, FIXSessionState.DISCONNECTED)

        # Transition through CONNECTING
        session.state = FIXSessionState.CONNECTING
        now = datetime.now(timezone.utc)

        # Send Logon (MsgType=A) — increment outbound sequence
        session.seq_num_out += 1
        session.state = FIXSessionState.LOGGED_ON
        session.connected_at = now
        session.last_heartbeat_at = now

        logger.info("Session connected: %s (seq_out=%d)", session_id, session.seq_num_out)
        return session

    def disconnect(self, session_id: str) -> FIXSession:
        """Disconnect session → LOGGED_OUT.

        Increments seq_num_out for the Logout message.
        """
        session = self._get_session_or_raise(session_id)
        self._require_state(
            session,
            FIXSessionState.LOGGED_ON,
            FIXSessionState.ACTIVE,
            FIXSessionState.RESENDING,
        )

        # Send Logout (MsgType=5) — increment outbound sequence
        session.seq_num_out += 1
        session.state = FIXSessionState.LOGGED_OUT

        logger.info("Session disconnected: %s (seq_out=%d)", session_id, session.seq_num_out)
        return session

    def send_new_order(self, session_id: str, order: NewOrderSingle) -> str:
        """Send NewOrderSingle — requires LOGGED_ON or ACTIVE state.

        Increments seq_num_out. Returns cl_ord_id.
        """
        session = self._get_session_or_raise(session_id)
        self._require_state(session, FIXSessionState.LOGGED_ON, FIXSessionState.ACTIVE)

        session.seq_num_out += 1
        # Transition to ACTIVE on first order
        if session.state == FIXSessionState.LOGGED_ON:
            session.state = FIXSessionState.ACTIVE

        logger.info(
            "NewOrderSingle sent: session=%s cl_ord_id=%s symbol=%s seq_out=%d",
            session_id, order.cl_ord_id, order.symbol, session.seq_num_out,
        )
        return order.cl_ord_id

    def send_cancel(self, session_id: str, cancel: OrderCancelRequest) -> str:
        """Send OrderCancelRequest — requires LOGGED_ON or ACTIVE state.

        Increments seq_num_out. Returns cl_ord_id.
        """
        session = self._get_session_or_raise(session_id)
        self._require_state(session, FIXSessionState.LOGGED_ON, FIXSessionState.ACTIVE)

        session.seq_num_out += 1

        logger.info(
            "OrderCancelRequest sent: session=%s orig=%s seq_out=%d",
            session_id, cancel.orig_cl_ord_id, session.seq_num_out,
        )
        return cancel.cl_ord_id

    def receive_execution_report(self, session_id: str, report: ExecutionReport) -> ExecutionReport:
        """Process inbound ExecutionReport — increments seq_num_in, stores report."""
        session = self._get_session_or_raise(session_id)
        self._require_state(
            session,
            FIXSessionState.LOGGED_ON,
            FIXSessionState.ACTIVE,
            FIXSessionState.RESENDING,
        )

        session.seq_num_in += 1

        # Store by cl_ord_id for retrieval
        self._store.put_execution_report(report.cl_ord_id, report)

        logger.info(
            "ExecutionReport received: session=%s exec_id=%s type=%s seq_in=%d",
            session_id, report.exec_id, report.exec_type, session.seq_num_in,
        )
        return report

    def heartbeat(self, session_id: str) -> FIXSession:
        """Send heartbeat — updates last_heartbeat_at, increments seq_num_out."""
        session = self._get_session_or_raise(session_id)
        self._require_state(
            session,
            FIXSessionState.LOGGED_ON,
            FIXSessionState.ACTIVE,
        )

        session.seq_num_out += 1
        session.last_heartbeat_at = datetime.now(timezone.utc)

        logger.info("Heartbeat: session=%s seq_out=%d", session_id, session.seq_num_out)
        return session

    def request_resend(self, session_id: str, begin_seq: int, end_seq: int) -> FIXSession:
        """Request resend for gap-fill recovery — state → RESENDING.

        begin_seq/end_seq define the sequence number range to request.
        end_seq=0 means infinity (all messages from begin_seq onward).
        """
        session = self._get_session_or_raise(session_id)
        self._require_state(session, FIXSessionState.LOGGED_ON, FIXSessionState.ACTIVE)

        if begin_seq < 1:
            raise ValueError("begin_seq must be >= 1")
        if end_seq != 0 and end_seq < begin_seq:
            raise ValueError("end_seq must be >= begin_seq or 0 (infinity)")

        session.seq_num_out += 1
        session.state = FIXSessionState.RESENDING

        logger.info(
            "ResendRequest: session=%s begin=%d end=%d seq_out=%d",
            session_id, begin_seq, end_seq, session.seq_num_out,
        )
        return session

    def get_session(self, session_id: str) -> Optional[FIXSession]:
        """Retrieve session by ID. Returns None if not found."""
        return self._store.get_session(session_id)

    def get_execution_reports(self, session_id: str, cl_ord_id: str) -> list[ExecutionReport]:
        """Get all execution reports for a given cl_ord_id."""
        # Validate session exists
        self._get_session_or_raise(session_id)
        return self._store.get_execution_reports(cl_ord_id)
