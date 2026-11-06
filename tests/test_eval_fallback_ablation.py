import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "eval_fallback_ablation", Path(__file__).resolve().parent.parent / "scripts" / "eval_fallback_ablation.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def test_clean_class_name_strips_local_name_suffix():
    assert ev.clean_class_name("ash gourd -kubhindo-") == "ash gourd"
    assert ev.clean_class_name("Sweet_Potato") == "sweet potato"


def test_match_synonyms_and_plurals():
    assert ev.is_match("eggplant", "brinjal")
    assert ev.is_match("bell pepper", "capsicum")
    assert ev.is_match("bananas", "banana")
    assert ev.is_match("sweet potato", "sweet potato -suthuni-")
    assert ev.is_match("palak paneer", "palakpaneer")


def test_match_rejects_vague_and_unknown():
    assert not ev.is_match("potato", "sweet potato")
    assert not ev.is_match("unknown", "apple")
    assert not ev.is_match("none", "apple")
    assert not ev.is_match("", "apple")


def test_bootstrap_ci_brackets_mean_and_is_deterministic():
    vals = [1.0] * 70 + [0.0] * 30
    m, lo, hi = ev.bootstrap_ci(vals, seed=1)
    assert m == 0.7 and lo < 0.7 < hi and 0.55 < lo and hi < 0.85
    assert ev.bootstrap_ci(vals, seed=1) == (m, lo, hi)


def test_paired_diff_positive_when_a_dominates():
    d, lo, hi = ev.paired_diff_ci([1] * 80 + [0] * 20, [1] * 50 + [0] * 50, seed=2)
    assert abs(d - 0.3) < 1e-9 and lo > 0


def test_single_class_of(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("3 0.5 0.5 0.1 0.1\n3 0.2 0.2 0.1 0.1\n")
    assert ev.single_class_of(f) == 3
    f.write_text("3 0.5 0.5 0.1 0.1\n4 0.2 0.2 0.1 0.1\n")
    assert ev.single_class_of(f) is None
