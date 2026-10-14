"""
Cross-module gate: M7 can ingest a PascalCase SFDC fixture.

Spec §Known Blockers row 14 (v0.2.0 — the row-number corrected per NI-1).
Currently EXPECTED TO FAIL — documents the SHARED-WITH-M7 PascalCase gap
and blocks pre-prod deployment of the SFDC adapter until M7 resolves it
(alias-map on `SalesforceFSCAccountContact` or alias-transformer helper).

Marked xfail so pytest exits 0; when M7 fixes it, remove the xfail.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from m7_schema_translators.salesforce_fsc.models import SalesforceFSCAccountContact


def _pascal_case_sfdc_account() -> dict[str, object]:
    """Minimal fixture of real SFDC Account REST shape (PascalCase keys)."""
    return {
        "Id": "001A000001234567",
        "Name": "Placeholder Name",
        "RecordTypeName": "PersonAccount",
        "OwnerId": "005A000000000001",
        "CreatedDate": "2024-01-01T00:00:00Z",
        "LastModifiedDate": "2024-06-01T00:00:00Z",
        "FinServ__FirmId__c": "firm-42",
        "FinServ__HouseholdId__c": "001H000000000001",
        "FinServ__Jurisdiction__c": "US",
    }


@pytest.mark.xfail(
    reason=(
        "SHARED-WITH-M7 gap: M7 SalesforceFSCAccountContact uses snake_case with "
        "extra='forbid' and no Pydantic aliases; SFDC returns PascalCase. "
        "M7 must add populate_by_name=True + Field(alias=...) or an "
        "alias-transformer helper. Tracked in spec §Known Blockers row 14."
    ),
    strict=True,
)
def test_m7_ingests_pascal_case_sfdc_payload() -> None:
    with pytest.raises(ValidationError):
        SalesforceFSCAccountContact(**_pascal_case_sfdc_account())
    # The assertion below asserts ingestion SUCCEEDS; together with strict xfail,
    # this test will fail CI the moment M7 is fixed — at which point remove the
    # xfail marker.
    SalesforceFSCAccountContact(**_pascal_case_sfdc_account())
