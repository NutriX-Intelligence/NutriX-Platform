"""FSN C1 capture logger: skip / undo / resume without duplicates (no DB: fake meal_logs source)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fsn_capture_logger as cl  # noqa: E402


def _m(i, w=100.0, src="esp32_yolo", kcal=52.0):
    return dict(id=i, user_id=1, log_date="2026-11-06", food_name="Apple", calories=kcal, protein=0.3, carbs=14.0,
                fat=0.2, weight_g=w, source=src)


class FakeSrc:
    def __init__(self, rows):
        self.rows = rows

    def after(self, after_id):
        return [r for r in self.rows if r["id"] > after_id]

    def by_id(self, mid):
        return next((r for r in self.rows if r["id"] == mid), None)


def _inp(answers):
    it = iter(answers)

    def f(prompt):
        try:
            return next(it)
        except StopIteration:
            raise KeyboardInterrupt          # what Ctrl+C at a prompt looks like
    return f


def test_scale_skip_undo_and_resume(tmp_path):
    led = cl.Ledger(tmp_path / "h1.csv", cl.H1_COLS)
    src = FakeSrc([_m(11, 50.2), _m(12, 99.8), _m(13, 200.0)])
    answers = ["obj1", "50", "1",            # #11 saved
               "obj2", "undo",               # undo removes #11 -> asked again
               "obj1", "50", "2",            # #11 re-saved (trial corrected)
               "obj2", "100", "1",           # #12 saved
               "skip"]                       # #13 skipped
    cl.run("scale", led, src, inp=_inp(answers), start_after=10, poll_s=0, stop_when_empty=True)
    rows = led.rows()
    assert [(r["meal_log_id"], r["status"], r["trial"]) for r in rows] == [("11", "ok", "2"), ("12", "ok", "1"), ("13", "skipped", "")]
    assert rows[0]["nutrix_g"] == "50.2" and rows[0]["ref_g"] == "50.0"
    # resume: rows already in the CSV are not asked again; a new capture is
    src.rows.append(_m(14, 300.0))
    cl.run("scale", led, src, inp=_inp(["obj3", "300", "1"]), start_after=10, poll_s=0, stop_when_empty=True)
    assert [r["meal_log_id"] for r in led.rows()] == ["11", "12", "13", "14"]


def test_ctrl_c_mid_entry_saves_nothing_for_that_capture(tmp_path):
    led = cl.Ledger(tmp_path / "h1.csv", cl.H1_COLS)
    src = FakeSrc([_m(1), _m(2)])
    with pytest.raises(KeyboardInterrupt):
        cl.run("scale", led, src, inp=_inp(["a", "10", "1", "b"]), start_after=0, poll_s=0, stop_when_empty=True)
    assert [r["meal_log_id"] for r in led.rows()] == ["1"]
    cl.run("scale", led, src, inp=_inp(["b", "20", "1"]), start_after=0, poll_s=0, stop_when_empty=True)
    assert [r["meal_log_id"] for r in led.rows()] == ["1", "2"]


def test_servings_packaged_and_capture_record(tmp_path):
    (tmp_path / "log").mkdir()
    (tmp_path / "log" / "21.json").write_text(json.dumps({
        "logged_at_utc": "2026-11-06T10:00:00Z", "image_path": "/x/21.jpg", "yolo_top1": "apple", "yolo_conf": 0.31,
        "conf_threshold": 0.5, "macro_source": "db",
        "vlm": {"food_name": "oreo", "confidence": 0.9, "flagged": False, "per_100g": {"calories": 480, "protein_g": 5, "carbs_g": 70, "fat_g": 20}}}))
    led = cl.Ledger(tmp_path / "h2.csv", cl.H2_COLS)
    src = FakeSrc([_m(21, 30.0, "esp32_qwen_vlm", 144.0), _m(22, 40.0, "no_nutrition_data", 0.0)])
    answers = ["oreo", "30.5", "maybe", "y", "480", "5.2", "71.9", "19.6",      # invalid y/n is re-asked
               "chocolate bar", "40", "n"]
    cl.run("servings", led, src, inp=_inp(answers), start_after=20, poll_s=0, log_dir=tmp_path / "log", stop_when_empty=True)
    r1, r2 = led.rows()
    assert r1["source"] == "qwen" and r1["yolo_top1"] == "apple" and r1["yolo_conf"] == "0.31" and r1["vlm_food"] == "oreo"
    assert r1["is_packaged"] == "y" and r1["label_kcal_100g"] == "480.0" and r1["image_path"] == "/x/21.jpg"
    assert r1["timestamp"] == "2026-11-06T10:00:00Z"
    assert r2["source"] == "no_nutrition_data" and r2["is_packaged"] == "n" and r2["label_kcal_100g"] == "" and r2["yolo_top1"] == ""


def test_ask_rejects_bad_numbers():
    assert cl.ask(_inp(["abc", "-1", "12.5"]), "", "float") == 12.5
    with pytest.raises(cl.Skip):
        cl.ask(_inp(["SKIP"]), "")


def test_undo_on_empty_ledger_is_harmless(tmp_path):
    led = cl.Ledger(tmp_path / "h1.csv", cl.H1_COLS)
    assert led.undo() is None
    cl.run("scale", led, FakeSrc([_m(5)]), inp=_inp(["undo", "o", "10", "1"]), start_after=0, poll_s=0, stop_when_empty=True)
    assert [r["meal_log_id"] for r in led.rows()] == ["5"]
