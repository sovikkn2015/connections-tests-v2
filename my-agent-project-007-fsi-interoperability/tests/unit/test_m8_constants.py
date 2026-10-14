"""Task 3 -- STAGE_NAMES / HITL_GATES / PIPELINE_NAMES invariants."""

from m8_pipeline_engine import (
    HITL_GATES,
    PIPELINE_NAMES,
    STAGE_NAMES,
    VALID_REASON_CODES,
)


def test_stage_names_count():
    assert len(STAGE_NAMES) == 23


def test_hitl_gates_exact():
    assert HITL_GATES == frozenset({7, 13, 21})


def test_pipeline_names_count():
    assert len(PIPELINE_NAMES) == 4
    for n in PIPELINE_NAMES:
        assert n.startswith("m8.research_")


def test_bijective_stage_numbering():
    nums = sorted(int(n.split("_")[1]) for n in STAGE_NAMES)
    assert nums == list(range(1, 24))


def test_stage_12_rename():
    assert "stage_12_cross_source_synthesis" in STAGE_NAMES
    assert "stage_12_sentiment_synthesis" not in STAGE_NAMES


def test_stage_21_rename():
    assert "stage_21_anti_fabrication_check" in STAGE_NAMES
    assert "stage_21_final_approval_gate" not in STAGE_NAMES


def test_valid_reason_codes_count():
    assert len(VALID_REASON_CODES) == 20


def test_all_reason_codes_m8_prefixed():
    for c in VALID_REASON_CODES:
        assert c.startswith("m8_")
