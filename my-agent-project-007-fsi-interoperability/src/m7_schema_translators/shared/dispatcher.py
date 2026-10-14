"""
TranslatorPair — frozen dataclass describing a registered translator.

Per AC2.5: every registry entry carries `module_path` so CI can verify
import-reachability invariant: `importlib.import_module(pair.module_path)`
succeeds for every entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class TranslatorPair:
    """A registered (vendor, canonical_type) translator pair."""

    to_canonical: Callable[..., tuple[object, object]]
    from_canonical: Callable[..., tuple[object, object]]
    schema_version: str
    vendor_api_version: str
    module_path: str
