"""
M13 FIX Bridge — QuickFIX/Python integration layer.

Wraps QuickFIX/Python to provide FIX 4.2 connectivity to broker engines.
Implements quickfix.Application interface and bridges callbacks to
FIXSessionManager state transitions.

Dev mode: QuickFIX is NOT imported. Class is a no-op that logs warnings.
Production mode: Lazily imports quickfix and manages the FIX engine lifecycle.

No cross-module imports. No credentials in code.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from .session_manager import FIXSessionManager
    from .models import (
        ExecutionReport,
        FIXBridgeConfig,
        FIXSessionState,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib

    _base = _pathlib.Path(__file__).parent

    _sm_spec = importlib.util.spec_from_file_location(
        "fix_sm_qf", _base / "session_manager.py"
    )
    _sm_mod = importlib.util.module_from_spec(_sm_spec)
    _sm_spec.loader.exec_module(_sm_mod)
    FIXSessionManager = _sm_mod.FIXSessionManager

    _m_spec = importlib.util.spec_from_file_location(
        "fix_models_qf", _base / "models.py"
    )
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    ExecutionReport = _m_mod.ExecutionReport
    FIXBridgeConfig = _m_mod.FIXBridgeConfig
    FIXSessionState = _m_mod.FIXSessionState

logger = logging.getLogger("m13_fix_bridge.quickfix_engine")

_DEV_MODE = not os.environ.get("FIX_BROKER_HOST", "")


class FIXEngine:
    """QuickFIX/Python engine wrapper.

    In production mode, implements quickfix.Application and manages the
    FIX initiator lifecycle. In dev mode, all methods are no-ops that
    log warnings.

    Usage:
        engine = FIXEngine(session_manager)
        engine.start(config)   # connects to broker
        engine.stop()          # graceful shutdown
    """

    def __init__(self, session_manager: FIXSessionManager) -> None:
        self._session_mgr = session_manager
        self._quickfix: Any = None
        self._initiator: Any = None
        self._settings: Any = None
        self._store_factory: Any = None
        self._log_factory: Any = None
        self._session_id_map: dict[str, Any] = {}  # our session_id → quickfix SessionID
        self._running = False

        if _DEV_MODE:
            logger.warning("QuickFIX not available — dev mode")
        else:
            self._lazy_import_quickfix()

    def _lazy_import_quickfix(self) -> None:
        """Import quickfix only in production mode."""
        try:
            import quickfix  # type: ignore[import-untyped]
            self._quickfix = quickfix
            logger.info("QuickFIX/Python loaded successfully")
        except ImportError:
            logger.error(
                "quickfix package not installed. "
                "Install with: pip install quickfix"
            )
            raise

    # ------------------------------------------------------------------
    # quickfix.Application interface
    # ------------------------------------------------------------------

    def onCreate(self, session_id: Any) -> None:
        """Called when a FIX session is created (not yet connected)."""
        logger.info("QuickFIX session created: %s", session_id)

    def onLogon(self, session_id: Any) -> None:
        """Called when logon is successful — sync state to LOGGED_ON."""
        qf_sid = str(session_id)
        logger.info("QuickFIX logon: %s", qf_sid)

        our_sid = self._find_our_session_id(qf_sid)
        if our_sid:
            session = self._session_mgr.get_session(our_sid)
            if session and session.state in (
                FIXSessionState.DISCONNECTED,
                FIXSessionState.CONNECTING,
            ):
                session.state = FIXSessionState.LOGGED_ON
                session.connected_at = datetime.now(timezone.utc)
                session.last_heartbeat_at = datetime.now(timezone.utc)

    def onLogout(self, session_id: Any) -> None:
        """Called on logout — sync state to LOGGED_OUT."""
        qf_sid = str(session_id)
        logger.info("QuickFIX logout: %s", qf_sid)

        our_sid = self._find_our_session_id(qf_sid)
        if our_sid:
            session = self._session_mgr.get_session(our_sid)
            if session and session.state not in (
                FIXSessionState.DISCONNECTED,
                FIXSessionState.LOGGED_OUT,
            ):
                session.state = FIXSessionState.LOGGED_OUT

    def toAdmin(self, message: Any, session_id: Any) -> None:
        """Called for outbound admin messages (Logon, Logout, Heartbeat).

        Sync outbound sequence number from QuickFIX to session_manager.
        """
        if _DEV_MODE:
            return

        qf = self._quickfix
        our_sid = self._find_our_session_id(str(session_id))

        if our_sid:
            session = self._session_mgr.get_session(our_sid)
            if session:
                try:
                    seq_num = int(
                        message.getHeader().getField(qf.MsgSeqNum().getTag())
                    )
                    session.seq_num_out = seq_num
                except Exception:
                    pass

        logger.debug("toAdmin: session=%s", session_id)

    def fromAdmin(self, message: Any, session_id: Any) -> None:
        """Called for inbound admin messages.

        Sync inbound sequence number and update heartbeat timestamp.
        """
        if _DEV_MODE:
            return

        qf = self._quickfix
        our_sid = self._find_our_session_id(str(session_id))

        if our_sid:
            session = self._session_mgr.get_session(our_sid)
            if session:
                try:
                    seq_num = int(
                        message.getHeader().getField(qf.MsgSeqNum().getTag())
                    )
                    session.seq_num_in = seq_num
                except Exception:
                    pass
                session.last_heartbeat_at = datetime.now(timezone.utc)

        logger.debug("fromAdmin: session=%s", session_id)

    def toApp(self, message: Any, session_id: Any) -> None:
        """Called for outbound application messages (NewOrderSingle, etc).

        Sync outbound sequence number.
        """
        if _DEV_MODE:
            return

        our_sid = self._find_our_session_id(str(session_id))
        if our_sid:
            session = self._session_mgr.get_session(our_sid)
            if session:
                qf = self._quickfix
                try:
                    seq_num = int(
                        message.getHeader().getField(qf.MsgSeqNum().getTag())
                    )
                    session.seq_num_out = seq_num
                except Exception:
                    pass

        logger.debug("toApp: session=%s", session_id)

    def fromApp(self, message: Any, session_id: Any) -> None:
        """Called for inbound application messages (ExecutionReport, etc).

        Parses ExecutionReports and feeds them to session_manager.
        """
        if _DEV_MODE:
            return

        qf = self._quickfix
        msg_type = message.getHeader().getField(qf.MsgType().getTag())
        our_sid = self._find_our_session_id(str(session_id))

        if msg_type == "8" and our_sid:  # ExecutionReport
            report = self._parse_execution_report(message)
            if report:
                try:
                    self._session_mgr.receive_execution_report(our_sid, report)
                except ValueError as exc:
                    logger.error("Failed to process ExecutionReport: %s", exc)
        else:
            logger.info(
                "fromApp: unhandled msg_type=%s session=%s", msg_type, session_id
            )

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def start(self, config: FIXBridgeConfig) -> Optional[str]:
        """Start the QuickFIX initiator and connect to broker.

        Returns the internal session_id, or None in dev mode.
        """
        if _DEV_MODE:
            logger.warning("FIXEngine.start() called in dev mode — no-op")
            return None

        qf = self._quickfix

        # Build QuickFIX settings
        settings_str = self._build_settings_string(config)
        self._settings = qf.SessionSettings(settings_str)
        self._store_factory = qf.FileStoreFactory(self._settings)
        self._log_factory = qf.FileLogFactory(self._settings)

        self._initiator = qf.SocketInitiator(
            self,  # Application interface
            self._store_factory,
            self._settings,
            self._log_factory,
        )

        # Create session in manager
        session = self._session_mgr.create_session(config)
        qf_session_id = qf.SessionID(
            "FIX.4.2",
            config.sender_comp_id,
            config.target_comp_id,
        )
        self._session_id_map[session.session_id] = qf_session_id

        self._initiator.start()
        self._running = True
        logger.info(
            "QuickFIX initiator started: %s → %s:%d",
            config.sender_comp_id,
            config.broker_host,
            config.broker_port,
        )
        return session.session_id

    def stop(self) -> None:
        """Stop the QuickFIX initiator gracefully."""
        if _DEV_MODE:
            logger.warning("FIXEngine.stop() called in dev mode — no-op")
            return

        if self._initiator and self._running:
            self._initiator.stop()
            self._running = False
            logger.info("QuickFIX initiator stopped")

    @property
    def is_running(self) -> bool:
        """Whether the engine is currently running."""
        return self._running

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_our_session_id(self, qf_session_id_str: str) -> Optional[str]:
        """Map a QuickFIX SessionID string back to our internal session_id."""
        for our_id, qf_id in self._session_id_map.items():
            if str(qf_id) == qf_session_id_str:
                return our_id
        return None

    def _parse_execution_report(self, message: Any) -> Optional[ExecutionReport]:
        """Parse a QuickFIX message into an ExecutionReport model."""
        if _DEV_MODE:
            return None

        try:
            def _get(tag: int, default: str = "") -> str:
                try:
                    return message.getField(tag)
                except Exception:
                    return default

            return ExecutionReport(
                exec_id=_get(17),                    # ExecID
                cl_ord_id=_get(11),                  # ClOrdID
                order_id=_get(37),                   # OrderID
                exec_type=_get(150),                 # ExecType
                ord_status=_get(39),                 # OrdStatus
                symbol=_get(55),                     # Symbol
                side=_get(54),                       # Side
                quantity=float(_get(38, "0")),        # OrderQty
                price=float(_get(44, "0")),           # Price
                leaves_qty=float(_get(151, "0")),     # LeavesQty
                cum_qty=float(_get(14, "0")),         # CumQty
                avg_px=float(_get(6, "0")),           # AvgPx
            )
        except Exception as exc:
            logger.error("Failed to parse ExecutionReport: %s", exc)
            return None

    @staticmethod
    def _build_settings_string(config: FIXBridgeConfig) -> str:
        """Build a QuickFIX settings INI string from config."""
        return (
            "[DEFAULT]\n"
            "ConnectionType=initiator\n"
            "ReconnectInterval=5\n"
            f"HeartBtInt={config.heartbeat_interval}\n"
            "StartTime=00:00:00\n"
            "EndTime=00:00:00\n"
            "UseDataDictionary=Y\n"
            "DataDictionary=FIX42.xml\n"
            "FileStorePath=./fix_store\n"
            "FileLogPath=./fix_log\n"
            "\n"
            "[SESSION]\n"
            "BeginString=FIX.4.2\n"
            f"SenderCompID={config.sender_comp_id}\n"
            f"TargetCompID={config.target_comp_id}\n"
            f"SocketConnectHost={config.broker_host}\n"
            f"SocketConnectPort={config.broker_port}\n"
        )
