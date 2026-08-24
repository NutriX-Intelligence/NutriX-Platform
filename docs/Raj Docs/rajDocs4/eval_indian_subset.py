import os
import yaml
import torch
import pandas as pd
from ultralytics import YOLO

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    weights_path = os.path.join(base_dir, "runs", "nutrix_custom_model-2", "weights", "best.pt")
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")
    output_dir = script_dir
    fig_dir = os.path.join(output_dir, "wacv_figures")
    os.makedirs(fig_dir, exist_ok=True)

    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data_config = yaml.safe_load(f)

    raw_names = data_config.get("names", {})
    if isinstance(raw_names, list):
        class_names = {idx: name for idx, name in enumerate(raw_names)}
    else:
        class_names = {int(idx): name for idx, name in raw_names.items()}

    indian_class_names = [
        "aloogobi", "aloomasala", "bhatura", "bhindimasala", "biryani", 
        "chai", "chole", "coconutchutney", "dal", "dosa", "dumaloo", 
        "fishcurry", "ghevar", "greenchutney", "gulabjamun", "idli", 
        "jalebi", "kebab", "kheer", "kulfi", "lassi", "muttoncurry", 
        "onionpakoda", "palakpaneer", "poha", "rahar ko daal", "rajmacurry", 
        "rasmalai", "samosa", "shahipaneer", "whiterice"
    ]

    indian_class_ids = [cls_id for cls_id, name in class_names.items() if name in indian_class_names]
    print(f"Identified {len(indian_class_ids)} Indian dish/food classes.")

    print(f"Loading checkpoint: {weights_path}...")
    model = YOLO(weights_path)
    device_val = 0 if torch.cuda.is_available() else 'cpu'

    print(f"Executing evaluation on Indian dish subset on validation split (device={device_val})...")
    results = model.val(
        data=data_yaml_path,
        split="val",
        classes=indian_class_ids,
        batch=16,
        imgsz=640,
        device=device_val,
        plots=False,
        save=False
    )

    mp = results.results_dict["metrics/precision(B)"]
    mr = results.results_dict["metrics/recall(B)"]
    map50 = results.results_dict["metrics/mAP50(B)"]
    map5095 = results.results_dict["metrics/mAP50-95(B)"]

    print(f"\n--- Indian Subset Overall Results ---")
    print(f"Classes Count: {len(indian_class_ids)}")
    print(f"Precision: {mp:.4f}")
    print(f"Recall: {mr:.4f}")
    print(f"mAP@50: {map50:.4f}")
    print(f"mAP@50-95: {map5095:.4f}")

    per_class_rows = []
    for cls_id in indian_class_ids:
        c_name = class_names[cls_id]
        if hasattr(results, 'ap_class_index') and cls_id in results.ap_class_index:
            idx = list(results.ap_class_index).index(cls_id)
            p = results.box.p[idx]
            r = results.box.r[idx]
            ap50 = results.box.ap50[idx]
            ap = results.box.ap[idx]
        else:
            p, r, ap50, ap = 0.0, 0.0, 0.0, 0.0
            
        per_class_rows.append({
            "class_id": cls_id,
            "class_name": c_name,
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "ap50": round(float(ap50), 4),
            "ap50_95": round(float(ap), 4)
        })

    df_per_class = pd.DataFrame(per_class_rows)
    csv_path = os.path.join(fig_dir, "indian_dish_subset_results.csv")
    df_per_class.to_csv(csv_path, index=False)
    print(f"Saved per-class Indian subset results to {csv_path}")

    summary_path = os.path.join(output_dir, "indian_subset_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("INDIAN DISH SUBSET EVALUATION SUMMARY\n")
        f.write("======================================\n")
        f.write(f"Checkpoint Used: {weights_path}\n")
        f.write(f"Dataset YAML: {data_yaml_path}\n")
        f.write(f"Total Indian Classes Evaluated: {len(indian_class_ids)}\n")
        f.write(f"Overall Precision: {mp:.4f}\n")
        f.write(f"Overall Recall: {mr:.4f}\n")
        f.write(f"Overall mAP50: {map50:.4f}\n")
        f.write(f"Overall mAP50-95: {map5095:.4f}\n")
    print(f"Saved summary to {summary_path}")

if __name__ == "__main__":
    main()
