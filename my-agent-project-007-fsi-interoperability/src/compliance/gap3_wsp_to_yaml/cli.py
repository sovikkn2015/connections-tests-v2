"""
Gap 3 — CLI (`python -m compliance.gap3_wsp_to_yaml`).

Single subcommand: scan-and-report.

Exit codes (frozen vocabulary — spec R6.3):
    0 — coverage OK (no gaps).
    1 — coverage gaps (unmapped sections or orphan rules).
    2 — CI-blocking (strict + orphan, OR empty registry).
    3 — wsp_ingest_failed
    4 — registry_build_failed
    5 — argument_parse_failed
    6 — manifest_write_failed

See .kiro/specs/gap3-wsp-to-yaml.md R6.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from m2_m4_policy_engine import AuthorityPolicy

from compliance.gap3_wsp_to_yaml.coverage import build_coverage_report
from compliance.gap3_wsp_to_yaml.ingest import (
    LocalFileReader,
    WspIngestError,
    ingest_wsp_yaml,
)
from compliance.gap3_wsp_to_yaml.registry import MappingRegistry
from compliance.gap3_wsp_to_yaml.yaml_generator import generate_manifest

EXIT_OK = 0
EXIT_GAPS = 1
EXIT_CI_BLOCK = 2
EXIT_INGEST_FAILED = 3
EXIT_REGISTRY_FAILED = 4
EXIT_ARGPARSE_FAILED = 5
EXIT_WRITE_FAILED = 6

FROZEN_REASONS: frozenset[str] = frozenset(
    {
        "wsp_ingest_failed",
        "registry_build_failed",
        "manifest_write_failed",
        "argument_parse_failed",
    }
)


def _print_reason(reason: str) -> None:
    if reason not in FROZEN_REASONS:
        reason = "argument_parse_failed"
    sys.stderr.write(f"gap3: {reason}\n")


def _print_debug_class(exc: BaseException) -> None:
    """R5.4: debug output is exception class name ONLY."""
    sys.stderr.write(f"gap3: debug: {exc.__class__.__name__}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m compliance.gap3_wsp_to_yaml",
        description="Gap 3 WSP-to-YAML compliance mapping tool.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "scan-and-report",
        help="Ingest WSP doc, join with M2 rule_table, emit manifest + "
        "coverage report.",
    )
    scan.add_argument("--wsp-file", required=True, type=str)
    scan.add_argument("--output", required=False, type=str, default=None)
    scan.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 2) if any orphan Rego rule exists.",
    )
    scan.add_argument(
        "--debug",
        action="store_true",
        help="Print exception class on error (no message/traceback).",
    )
    return parser


def _run_scan_and_report(args: argparse.Namespace) -> int:
    reader = LocalFileReader()

    # Step 1: ingest.
    try:
        sections = ingest_wsp_yaml(reader, args.wsp_file)
    except WspIngestError as exc:
        _print_reason("wsp_ingest_failed")
        if args.debug:
            _print_debug_class(exc)
        return EXIT_INGEST_FAILED
    except Exception as exc:  # defense in depth
        _print_reason("wsp_ingest_failed")
        if args.debug:
            _print_debug_class(exc)
        return EXIT_INGEST_FAILED

    # Step 2: build registry.
    try:
        registry = MappingRegistry.from_m2(AuthorityPolicy(), sections)
    except Exception as exc:
        _print_reason("registry_build_failed")
        if args.debug:
            _print_debug_class(exc)
        return EXIT_REGISTRY_FAILED

    # Step 3: coverage report.
    report = build_coverage_report(registry, strict=args.strict)

    # Step 4: optional manifest write.
    if args.output:
        try:
            manifest = generate_manifest(
                registry,
                generated_at=datetime.now(timezone.utc).replace(microsecond=0),
                last_updated_by="gap3-cli",
            )
            Path(args.output).write_text(manifest, encoding="utf-8")
        except Exception as exc:
            _print_reason("manifest_write_failed")
            if args.debug:
                _print_debug_class(exc)
            return EXIT_WRITE_FAILED

    # Step 5: print one-line summary.
    summary = (
        f"gap3: total_wsp={report.total_wsp_sections} "
        f"total_rules={report.total_rules} "
        f"mapped={report.mapped_sections} "
        f"unmapped={len(report.unmapped_sections)} "
        f"orphans={len(report.orphan_rules)} "
        f"coverage_pct={report.coverage_pct} "
        f"exit={report.exit_code}"
    )
    sys.stdout.write(summary + "\n")
    return report.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry. Returns exit code instead of calling sys.exit() so
    tests can invoke main() with capsys."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse calls sys.exit on error. We map any exit to our
        # frozen argparse code (5) and print a frozen reason.
        _print_reason("argument_parse_failed")
        # If argparse asked for help (exit 0), preserve that.
        if exc.code == 0:
            return 0
        return EXIT_ARGPARSE_FAILED
    except Exception:
        _print_reason("argument_parse_failed")
        return EXIT_ARGPARSE_FAILED

    if args.command == "scan-and-report":
        return _run_scan_and_report(args)

    _print_reason("argument_parse_failed")
    return EXIT_ARGPARSE_FAILED


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
