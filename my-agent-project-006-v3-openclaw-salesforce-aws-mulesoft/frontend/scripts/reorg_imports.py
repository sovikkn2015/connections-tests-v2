#!/usr/bin/env python3
"""
Post-reorg import rewriter.

Walks every .ts/.tsx file under frontend/src and frontend/tests, rewrites
imports to match the new layout:

  src/shared/{types,store,hooks,lib,data,components}/
  src/v1/{components,personas,styles}/
  src/v2/{atoms,personas,styles}/
  src/App.tsx
  src/main.tsx

Caller location → path remap:

  src/v1/components/*       ../{store,types,hooks,lib,data}/X → ../../shared/{same}/X
  src/v1/personas/*/*       ../../{store,types,hooks,lib,data}/X → ../../../shared/{same}/X
                            ../../components/{Shared4}         → ../../../shared/components/{Shared4}
                            ../../components/X                 → ../../components/X (v1-internal, unchanged)
  src/v2/atoms/*            ../../{store,types,hooks,lib,data,components}/X → ../../shared/{same}/X
  src/v2/personas/*         ../../{store,types,hooks,lib,data,components}/X → ../../shared/{same}/X
  src/v2/V2App.tsx          ../{store,types,hooks,lib,data,components}/X → ../shared/{same}/X
                            ../styles/v2-{name}.css → ./styles/{name}.css
  src/App.tsx               ./personas/... → ./v1/personas/...
                            ./{store,types,hooks,lib,data}/X → ./shared/{same}/X
  src/main.tsx              ./styles/{v1-name}.css → ./v1/styles/{v1-name}.css
  src/shared/hooks/useTopologyData.ts  ../components/TraversalMap → ../types/topology
  src/shared/hooks/useTraversalState.tsx  ../components/TraversalMap → ../types/topology
  tests/unit/v2/*           already ../../../src/v2/...  (unchanged)
  tests/unit/components/*   ../../../src/components/{Shared4} → ../../../src/shared/components/{Shared4}
                            ../../../src/components/X → ../../../src/v1/components/X
  tests/unit/{hooks,lib,data,store}/* ../../../src/{X}/ → ../../../src/shared/{X}/
  tests/integration/*       ../../src/personas/ → ../../src/v1/personas/
                            ../../src/{store,hooks,lib,data,types}/ → ../../src/shared/{same}/
                            ../../src/components/{Shared4} → ../../src/shared/components/{Shared4}
                            ../../src/components/X → ../../src/v1/components/X

Idempotent — safe to re-run.
"""

import os
import re
import sys
from pathlib import Path

SHARED4 = {"ErrorBoundary", "StreamingText", "SkeletonTool", "CitationChip"}
SHARED_DIRS = ("store", "types", "hooks", "lib", "data")


def rewrite_v1_components(src: str) -> str:
    """Files in src/v1/components/ — use ../../shared/DIR/ for shared imports."""
    # Handle partial pre-rewrite from smartRelocate: '../shared/DIR/' (invalid
    # at this depth) → '../../shared/DIR/'
    src = re.sub(
        r"from (['\"])\.\./shared/(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    # '../(DIR)/...' → '../../shared/(DIR)/...'
    return re.sub(
        r"from (['\"])\.\./(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )


def rewrite_v1_persona_nested(src: str) -> str:
    """Files in src/v1/personas/<persona>/*.tsx — one level deeper than components."""
    # Handle partial pre-rewrite: '../../shared/DIR/' (invalid at this depth)
    # → '../../../shared/DIR/'
    src = re.sub(
        r"from (['\"])\.\./\.\./shared/(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../../../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    # '../../(DIR)/...' → '../../../shared/(DIR)/...'
    src = re.sub(
        r"from (['\"])\.\./\.\./(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../../../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    # '../../components/(Shared4)...' → '../../../shared/components/(Shared4)...'
    src = re.sub(
        r"from (['\"])\.\./\.\./components/(" + "|".join(SHARED4) + r")(.*?)\1",
        lambda m: f"from {m.group(1)}../../../shared/components/{m.group(2)}{m.group(3)}{m.group(1)}",
        src,
    )
    return src


def rewrite_v2_atoms_or_personas(src: str) -> str:
    """Files in src/v2/atoms/*.tsx or src/v2/personas/*.tsx.
    Change ../../DIR/ → ../../shared/DIR/ for shared dirs including components.
    """
    dirs = SHARED_DIRS + ("components",)
    src = re.sub(
        r"from (['\"])\.\./\.\./(" + "|".join(dirs) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    return src


def rewrite_v2_app(src: str) -> str:
    """src/v2/V2App.tsx — one level deep under src/."""
    dirs = SHARED_DIRS + ("components",)
    src = re.sub(
        r"from (['\"])\.\./(" + "|".join(dirs) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}../shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    # '../styles/v2-NAME.css' → './styles/NAME.css' (moved into v2/styles/ and stripped prefix)
    src = re.sub(
        r"(['\"])\.\./styles/v2-(tokens|header|map|timeline|gates|personas)\.css\1",
        lambda m: f"{m.group(1)}./styles/{m.group(2)}.css{m.group(1)}",
        src,
    )
    return src


def rewrite_src_app(src: str) -> str:
    """src/App.tsx — ./personas/... → ./v1/personas/... and shared remaps."""
    src = re.sub(
        r"from (['\"])\./personas/(.+?)\1",
        lambda m: f"from {m.group(1)}./v1/personas/{m.group(2)}{m.group(1)}",
        src,
    )
    src = re.sub(
        r"from (['\"])\./(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}./shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    return src


def rewrite_src_main(src: str) -> str:
    """src/main.tsx — relocate v1 CSS imports."""
    src = re.sub(
        r"(['\"])\./styles/(global|research|advisor|client|traversal-map)\.css\1",
        lambda m: f"{m.group(1)}./v1/styles/{m.group(2)}.css{m.group(1)}",
        src,
    )
    return src


def rewrite_shared_hooks_topology_ref(src: str) -> str:
    """Extract topology types dependency — shared hooks must not depend on v1."""
    src = src.replace(
        "from '../components/TraversalMap'",
        "from '../types/topology'",
    )
    src = src.replace(
        'from "../components/TraversalMap"',
        'from "../types/topology"',
    )
    return src


def rewrite_test_file(src: str, test_depth: str) -> str:
    """Tests at tests/unit/* (depth 'unit') and tests/integration/* (depth 'integration')."""
    if test_depth == "unit":
        prefix = "../../../src"
    else:
        prefix = "../../src"
    # prefix/components/{Shared4} → prefix/shared/components/{Shared4}
    src = re.sub(
        rf"from (['\"])(?:\.\./)+src/components/(" + "|".join(SHARED4) + r")(.*?)\1",
        lambda m: f"from {m.group(1)}{prefix}/shared/components/{m.group(2)}{m.group(3)}{m.group(1)}",
        src,
    )
    # prefix/components/X → prefix/v1/components/X
    src = re.sub(
        rf"from (['\"])(?:\.\./)+src/components/(.+?)\1",
        lambda m: f"from {m.group(1)}{prefix}/v1/components/{m.group(2)}{m.group(1)}",
        src,
    )
    # prefix/personas/... → prefix/v1/personas/...
    src = re.sub(
        rf"from (['\"])(?:\.\./)+src/personas/(.+?)\1",
        lambda m: f"from {m.group(1)}{prefix}/v1/personas/{m.group(2)}{m.group(1)}",
        src,
    )
    # prefix/DIR/X → prefix/shared/DIR/X
    src = re.sub(
        rf"from (['\"])(?:\.\./)+src/(" + "|".join(SHARED_DIRS) + r")/(.+?)\1",
        lambda m: f"from {m.group(1)}{prefix}/shared/{m.group(2)}/{m.group(3)}{m.group(1)}",
        src,
    )
    return src


def process_file(path: Path, repo_root: Path):
    rel = path.relative_to(repo_root)
    rel_posix = str(rel).replace(os.sep, "/")
    src = path.read_text()
    original = src

    if rel_posix == "src/App.tsx":
        src = rewrite_src_app(src)
    elif rel_posix == "src/main.tsx":
        src = rewrite_src_main(src)
    elif rel_posix == "src/v2/V2App.tsx":
        src = rewrite_v2_app(src)
    elif rel_posix.startswith("src/v1/components/"):
        src = rewrite_v1_components(src)
    elif rel_posix.startswith("src/v1/personas/"):
        src = rewrite_v1_persona_nested(src)
    elif rel_posix.startswith("src/v2/atoms/") or rel_posix.startswith("src/v2/personas/"):
        src = rewrite_v2_atoms_or_personas(src)
    elif rel_posix.startswith("src/shared/hooks/"):
        src = rewrite_shared_hooks_topology_ref(src)
    elif rel_posix.startswith("tests/unit/"):
        src = rewrite_test_file(src, "unit")
    elif rel_posix.startswith("tests/integration/"):
        src = rewrite_test_file(src, "integration")

    if src != original:
        path.write_text(src)
        print(f"  rewrote {rel_posix}")


def main():
    repo_root = Path(__file__).resolve().parent.parent  # frontend/
    for root_dir in ("src", "tests"):
        base = repo_root / root_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".ts", ".tsx"):
                process_file(path, repo_root)


if __name__ == "__main__":
    main()
