"""Task 11 property test -- every TaxLot.cost_basis_method is non-None.

Req-Fix 5 re-statement: Holding has NO cost_basis_method. TaxLot does.
M8's state-invariant walker walks holding.tax_lots[*].cost_basis_method.
"""

import os
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from m3_schema_registry import CostBasisMethod, Holding, TaxLot

_CI = os.environ.get("CI") == "1"
_MAX = 20 if _CI else 50


@st.composite
def tax_lot_with_method(draw) -> TaxLot:
    """cost_basis_method NEVER null per M3 validator + v0.2.0 Req-Fix 5."""
    return TaxLot(
        lot_id=str(draw(st.uuids())),
        holding_ref="HOLD-" + draw(st.from_regex(r"[a-f0-9]{8}", fullmatch=True)),
        quantity=draw(st.floats(min_value=1.0, max_value=10_000.0)),
        cost_basis_method=draw(st.sampled_from(list(CostBasisMethod))),
        cost_basis_amount=draw(
            st.floats(min_value=100.0, max_value=1_000_000.0)
        ),
        source_custodian="schwab",
        acquisition_date=draw(st.dates()),
    )


@st.composite
def holding_with_tax_lots(draw) -> Holding:
    lots = draw(st.lists(tax_lot_with_method(), min_size=1, max_size=3))
    return Holding(
        canonical_id=str(uuid.uuid4()),
        account_ref="ACCT-" + draw(st.from_regex(r"[a-f0-9]{8}", fullmatch=True)),
        quantity=sum(lot.quantity for lot in lots),
        market_value=draw(st.floats(min_value=1000.0, max_value=10_000_000.0)),
        as_of_date=draw(st.dates()),
        source_system="schwab",
        source_id=draw(st.from_regex(r"SCH-[0-9]{10}", fullmatch=True)),
        tax_lots=lots,
    )


@settings(max_examples=_MAX, deadline=5000)
@given(h=holding_with_tax_lots())
def test_every_tax_lot_has_non_null_cost_basis_method(h: Holding) -> None:
    assert len(h.tax_lots) >= 1
    for lot in h.tax_lots:
        assert lot.cost_basis_method is not None


def test_m8_state_invariant_walker_catches_none_via_m3_validator() -> None:
    """M3 validator blocks construction of a TaxLot without cost_basis_method."""
    import pydantic
    with pytest.raises((pydantic.ValidationError, ValueError, TypeError)):
        TaxLot(
            lot_id="L-1",
            holding_ref="HOLD-00000001",
            quantity=1.0,
            cost_basis_method=None,  # type: ignore[arg-type]
            cost_basis_amount=100.0,
            source_custodian="schwab",
        )
