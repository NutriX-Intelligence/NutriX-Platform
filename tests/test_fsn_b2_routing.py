"""FSN B2 routing rule: which frames keep YOLO's answer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fsn_b2_routing as b2  # noqa: E402

INDIAN = {"idli", "kulfi"}


def r(yolo, conf, gt, vlm="unknown", canon="", supp=False):
    return dict(yolo=yolo, yolo_conf=conf, gt=gt, hybrid_vlm=vlm, hybrid_vlm_canon=canon, suppressed=supp, leak_free=True)


def test_indian_low_conf_kept_above_c():
    x = r("idli", 0.35, "idli", vlm="dosa")
    assert b2.correct(x, None, INDIAN) == 0.0      # no rule: falls back, VLM wrong
    assert b2.correct(x, 0.3, INDIAN) == 1.0       # rule keeps YOLO
    assert b2.correct(x, 0.4, INDIAN) == 0.0       # below c: falls back


def test_non_indian_and_suppressed_not_routed():
    assert b2.correct(r("apple", 0.35, "apple", vlm="pear"), 0.1, INDIAN) == 0.0
    assert b2.correct(r("kulfi", 0.9, "kulfi", vlm="ice cream", supp=True), 0.1, INDIAN) == 0.0


def test_above_threshold_unchanged_and_resolved_canon_counts():
    assert b2.correct(r("idli", 0.8, "idli"), 0.4, INDIAN) == 1.0
    assert b2.correct(r("apple", 0.2, "apple", vlm="red fruit", canon="Apple"), 0.4, INDIAN) == 1.0


def test_n_overridden():
    rows = [r("idli", 0.35, "idli"), r("idli", 0.15, "idli"), r("idli", 0.7, "idli"), r("apple", 0.35, "apple")]
    assert b2.n_overridden(rows, 0.1, INDIAN) == 2 and b2.n_overridden(rows, 0.3, INDIAN) == 1
