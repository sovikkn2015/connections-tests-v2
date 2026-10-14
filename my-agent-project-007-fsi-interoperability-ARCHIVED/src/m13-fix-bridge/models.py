"""
M13 FIX Bridge — Pydantic v2 models for FIX 4.2 protocol.

Stateful session management with sequence number tracking.
Separate module from M11 per ARCH-09.

No cross-module imports. No credentials in code.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class FIXSessionState(str, enum.Enum):
    """FIX session lifecycle states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    LOGGED_ON = "LOGGED_ON"
    ACTIVE = "ACTIVE"
    RESENDING = "RESENDING"
    LOGGED_OUT = "LOGGED_OUT"
    ERROR = "ERROR"


class FIXMessageType(str, enum.Enum):
    """FIX 4.2 message types supported by the bridge."""
    NEW_ORDER_SINGLE = "D"       # Tag 35=D
    EXECUTION_REPORT = "8"       # Tag 35=8
    ORDER_CANCEL_REQUEST = "F"   # Tag 35=F
    ALLOCATION = "J"             # Tag 35=J
    LOGON = "A"                  # Tag 35=A
    LOGOUT = "5"                 # Tag 35=5
    HEARTBEAT = "0"              # Tag 35=0
    RESEND_REQUEST = "2"         # Tag 35=2


# ── Session model ────────────────────────────────────────────────


class FIXSession(BaseModel):
    """Persistent FIX session with sequence number tracking."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_comp_id: str
    target_comp_id: str
    state: FIXSessionState = FIXSessionState.DISCONNECTED
    seq_num_out: int = Field(default=1, ge=1, description="Outbound sequence number")
    seq_num_in: int = Field(default=1, ge=1, description="Inbound sequence number")
    last_heartbeat_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    broker_name: str = ""


# ── FIX message models ───────────────────────────────────────────


class NewOrderSingle(BaseModel):
    """FIX NewOrderSingle (MsgType=D) — submit a new order."""
    cl_ord_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Client order ID")
    symbol: str = Field(..., description="Instrument symbol (Tag 55)")
    side: str = Field(..., pattern=r"^[12]$", description="1=Buy, 2=Sell (Tag 54)")
    order_type: str = Field(..., pattern=r"^[12]$", description="1=Market, 2=Limit (Tag 40)")
    quantity: float = Field(..., gt=0, description="Order quantity (Tag 38)")
    price: Optional[float] = Field(None, gt=0, description="Limit price (Tag 44, required for limit orders)")
    account: str = Field(..., description="Account identifier (Tag 1)")
    time_in_force: str = Field(default="0", description="0=Day, 1=GTC, 3=IOC (Tag 59)")


class ExecutionReport(BaseModel):
    """FIX ExecutionReport (MsgType=8) — fill, reject, ack."""
    exec_id: str = Field(..., description="Execution ID (Tag 17)")
    cl_ord_id: str = Field(..., description="Client order ID (Tag 11)")
    order_id: str = Field(..., description="Exchange order ID (Tag 37)")
    exec_type: str = Field(..., pattern=r"^[01248]$", description="0=New, 1=Partial, 2=Fill, 4=Cancel, 8=Reject (Tag 150)")
    ord_status: str = Field(..., description="Order status (Tag 39)")
    symbol: str = Field(..., description="Instrument symbol (Tag 55)")
    side: str = Field(..., pattern=r"^[12]$", description="1=Buy, 2=Sell (Tag 54)")
    quantity: float = Field(..., gt=0, description="Order quantity (Tag 38)")
    price: float = Field(..., ge=0, description="Price (Tag 44)")
    leaves_qty: float = Field(..., ge=0, description="Remaining quantity (Tag 151)")
    cum_qty: float = Field(..., ge=0, description="Cumulative filled quantity (Tag 14)")
    avg_px: float = Field(..., ge=0, description="Average fill price (Tag 6)")


class OrderCancelRequest(BaseModel):
    """FIX OrderCancelRequest (MsgType=F) — cancel an existing order."""
    orig_cl_ord_id: str = Field(..., description="Original client order ID to cancel (Tag 41)")
    cl_ord_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="New client order ID for cancel (Tag 11)")
    symbol: str = Field(..., description="Instrument symbol (Tag 55)")
    side: str = Field(..., pattern=r"^[12]$", description="1=Buy, 2=Sell (Tag 54)")


class FIXBridgeConfig(BaseModel):
    """Configuration for a FIX bridge connection."""
    broker_host: str = Field(..., description="Broker FIX engine hostname")
    broker_port: int = Field(..., ge=1, le=65535, description="Broker FIX engine port")
    sender_comp_id: str = Field(..., description="Our CompID (Tag 49)")
    target_comp_id: str = Field(..., description="Broker CompID (Tag 56)")
    heartbeat_interval: int = Field(default=30, ge=1, description="Heartbeat interval in seconds")
    state_backend: str = Field(default="memory", pattern=r"^(memory|postgresql|dynamodb)$", description="Session state persistence backend")
