import os
import sys
import time
import json
import psutil
import subprocess
from PIL import Image

import torch
from shared.db import get_db
from shared.models import Food, FoodAlias, FoodNutrient
from shared.food_lookup import lookup_food, per_100g, persist_llm_food, normalize_name
from ms1_cv.cv_engine import NutriXCVEngine, MealSession
from ms2_llm.vlm_engine import engine as vlm_engine
from ms2_llm import prompts
from ms2_llm.validation import parse_nutrition

def get_gpu_vram():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True
        ).strip()
        used, total = (float(x) for x in out.split(","))
        return used, total
    except Exception:
        return 0.0, 0.0

def get_ram_mb():
    vm = psutil.virtual_memory()
    return vm.used / (1024 * 1024), vm.total / (1024 * 1024)

def run_evaluation():
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": {},
        "resources": {},
        "cold_load": {},
        "image_tests": [],
        "text_lookups": []
    }

    # 1. Hardware baseline
    gpu_used_0, gpu_tot = get_gpu_vram()
    ram_used_0, ram_tot = get_ram_mb()
    results["hardware"] = {
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None",
        "gpu_total_mb": gpu_tot,
        "ram_total_mb": round(ram_tot, 1)
    }
    results["resources"]["initial"] = {
        "gpu_used_mb": gpu_used_0,
        "ram_used_mb": round(ram_used_0, 1)
    }
    print(f"[*] Initial Baseline: GPU VRAM {gpu_used_0:.1f}/{gpu_tot:.1f} MB | System RAM {ram_used_0:.1f}/{ram_tot:.1f} MB")

    # 2. Cold load YOLO
    t0 = time.time()
    cv_engine = NutriXCVEngine(model_path="backend/services/ingestion/best.pt", confidence_threshold=0.5)
    _ = cv_engine.model
    yolo_load_time = time.time() - t0
    gpu_used_yolo, _ = get_gpu_vram()
    results["cold_load"]["yolo_s"] = round(yolo_load_time, 2)
    results["resources"]["post_yolo"] = {"gpu_used_mb": gpu_used_yolo}
    print(f"[*] YOLO Cold Load: {yolo_load_time:.2f}s | GPU VRAM: {gpu_used_yolo:.1f} MB")

    # 3. Cold load Qwen3-VL-2B
    t0 = time.time()
    vlm_engine.load()
    qwen_load_time = time.time() - t0
    gpu_used_qwen, _ = get_gpu_vram()
    results["cold_load"]["qwen_s"] = round(qwen_load_time, 2)
    results["resources"]["post_qwen"] = {"gpu_used_mb": gpu_used_qwen}
    print(f"[*] Qwen3-VL-2B Cold Load: {qwen_load_time:.2f}s | GPU VRAM: {gpu_used_qwen:.1f} MB")

    # 4. Test Images
    test_files = [
        {"path": "inference_outputs/appleTest.png", "ground_truth": "Apple", "weight": 180.0},
        {"path": "inference_outputs/banana-trial.jpg", "ground_truth": "Banana", "weight": 120.0},
        {"path": "inference_outputs/tomato-trial.jpg", "ground_truth": "Tomato", "weight": 95.0},
        {"path": "inference_outputs/watermelon-trial.jpg", "ground_truth": "Watermelon", "weight": 350.0},
        {"path": "inference_outputs/sweet-potat-test.jpg", "ground_truth": "Sweet Potato", "weight": 210.0},
        {"path": "inference_outputs/IDLI.jpg", "ground_truth": "Idli", "weight": 150.0},
        {"path": "inference_outputs/esp32.jpg", "ground_truth": "Carrot/Apple/Tomato (Scale Plate)", "weight": 150.0},
    ]

    db_gen = get_db()
    db = next(db_gen)

    print("\n" + "="*80)
    print("RUNNING IMAGE EVALUATION MATRIX")
    print("="*80)

    for item in test_files:
        fpath = item["path"]
        if not os.path.exists(fpath):
            print(f"[-] Warning: {fpath} not found, skipping.")
            continue

        gt = item["ground_truth"]
        w = item["weight"]
        print(f"\n[>] Testing: {fpath} (Ground Truth: {gt})")

        # Step A: YOLO Test
        session = MealSession(session_id="eval-test")
        t_yolo_start = time.perf_counter()
        yolo_success, yolo_res = cv_engine.process_scale_event(fpath, current_weight=w, session=session)
        t_yolo_ms = (time.perf_counter() - t_yolo_start) * 1000

        yolo_status = yolo_res.get("status", "unidentified")
        yolo_pred = "None"
        yolo_conf = 0.0
        if yolo_success and yolo_status == "identified":
            yolo_pred = yolo_res["addition"]["food_name"]
            yolo_conf = yolo_res["addition"]["confidence"] * 100
        else:
            yolo_pred = yolo_res.get("fallback_class") or "None"
            yolo_conf = (yolo_res.get("fallback_conf") or 0.0) * 100

        # Step B: Qwen3-VL-2B Test
        pil_img = Image.open(fpath).convert("RGB")
        sys_prompt = prompts.get_system_prompt(prompts.VISION_KEY)
        user_prompt = prompts.vision_user_prompt(weight_g=w, yolo_hint=yolo_pred if yolo_pred != "None" else None)

        t_vlm_start = time.perf_counter()
        raw_vlm = vlm_engine.infer(sys_prompt, user_prompt, pil_img)
        t_vlm_ms = (time.perf_counter() - t_vlm_start) * 1000
        parsed_vlm = parse_nutrition(raw_vlm)

        vlm_pred = parsed_vlm["food_name"] if parsed_vlm else "unknown"
        vlm_conf = (parsed_vlm.get("confidence") or 0.0) * 100 if parsed_vlm else 0.0
        vlm_flagged = parsed_vlm.get("flagged", False) if parsed_vlm else True
        vlm_macros = parsed_vlm.get("per_100g") if parsed_vlm else None

        # Step C: Fallback & Macro Lookup Logic (Post-LLM Pipeline)
        t_pipe_start = time.perf_counter()
        final_identified_by = "yolo"
        final_food = yolo_pred
        final_conf = yolo_conf

        if yolo_status != "identified":
            # Fallback triggered!
            final_identified_by = "qwen"
            final_food = vlm_pred
            final_conf = vlm_conf

        clean_name = normalize_name(final_food)
        db_food = lookup_food(db, clean_name)
        per100 = per_100g(db_food) if db_food else None
        macro_src = "db" if per100 else "none"

        if per100 is None and vlm_macros and not vlm_flagged:
            per100 = vlm_macros
            macro_src = "qwen3-vl-2b"
            persist_llm_food(db, clean_name, per100)

        if per100 is None:
            per100 = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}

        total_kcal = round((w / 100.0) * per100["calories"], 1)
        total_p = round((w / 100.0) * per100["protein_g"], 1)
        total_c = round((w / 100.0) * per100["carbs_g"], 1)
        total_f = round((w / 100.0) * per100["fat_g"], 1)

        t_pipe_ms = (time.perf_counter() - t_pipe_start) * 1000
        # If Qwen was used, total end-to-end includes YOLO + Qwen + DB
        e2e_ms = t_yolo_ms + (t_vlm_ms if final_identified_by == "qwen" else 0.0) + t_pipe_ms

        curr_gpu, _ = get_gpu_vram()

        test_record = {
            "image": os.path.basename(fpath),
            "ground_truth": gt,
            "weight_g": w,
            "yolo": {
                "prediction": yolo_pred,
                "confidence": round(yolo_conf, 1),
                "status": yolo_status,
                "latency_ms": round(t_yolo_ms, 1)
            },
            "qwen": {
                "prediction": vlm_pred,
                "confidence": round(vlm_conf, 1),
                "flagged": vlm_flagged,
                "latency_ms": round(t_vlm_ms, 1),
                "per_100g": vlm_macros.model_dump() if hasattr(vlm_macros, "model_dump") else (dict(vlm_macros) if vlm_macros else None)
            },
            "pipeline_resolution": {
                "identified_by": final_identified_by,
                "final_food": clean_name.title(),
                "macro_source": macro_src,
                "calculated_calories": total_kcal,
                "protein_g": total_p,
                "carbs_g": total_c,
                "fat_g": total_f,
                "e2e_latency_ms": round(e2e_ms, 1)
            },
            "vram_mb": curr_gpu
        }
        results["image_tests"].append(test_record)
        print(f"  • YOLO Result     : {yolo_pred} ({yolo_conf:.1f}%) | {t_yolo_ms:.1f}ms | Status: {yolo_status}")
        print(f"  • Qwen Result     : {vlm_pred} ({vlm_conf:.1f}%) | {t_vlm_ms:.1f}ms | Flagged: {vlm_flagged}")
        print(f"  • Final Resolution: [{final_identified_by.upper()}] {clean_name.title()} | {total_kcal} kcal (via {macro_src}) | E2E: {e2e_ms:.1f}ms")

    # 5. Text Lookups
    print("\n" + "="*80)
    print("RUNNING TEXT LOOKUP & PERSISTENCE BENCHMARK")
    print("="*80)
    lookup_samples = ["apple", "paneer butter masala", "paneer butter masala"]
    for item_name in lookup_samples:
        t0 = time.perf_counter()
        clean = normalize_name(item_name)
        db_f = lookup_food(db, clean)
        m = per_100g(db_f) if db_f else None
        src = "db"
        if not m:
            # Query Qwen text lookup
            sys_p = prompts.get_system_prompt(prompts.LOOKUP_KEY)
            usr_p = prompts.lookup_user_prompt(item_name)
            raw = vlm_engine.infer(sys_p, usr_p, None)
            parsed = parse_nutrition(raw)
            if parsed and parsed.get("per_100g") and not parsed.get("flagged"):
                m = parsed["per_100g"]
                src = "qwen3-vl-2b"
                persist_llm_food(db, clean, m)
            else:
                src = "failed"
        lat = (time.perf_counter() - t0) * 1000
        rec = {
            "query": item_name,
            "source": src,
            "macros": m.model_dump() if hasattr(m, "model_dump") else (dict(m) if m else None),
            "latency_ms": round(lat, 1)
        }
        results["text_lookups"].append(rec)
        print(f"  • Lookup '{item_name}': Source: {src} | {lat:.1f}ms | Macros: {m}")

    # Peak VRAM
    peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
    results["resources"]["peak_vram_allocated_mb"] = round(peak_vram, 1)

    out_json = "inference_outputs/post_llm_benchmark_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Benchmark completed. Raw results saved to {out_json}")

if __name__ == "__main__":
    run_evaluation()
