"""Entry point for `python -m compliance.gap3_wsp_to_yaml`."""

from __future__ import annotations

import sys

from compliance.gap3_wsp_to_yaml.cli import main

if __name__ == "__main__":
    sys.exit(main())
