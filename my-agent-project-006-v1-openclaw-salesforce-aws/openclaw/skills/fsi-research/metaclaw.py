"""
MetaClaw — cross-run learning for the FSI research pipeline.

Stores lessons from pipeline failures and successes as local JSON files.
Lessons are used to provide advice to future runs for the same ticker/stage.

MNPI rule: lesson detail must NEVER contain holdings amounts, trade
intentions, wire details, or any material non-public information.
Only operational metadata (stage failures, error types, recovery info).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("metaclaw")

LESSONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "metaclaw_lessons")
MAX_LESSONS = 1000


def _ensure_dir() -> None:
    """Create the lessons directory if it doesn't exist."""
    os.makedirs(LESSONS_DIR, exist_ok=True)


def _lesson_path(run_id: str, stage: int, ts: str) -> str:
    """Build a filename for a lesson: {run_id}_{stage}_{timestamp}.json."""
    safe_ts = ts.replace(":", "-").replace("+", "p")
    return os.path.join(LESSONS_DIR, f"{run_id}_{stage}_{safe_ts}.json")


def _enforce_limit() -> None:
    """Delete oldest lessons when the directory exceeds MAX_LESSONS files."""
    try:
        files = [
            f for f in os.listdir(LESSONS_DIR)
            if f.endswith(".json")
        ]
    except OSError:
        return

    if len(files) <= MAX_LESSONS:
        return

    # Sort by filename (contains timestamp) and remove oldest
    files.sort()
    to_remove = files[: len(files) - MAX_LESSONS]
    for fname in to_remove:
        try:
            os.remove(os.path.join(LESSONS_DIR, fname))
        except OSError:
            pass


def record_lesson(
    run_id: str,
    stage: int,
    lesson_type: str,
    detail: str,
    severity: str = "info",
    ticker: str = "",
) -> dict:
    """
    Record a lesson from a pipeline run.

    Parameters
    ----------
    run_id : str
        Pipeline run identifier.
    stage : int
        Pipeline stage number (1-23).
    lesson_type : str
        One of "error", "warning", "success", "recovery".
    detail : str
        Human-readable description. Must NOT contain MNPI data.
    severity : str
        "info", "warning", or "error".
    ticker : str
        Ticker symbol for the run.

    Returns
    -------
    dict
        The stored lesson record.
    """
    _ensure_dir()
    ts = datetime.now(timezone.utc).isoformat()
    lesson = {
        "run_id": run_id,
        "stage": stage,
        "lesson_type": lesson_type,
        "detail": detail,
        "severity": severity,
        "ticker": ticker,
        "timestamp": ts,
    }
    path = _lesson_path(run_id, stage, ts)
    try:
        with open(path, "w") as f:
            json.dump(lesson, f, indent=2)
        logger.info("MetaClaw lesson recorded: %s stage=%d type=%s", run_id, stage, lesson_type)
    except OSError as exc:
        logger.error("Failed to write lesson: %s", exc)
        return {"error": True, "message": str(exc)}

    _enforce_limit()
    return lesson


def get_lessons(
    ticker: str | None = None,
    stage: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve relevant lessons, optionally filtered by ticker and/or stage.

    Parameters
    ----------
    ticker : str, optional
        Filter by ticker symbol.
    stage : int, optional
        Filter by pipeline stage number.
    limit : int
        Maximum number of lessons to return (newest first).

    Returns
    -------
    list[dict]
        Matching lesson records, sorted newest-first.
    """
    _ensure_dir()
    lessons: list[dict] = []
    try:
        files = sorted(os.listdir(LESSONS_DIR), reverse=True)
    except OSError:
        return []

    for fname in files:
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(LESSONS_DIR, fname)) as f:
                lesson = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if ticker and lesson.get("ticker", "").upper() != ticker.upper():
            continue
        if stage is not None and lesson.get("stage") != stage:
            continue

        lessons.append(lesson)
        if len(lessons) >= limit:
            break

    return lessons


def apply_lessons(ticker: str, stage: int) -> list[str]:
    """
    Get applicable advice for a specific stage based on past lessons.

    Returns a list of human-readable advice strings derived from
    previous failures, recoveries, and successes for the same
    ticker and stage combination.

    Parameters
    ----------
    ticker : str
        Ticker symbol.
    stage : int
        Pipeline stage number.

    Returns
    -------
    list[str]
        Advice strings from past lessons.
    """
    past = get_lessons(ticker=ticker, stage=stage, limit=10)
    advice: list[str] = []
    for lesson in past:
        lt = lesson.get("lesson_type", "")
        detail = lesson.get("detail", "")
        run_id = lesson.get("run_id", "?")
        if lt == "error":
            advice.append(f"[WARN] Previous failure in run {run_id}: {detail}")
        elif lt == "recovery":
            advice.append(f"[INFO] Recovered in run {run_id}: {detail}")
        elif lt == "success":
            advice.append(f"[OK] Succeeded in run {run_id}: {detail}")
        elif lt == "warning":
            advice.append(f"[WARN] Warning from run {run_id}: {detail}")
    return advice
