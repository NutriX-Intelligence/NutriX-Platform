"""FSN C3: H2 report on synthetic rows with hand-computed answers (tmp dir, removed by pytest)."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fsn_capture_logger as cl  # noqa: E402
import fsn_h2_report as h2  # noqa: E402


class FakeRefs:
    REF = {"apple": ("USDA FDC SR Legacy", "FDC_1", dict(kcal=52, protein=0.3, carbs=14, fat=0.2)),
           "idli": ("INDB", "ASC144", dict(kcal=130, protein=4, carbs=27, fat=0.5))}

    def get(self, name):
        return self.REF.get(name.lower())


DB = {"apple": 52.0, "idli": 140.0, "dosa": 160.0, "oreo": 483.0}


def _row(**k):
    return {**{c: "" for c in cl.H2_COLS}, "status": "ok", "is_packaged": "n", **k}


ROWS = [
    # A: right food, +5 g weight error -> decomposition: weight only
    _row(meal_log_id=1, food_name="Apple", source="yolo", weight_g=105, kcal=54.6, protein_g=0.3, carbs_g=14.7, fat_g=0.2,
         true_food="apple", ref_g=100, yolo_top1="apple", yolo_conf=0.9),
    # B: wrong food (dosa for idli), YOLO top-1 right but below 0.5
    _row(meal_log_id=2, food_name="Dosa", source="qwen", weight_g=98, kcal=156.8, protein_g=4, carbs_g=28, fat_g=4,
         true_food="idli", ref_g=100, yolo_top1="idli", yolo_conf=0.3),
    # C: packaged, label reference, logged from a 480 kcal estimate while the DB says 483
    _row(meal_log_id=3, food_name="Oreo", source="qwen", weight_g=30, kcal=144, protein_g=1.5, carbs_g=21, fat_g=6,
         true_food="oreo", ref_g=30, is_packaged="y", label_kcal_100g=480, label_protein_100g=5, label_carbs_100g=70,
         label_fat_100g=20, yolo_top1="cookie", yolo_conf=0.6),
    # D: no nutrition data, no MS1 record
    _row(meal_log_id=4, food_name="Chocolate Bar", source="no_nutrition_data", weight_g=40, kcal=0, protein_g=0, carbs_g=0,
         fat_g=0, true_food="chocolate bar", ref_g=40),
    _row(meal_log_id=5, status="skipped", food_name="Apple", source="yolo", weight_g=1, kcal=1),
]


def test_h2_report_by_hand(tmp_path):
    p = tmp_path / "H2_servings.csv"
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cl.H2_COLS)
        w.writeheader()
        w.writerows(ROWS)
    h2.main(["--csv", str(p), "--out-dir", str(tmp_path)], refs=FakeRefs(), db_kcal=lambda n: DB.get(n.lower()))
    s = json.loads((tmp_path / "H2_summary.json").read_text())
    assert (s["n_ok"], s["n_skipped"], s["n_with_yolo_record"], s["n_packaged"]) == (4, 1, 3, 1)
    i = s["identification"]
    assert i["yolo_only_t0.5"]["acc"] == pytest.approx(1 / 3, abs=1e-4)      # only A (B abstains, C wrong)
    assert i["yolo_raw_top1"]["acc"] == pytest.approx(2 / 3, abs=1e-4)
    assert i["pipeline_logged"]["acc"] == 0.75                               # A, C, D right; B wrong
    assert s["weight_error_g"]["n"] == 4 and s["weight_error_g"]["bias"] == 0.75   # +5, -2, 0, 0
    e = s["energy_macro_error_per_serving"]["all"]["kcal"]
    assert e["n"] == 3 and e["bias"] == 9.8 and e["MAE"] == 9.8              # 2.6, 26.8, 0.0
    d = s["decomposition"]
    assert d["n"] == 3
    assert d["composition"]["mean_kcal"] == 3.63        # (0 + 10 + 0.9) / 3
    assert d["identification"]["mean_kcal"] == 6.67     # (0 + 20 + 0) / 3
    assert d["weight"]["mean_kcal"] == -0.2             # (2.6 - 3.2 + 0) / 3
    assert d["macro_source"]["mean_kcal"] == -0.3       # (0 + 0 - 0.9) / 3
    assert d["identification"]["share_of_abs_pct"] == 53.2    # 20 / 37.6
    assert [r["meal_log_id"] for r in s["no_nutrition_data"]] == ["4"]
    assert s["unmatched_reference"] == []
    per = list(csv.DictReader(open(tmp_path / "H2_per_serving.csv")))
    b = next(r for r in per if r["meal_log_id"] == "2")
    assert float(b["composition"]) + float(b["identification"]) + float(b["weight"]) + float(b["macro_source"]) == pytest.approx(float(b["total"]))


def test_real_reference_resolver_finds_indb_and_usda():
    if not (h2.INDB.exists() and (h2.OUT / "fdc_reference_per100g.csv").exists()):
        pytest.skip("INDB / FDC reference files not present")
    r = h2.References()
    assert r.get("Idli")[0] == "INDB" and r.get("idli")[1] == "ASC144"
    assert r.get("apple")[0].startswith("USDA") and r.get("apple")[2]["kcal"] == 52.0
    assert r.get("spaceship pie") is None
