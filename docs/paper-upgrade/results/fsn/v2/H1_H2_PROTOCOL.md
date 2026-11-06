# H1 / H2 physical-test checklist

All commands run in WSL:

```bash
cd /home/harsh/Nutrix && source .venv/bin/activate
```

## Before either test

- [ ] `docker compose up -d postgres redis`
- [ ] Start the gateway, MS1 and MS2 on the **current code**. Restart MS1 if it was already running, because the capture record (`dataset/live_captures/log/<meal_log_id>.json`, holding YOLO top-1, confidence and VLM output) needs this commit.
- [ ] Check that `.env` has `YOLO_CONF_THRESHOLD=0.5` (`grep ^YOLO_CONF_THRESHOLD .env`).
- [ ] Reset today's session: `PYTHONPATH=. python scripts/reset_test_session.py`
- [ ] Clear the old `eval-test_*` frames out of `dataset/pending/` (they are from 27 Oct, not part of this test).
- [ ] Reference scale: note its make, model and resolution. Check it against a known mass (e.g. a 500 g or 1 kg calibration weight) before starting.

## H1: scale weight accuracy

- [ ] Pick **10 objects from 20 g to 1,000 g**, spread across the range (e.g. about 20, 50, 100, 150, 250, 400, 500, 650, 800 and 1,000 g). Give each one a short id (`O01` … `O10`).
- [ ] Weigh each object on the reference scale and write the weight down. That is `ref_g`.
- [ ] Start the logger in a second terminal:
  ```bash
  PYTHONPATH=. python scripts/fsn_capture_logger.py --scale
  ```
- [ ] For each object, do **5 trials**. For each trial:
  1. Tare the NutriX scale with nothing on it.
  2. Place the object and trigger a capture.
  3. Answer the logger prompts: object_id, ref_g, trial (1–5).
- [ ] If a capture goes wrong, type `skip` (it is kept as skipped). If you typed a wrong answer, type `undo` (removes your last entry and asks for it again).
- [ ] Ctrl+C stops the logger at any time. Run the same command again to resume; nothing is asked twice.
- [ ] Target: 50 rows with status `ok` in `docs/paper-upgrade/results/fsn/v2/H1_scale.csv`.
- [ ] Report:
  ```bash
  PYTHONPATH=. python scripts/fsn_h1_report.py
  ```
  This writes `H1_summary.md`, `H1_summary.json` and `H1_bland_altman.png` in `v2/`.

## H2: servings (identification + weight + energy)

- [ ] Plan **40–60 servings, one food per plate**:
  - At least **half Indian home foods** (dal, rice, roti, sabzi, idli, poha, …).
  - **8–10 packaged items** with a nutrition label.
  - The rest raw or other foods (fruit, vegetables, egg, …).
- [ ] **Photograph the label** of every packaged item (per-100 g panel visible). Name each photo with the meal_log id the logger shows.
- [ ] Weigh each serving on the reference scale (`ref_g`). Do this with the plate tared, so `ref_g` is food only.
- [ ] Start the logger:
  ```bash
  PYTHONPATH=. python scripts/fsn_capture_logger.py --servings
  ```
- [ ] For each serving, tare the plate, put the food on it and trigger a capture. Then answer:
  - true_food: use a plain name, e.g. `dal`, `idli`, `apple`, `oreo`. The report matches it to INDB or USDA by name.
  - ref_g
  - is_packaged: y or n
  - For packaged items only: label kcal, protein, carbs and fat per 100 g.
- [ ] `skip`, `undo` and Ctrl+C behave as in H1.
- [ ] Rows the logger shows as **no nutrition data** (0 kcal that is missing data) are expected sometimes. Answer them normally; the report lists them separately.
- [ ] Report:
  ```bash
  PYTHONPATH=. python scripts/fsn_h2_report.py
  ```
  This writes `H2_summary.md`, `H2_summary.json` and `H2_per_serving.csv` in `v2/`.
  - If the report lists **foods without a reference**, add each one to `v2/H2_reference_map.csv` and rerun. Columns: `true_food,ref_source,ref_code,kcal,protein,carbs,fat`, values per 100 g, with ref_code naming the INDB code or FDC id you used.

## After the tests

- [ ] Stop the services. Check `nvidia-smi` shows no process holding the GPU.
- [ ] Keep `H1_scale.csv`, `H2_servings.csv`, their `.state.json` files and the label photos. Do not edit the CSVs by hand: use `undo` while logging, or note corrections in a separate file.
