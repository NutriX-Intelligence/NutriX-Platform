# S1: 7-image benchmark rerun (generated)

Run 2026-11-06 07:38:38 on current code. esp32.jpg = mixed plate, excluded from scoring.
Scoring: {"n_total": 7, "n_scored": 6, "n_excluded": 1, "yolo": 3, "qwen": 6, "pipeline": 6}
Cold load: {"yolo_s": 0.19, "qwen_s": 34.2}; peak VRAM allocated 4203.5 MB
Latency excluding the first (warm-up) image: {"yolo_ms": {"n": 6, "mean": 54.1, "median": 53.4, "min": 11.4, "max": 97.8}, "qwen_ms": {"n": 6, "mean": 2219.3, "median": 2293.1, "min": 1982.3, "max": 2420.6}, "e2e_ms": {"n": 6, "mean": 1159.0, "median": 1996.7, "min": 53.4, "max": 2396.8}}

| image | YOLO pred (raw conf %) | status | Qwen pred | Qwen raw kcal | Atwater kcal | flag_reason | macro src | kcal | score yolo/qwen/pipeline |
|---|---|---|---|---|---|---|---|---|---|
| appleTest.png | apple (42.9) | unidentified | apple | 52.0 | 112.7 | kcal 52 inconsistent with macros (Atwater estimate 112.7) | db | 93.6 | wrong/correct/correct |
| banana-trial.jpg | banana (78.3) | identified | banana | 85.0 | 116.5 | kcal recomputed from macros (model said 85) | db | 106.8 | correct/correct/correct |
| tomato-trial.jpg | tomato (83.1) | identified | tomato | 45.0 | 43.3 | None | db | 17.1 | correct/correct/correct |
| watermelon-trial.jpg | greenchutney (42.2) | unidentified | watermelon | 34.0 | 49.7 | kcal recomputed from macros (model said 34) | db | 105.0 | wrong/correct/correct |
| sweet-potat-test.jpg | None (0.0) | unidentified | sweet potato | 320.0 | 140.0 | kcal 320 inconsistent with macros (Atwater estimate 140) | db | 180.6 | wrong/correct/correct |
| IDLI.jpg | idli (52.8) | identified | idli | 240.0 | 146.0 | kcal recomputed from macros (model said 240) | db | 210.0 | correct/correct/correct |
| esp32.jpg | bell pepper (38.5) | unidentified | bell pepper | 35.0 | 37.0 | None | db | 30.0 | excluded/excluded/excluded |

## Text lookups (miss path)

'paneer butter masala' is a curated DB row (IND_FOOD_0018, brand NULL), not an LLM-Inferred one, so it is always a DB hit; kadhai paneer / shahi tukda were verified absent beforehand and are used for the miss path.

| query | source | latency ms | qwen raw kcal | Atwater kcal | flag_reason |
|---|---|---|---|---|---|
| apple | db | 2.6 |  |  |  |
| paneer butter masala | db | 2.6 |  |  |  |
| kadhai paneer | qwen3-vl-2b | 2658.5 | 280.0 | 208.0 | kcal recomputed from macros (model said 280) |
| kadhai paneer | db | 3.4 |  |  |  |
| shahi tukda | qwen3-vl-2b | 2636.1 | 250.0 | 210.0 |  |
| shahi tukda | db | 2.1 |  |  |  |
