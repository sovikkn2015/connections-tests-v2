"""
M7 Schema Translators — Abstract Base

Defines the translator interface that every vendor translator MUST implement.
Rule 8: Every translator has to_canonical() and from_canonical().
Rule 16: No cross-module imports. M7 imports only from M3 (canonical types).

NOTE on reconciliation: The ``reconciliation`` field on canonical types is
populated by the reconciliation service when merging multi-vendor data for the
same entity, NOT by individual translators.  Single-source translations
correctly set ``reconciliation=None``.  See DECISION-LOG 2026-04-16.

Python 3.12+ / Pydantic v2.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

# Generic type variables for canonical and vendor types
CanonicalT = TypeVar("CanonicalT", bound=BaseModel)
VendorT = TypeVar("VendorT", bound=dict[str, Any])


# ---------------------------------------------------------------------------
# Shared helper functions — used by ALL M7 translators (ISSUE 7 dedup)
# ---------------------------------------------------------------------------

def parse_uuid(val: Any) -> UUID | None:
    """Safely parse a UUID from string, returning None on failure."""
    if val is None:
        return None
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return None


def parse_date(val: Any) -> date | None:
    """Parse a date from string (ISO format), returning None on failure."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, AttributeError):
        return None


def parse_datetime(val: Any) -> datetime | None:
    """Parse a datetime from string (ISO format), returning None on failure."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        s = str(val)
        if "+" in s and not s.endswith("Z"):
            s = s.replace("+0000", "+00:00")
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def safe_float(val: Any) -> float | None:
    """Safely convert to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def map_time_horizon(val: Any) -> str | None:
    """Map vendor time horizon values to canonical enum."""
    if val is None:
        return None
    v = str(val).lower().replace(" ", "_")
    if v in {"short_term", "medium_term", "long_term"}:
        return v
    if "short" in v:
        return "short_term"
    if "long" in v:
        return "long_term"
    return "medium_term"


def utcnow() -> datetime:
    """Return timezone-aware UTC now (Python 3.12+ compatible).

    Replaces deprecated ``datetime.utcnow()`` — ISSUE 10.
    """
    return datetime.now(timezone.utc)


class BaseTranslator(ABC, Generic[CanonicalT]):
    """Abstract base for all M7 vendor translators.

    Each vendor translator subclasses this and implements to_canonical/from_canonical
    for every canonical type it maps. The source_system property identifies the vendor.
    """

    @property
    @abstractmethod
    def source_system(self) -> str:
        """Vendor source system identifier (e.g., 'salesforce_fsc', 'orion', 'schwab')."""
        ...

    @abstractmethod
    def to_canonical(self, vendor_data: dict[str, Any]) -> CanonicalT:
        """Convert vendor-specific data dict to a canonical Pydantic model.

        Args:
            vendor_data: Raw vendor data as a dictionary.

        Returns:
            Validated canonical Pydantic model instance.

        Raises:
            ValueError: If required fields are missing or invalid.
            ValidationError: If Pydantic validation fails.
        """
        ...

    @abstractmethod
    def from_canonical(self, canonical: CanonicalT) -> dict[str, Any]:
        """Convert canonical Pydantic model back to vendor-specific data dict.

        Args:
            canonical: Validated canonical Pydantic model instance.

        Returns:
            Vendor-specific data dictionary for write-back.

        Raises:
            ValueError: If canonical data cannot be mapped to vendor format.
        """
        ...


class MultiTypeTranslator(ABC):
    """Base for translators that handle multiple canonical types.

    Most vendor translators map several vendor objects to different canonical types.
    This base provides the source_system property and leaves type-specific
    translate_* methods to the subclass.

    NOTE: ``reconciliation`` is populated by the reconciliation service when
    merging multi-vendor data, not by individual translators.
    """

    @property
    @abstractmethod
    def source_system(self) -> str:
        """Vendor source system identifier."""
        ...

    def _require_field(self, data: dict[str, Any], field: str, context: str = "") -> Any:
        """Extract a required field from vendor data, raising ValueError if missing."""
        val = data.get(field)
        if val is None:
            ctx = f" ({context})" if context else ""
            raise ValueError(f"Required field '{field}' is missing or null{ctx}")
        return val

    def _optional_field(self, data: dict[str, Any], field: str, default: Any = None) -> Any:
        """Extract an optional field from vendor data with a default."""
        return data.get(field, default)
