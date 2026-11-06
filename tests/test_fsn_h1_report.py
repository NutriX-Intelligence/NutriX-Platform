"""FSN C2: H1 report on a synthetic CSV with hand-computed answers (written to pytest's tmp dir, removed after)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fsn_h1_report as h1  # noqa: E402

# object A ref 100: errors +1 +2 +3 (mean 2, SD 1); object B ref 200: errors -2 0 +2 (mean 0, SD 2)
ROWS = [("A", 100, 1, 101), ("A", 100, 2, 102), ("A", 100, 3, 103),
        ("B", 200, 1, 198), ("B", 200, 2, 200), ("B", 200, 3, 202), ("C", 50, 1, 70)]


def test_h1_report_by_hand(tmp_path):
    p = tmp_path / "H1_scale.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=h1_cols())
        w.writeheader()
        for i, (o, ref, t, nx) in enumerate(ROWS):
            w.writerow(dict(object_id=o, ref_g=ref, trial=t, nutrix_g=nx, meal_log_id=i, timestamp="", status="skipped" if o == "C" else "ok"))
    h1.main(["--csv", str(p), "--out-dir", str(tmp_path)])
    s = json.loads((tmp_path / "H1_summary.json").read_text())
    # all errors 1,2,3,-2,0,2: mean 1, MAE 10/6, SD sqrt(16/5)=1.7889, LoA 1 +/- 3.5062
    assert s["n_measurements"] == 6 and s["n_objects"] == 2          # the skipped row is excluded
    assert s["bias_g"] == 1.0 and s["MAE_g"] == 1.67 and s["sd_diff_g"] == 1.79
    assert s["loa_g"] == [-2.51, 4.51]
    assert s["MAPE_pct"] == 1.33                                      # (1+2+3+1+0+1)/6 %
    # pooled within-object SD = sqrt((2*1 + 2*4)/4) = 1.5811; RC = 1.96*sqrt(2)*1.5811 = 4.38
    assert s["within_object_sd_g"] == 1.581 and s["repeatability_coefficient_g"] == 4.38
    a = next(o for o in s["per_object"] if o["object_id"] == "A")
    assert a["mean_error_g"] == 2.0 and a["sd_error_g"] == 1.0
    assert (tmp_path / "H1_bland_altman.png").stat().st_size > 1000
    assert "repeatability coefficient" in (tmp_path / "H1_summary.md").read_text()


def h1_cols():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import fsn_capture_logger as cl
    return cl.H1_COLS
