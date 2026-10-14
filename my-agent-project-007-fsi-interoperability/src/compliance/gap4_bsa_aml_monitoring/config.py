"""
Gap 4 — BsaAmlEngine orchestrator.

Wires the WindowStore, CTR monitor, SAR structuring monitor, and
AuditEmitter into a single fail-closed entry point. Honors the
BsaAmlConfig.enabled short-circuit: when disabled, every method is
a no-op with zero side effects (R6.1, R6.2).

Two entry points:
- `evaluate_post_trade(txn)` — records the txn, evaluates both
  monitors, emits audit entries for every alert. Used by M6's
  post-trade hook.
- `peek(txn)` — pure evaluation WITHOUT recording or audit
  emission. Used by M2 PolicyRule adapters so pre-trade gating does
  not double-count the current txn.

See .kiro/specs/gap4-bsa-aml-monitoring.md §2.3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from m5_config_loader import BsaAmlConfig

from compliance.gap4_bsa_aml_monitoring.audit_emitter import AuditEmitter
from compliance.gap4_bsa_aml_monitoring.models import (
    BsaAmlAlert,
    CashTransaction,
)
from compliance.gap4_bsa_aml_monitoring.monitors import (
    CtrMonitor,
    SarStructuringMonitor,
)
from compliance.gap4_bsa_aml_monitoring.window_store import WindowStore


class BsaAmlEngine:
    """BSA/AML orchestrator. Thread-safe because all state is the
    WindowStore (which is thread-safe) plus immutable attrs.
    """

    def __init__(
        self,
        *,
        config: Optional[BsaAmlConfig],
        store: WindowStore,
        clock: Callable[[], datetime],
        audit_emitter: Optional[AuditEmitter] = None,
    ) -> None:
        if not isinstance(store, WindowStore):
            raise TypeError("store must implement WindowStore Protocol")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._config = config
        self._store = store
        self._clock = clock
        self._emitter = audit_emitter
        self._ctr = CtrMonitor(store=store, config=config, clock=clock)
        self._sar = SarStructuringMonitor(
            store=store, config=config, clock=clock
        )

    @property
    def config(self) -> Optional[BsaAmlConfig]:
        return self._config

    @property
    def store(self) -> WindowStore:
        return self._store

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def peek(self, cash_txn: CashTransaction) -> tuple[BsaAmlAlert, ...]:
        """Non-mutating evaluation — no recording, no audit emission.

        Used by M2 PolicyRule adapters to score the current txn
        against historical store contents WITHOUT mutating state.
        """
        if self._config is None or not self._config.enabled:
            return ()
        if not isinstance(cash_txn, CashTransaction):
            raise TypeError("cash_txn must be CashTransaction")
        # Monitors already include the current txn in their window
        # iff the store doesn't yet have it — which is the non-mutating
        # case here.
        return (*self._ctr.evaluate(cash_txn), *self._sar.evaluate(cash_txn))

    def evaluate_post_trade(
        self, cash_txn: CashTransaction
    ) -> tuple[BsaAmlAlert, ...]:
        """Record + evaluate + emit.

        Post-trade pipeline:
          1. If config is None or disabled -> return () (no side effect).
          2. Record txn in the WindowStore.
          3. Run CtrMonitor, then SarStructuringMonitor.
          4. For every alert, emit one AuditEntry via AuditEmitter.
          5. Return the alerts.
        """
        if self._config is None or not self._config.enabled:
            return ()
        if not isinstance(cash_txn, CashTransaction):
            raise TypeError("cash_txn must be CashTransaction")

        # Record BEFORE evaluating so the monitors see the current
        # txn as part of their window.
        self._store.record((cash_txn.firm_id, cash_txn.client_id), cash_txn)

        alerts: tuple[BsaAmlAlert, ...] = (
            *self._ctr.evaluate(cash_txn),
            *self._sar.evaluate(cash_txn),
        )

        if self._emitter is not None:
            for alert in alerts:
                self._emitter.emit(
                    alert=alert,
                    actor_id="system:bsa_aml_engine",
                    cash_txn=cash_txn,
                )

        return alerts
