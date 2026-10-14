"""
Execution Specialist — FastAPI REST endpoints.

POST /order/create       — Create a new trade order
POST /order/{id}/approve — HITL approve an order
POST /order/{id}/reject  — HITL reject an order
POST /order/{id}/submit  — Submit approved order for execution
GET  /order/{id}         — Get order by ID
GET  /health             — Health check

No cross-module imports. No credentials in code.
"""

import logging

from fastapi import FastAPI, HTTPException

try:
    from .state_machine import ExecutionStateMachine
    from .models import OrderRequest, OrderState
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _base = _pathlib.Path(__file__).parent
    _sm_spec = importlib.util.spec_from_file_location("execution_sm_local", _base / "state_machine.py")
    _sm_mod = importlib.util.module_from_spec(_sm_spec)
    _sm_spec.loader.exec_module(_sm_mod)
    ExecutionStateMachine = _sm_mod.ExecutionStateMachine
    _m_spec = importlib.util.spec_from_file_location("execution_models_local2", _base / "models.py")
    _m_mod = importlib.util.module_from_spec(_m_spec)
    _m_spec.loader.exec_module(_m_mod)
    OrderRequest = _m_mod.OrderRequest
    OrderState = _m_mod.OrderState

logger = logging.getLogger("execution_specialist.app")


def create_app() -> FastAPI:
    """Create the Execution Specialist FastAPI application."""

    app = FastAPI(
        title="Execution Specialist",
        description=(
            "Trade order lifecycle state machine with mandatory HITL. "
            "Phase 3 module per ARCH-09."
        ),
        version="0.1.0",
    )

    sm = ExecutionStateMachine()
    app.state.state_machine = sm

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "execution-specialist", "version": "0.1.0"}

    @app.post("/order/create")
    async def create_order(request: OrderRequest):
        """Create a new trade order in DRAFT state."""
        try:
            order = sm.create_order(request)
            return order.model_dump()
        except Exception as e:
            logger.error("Order creation failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/order/{order_id}/approve")
    async def approve_order(order_id: str, approver_id: str):
        """HITL approve an order. Generates SHA-256 token."""
        try:
            order = sm.approve_order(order_id, approver_id)
            return order.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/order/{order_id}/reject")
    async def reject_order(order_id: str, approver_id: str):
        """HITL reject an order → CANCELLED."""
        try:
            order = sm.reject_order(order_id, approver_id)
            return order.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/order/{order_id}/submit")
    async def submit_order(order_id: str):
        """Submit approved order for execution. HITL mandatory."""
        try:
            order = sm.submit_order(order_id)
            return order.model_dump()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/order/{order_id}")
    async def get_order(order_id: str):
        """Get order by ID."""
        order = sm.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
        return order.model_dump()

    return app
