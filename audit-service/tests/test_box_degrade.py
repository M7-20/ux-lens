"""Tests for the "no box_2d from the provider must not drop the finding"
behaviour in engine.py and ux/ux_visual_checks.py — the downstream half of
the ministry VLM scan (see ux/ux_visual_checks.py).
Both modules keep their own independent copies of to_box()/dedup() by design
(see ux/ux_visual_checks.py's header comment on why) — this file mirrors
that and tests both copies rather than assuming they stay identical forever.
"""
import engine
from ux import ux_visual_checks


# engine.py's to_box: (box, had_box_field)

def test_engine_to_box_missing_field_returns_no_had_box():
    box, had_box = engine.to_box({"rule_id": "DGA-X"}, W=1000, th=1000, y0=0)
    assert box is None
    assert had_box is False


def test_engine_to_box_valid_box():
    box, had_box = engine.to_box({"box_2d": [100, 100, 200, 200]}, W=1000, th=1000, y0=0)
    assert had_box is True
    assert box is not None
    assert box[0] < box[2] and box[1] < box[3]


def test_engine_to_box_degenerate_box_dropped_but_had_box_true():
    # A 0px-wide box: box_2d WAS present, but it's nonsense — this is the
    # pre-existing Gemini-hallucination guard, unrelated to the ministry
    # provider's "no box at all" case, and must still be dropped.
    box, had_box = engine.to_box({"box_2d": [500, 500, 500, 501]}, W=1000, th=1000, y0=0)
    assert had_box is True
    assert box is None


def test_engine_to_box_malformed_types_treated_as_absent():
    for bad in ([1, 2, 3], "nope", None, [1, 2, "x", 4]):
        box, had_box = engine.to_box({"box_2d": bad}, W=1000, th=1000, y0=0)
        assert (box, had_box) == (None, False)


def test_engine_dedup_keeps_one_boxless_finding_per_rule_highest_confidence():
    viols = [
        {"box": None, "rule_id": "DGA-X", "conf": "منخفضة", "rec": None, "evidence": "a", "sev": "Warning"},
        {"box": None, "rule_id": "DGA-X", "conf": "عالية", "rec": "better", "evidence": "b", "sev": "Warning"},
        {"box": None, "rule_id": "DGA-Y", "conf": "متوسطة", "rec": None, "evidence": "c", "sev": "Error"},
    ]
    out = engine.dedup(viols, thr=0.5)
    by_rule = {v["rule_id"]: v for v in out}
    assert set(by_rule) == {"DGA-X", "DGA-Y"}
    assert by_rule["DGA-X"]["conf"] == "عالية"  # kept the higher-confidence one


def test_engine_dedup_still_merges_boxed_findings_by_iou():
    viols = [
        {"box": (10, 10, 100, 100), "rule_id": "DGA-X", "conf": "منخفضة", "rec": None, "evidence": "a", "sev": "Warning"},
        {"box": (12, 12, 102, 102), "rule_id": "DGA-X", "conf": "عالية", "rec": "better", "evidence": "b", "sev": "Warning"},
    ]
    out = engine.dedup(viols, thr=0.5)
    assert len(out) == 1
    assert out[0]["conf"] == "عالية"


def test_engine_dedup_mixed_boxed_and_boxless_both_survive():
    viols = [
        {"box": (10, 10, 100, 100), "rule_id": "DGA-X", "conf": "عالية", "rec": None, "evidence": "a", "sev": "Warning"},
        {"box": None, "rule_id": "DGA-Y", "conf": "منخفضة", "rec": None, "evidence": "b", "sev": "Warning"},
    ]
    out = engine.dedup(viols, thr=0.5)
    assert len(out) == 2


# ux/ux_visual_checks.py's independent copy of the same contract

def test_ux_to_box_missing_field_returns_no_had_box():
    box, had_box = ux_visual_checks.to_box({"rule_id": "UX-X"}, W=1000, th=1000, y0=0)
    assert (box, had_box) == (None, False)


def test_ux_to_box_valid_box():
    box, had_box = ux_visual_checks.to_box({"box_2d": [100, 100, 200, 200]}, W=1000, th=1000, y0=0)
    assert had_box is True
    assert box is not None


def test_ux_dedup_keeps_boxless_findings():
    viols = [
        {"box": None, "rule_id": "UX-X", "conf": "منخفضة", "rec": None, "evidence": "a"},
        {"box": None, "rule_id": "UX-X", "conf": "عالية", "rec": "better", "evidence": "b"},
    ]
    out = ux_visual_checks.dedup(viols, thr=0.5)
    assert len(out) == 1
    assert out[0]["conf"] == "عالية"
