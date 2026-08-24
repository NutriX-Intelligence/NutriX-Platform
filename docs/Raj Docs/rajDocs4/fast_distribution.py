import os
import glob
import csv
import math
import yaml

def parse_split(dataset_root, split_name, class_names):
    labels_dir = os.path.join(dataset_root, split_name, "labels")
    img_counts = {i: 0 for i in class_names}
    ann_counts = {i: 0 for i in class_names}
    
    if not os.path.exists(labels_dir):
        return img_counts, ann_counts
        
    for entry in os.scandir(labels_dir):
        if entry.name.endswith(".txt"):
            seen = set()
            with open(entry.path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        cid = int(parts[0])
                        if cid in ann_counts:
                            ann_counts[cid] += 1
                            seen.add(cid)
            for cid in seen:
                img_counts[cid] += 1
                
    return img_counts, ann_counts

def calc_stats(vals):
    if not vals:
        return 0, 0, 0, 0, 0
    mn = min(vals)
    mx = max(vals)
    mean = sum(vals) / len(vals)
    s_vals = sorted(vals)
    n = len(s_vals)
    med = s_vals[n//2] if n % 2 != 0 else (s_vals[n//2 - 1] + s_vals[n//2]) / 2.0
    var = sum((x - mean) ** 2 for x in vals) / len(vals)
    std = math.sqrt(var)
    return mn, mx, round(mean, 2), round(med, 2), round(std, 2)

def main():
    base_dir = "/home/harsh/Nutrix"
    data_yaml = os.path.join(base_dir, "dataset/custom_training_data/data.yaml")
    out_dir = os.path.join(base_dir, "docs/rajDocs4")
    fig_dir = os.path.join(out_dir, "wacv_figures")
    os.makedirs(fig_dir, exist_ok=True)
    
    with open(data_yaml, "r") as f:
        cfg = yaml.safe_load(f)
        
    names = cfg.get("names", {})
    if isinstance(names, list):
        class_names = {i: name for i, name in enumerate(names)}
    else:
        class_names = {int(i): name for i, name in names.items()}
        
    ds_root = os.path.join(base_dir, "dataset/custom_training_data")
    
    tr_img, tr_ann = parse_split(ds_root, "train", class_names)
    val_img, val_ann = parse_split(ds_root, "valid", class_names)
    tst_img, tst_ann = parse_split(ds_root, "test", class_names)
    
    csv_path = os.path.join(out_dir, "class_distribution.csv")
    rows = []
    
    for cid in sorted(class_names.keys()):
        cname = class_names[cid]
        tri, tra = tr_img[cid], tr_ann[cid]
        vai, vaa = val_img[cid], val_ann[cid]
        tsi, tsa = tst_img[cid], tst_ann[cid]
        tot_i = tri + vai + tsi
        tot_a = tra + vaa + tsa
        
        rows.append({
            "class_id": cid,
            "class_name": cname,
            "train_images": tri,
            "train_annotations": tra,
            "val_images": vai,
            "val_annotations": vaa,
            "test_images": tsi,
            "test_annotations": tsa,
            "total_images": tot_i,
            "total_annotations": tot_a
        })
        
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Saved fast distribution CSV to {csv_path}")
    
    # Calculate statistics
    cols = ["train_images", "val_images", "test_images", "total_images",
            "train_annotations", "val_annotations", "test_annotations", "total_annotations"]
    
    stats_path = os.path.join(out_dir, "class_distribution_statistics.csv")
    with open(stats_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "min", "max", "mean", "median", "std"])
        for c in cols:
            vals = [r[c] for r in rows]
            mn, mx, mean, med, std = calc_stats(vals)
            writer.writerow([c, mn, mx, mean, med, std])
            
    print(f"Saved statistics CSV to {stats_path}")
    
    # Brackets
    v_zero = [r["class_name"] for r in rows if r["val_images"] == 0]
    v_lt5 = [r["class_name"] for r in rows if 0 < r["val_images"] < 5]
    v_5_20 = [r["class_name"] for r in rows if 5 <= r["val_images"] <= 20]
    v_gt20 = [r["class_name"] for r in rows if r["val_images"] > 20]
    
    summary_path = os.path.join(out_dir, "validation_brackets_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Validation Image Distribution Brackets:\n")
        f.write(f"Zero Validation Images ({len(v_zero)} classes): {', '.join(v_zero)}\n\n")
        f.write(f"<5 Validation Images ({len(v_lt5)} classes): {', '.join(v_lt5)}\n\n")
        f.write(f"5-20 Validation Images ({len(v_5_20)} classes): {', '.join(v_5_20)}\n\n")
        f.write(f">20 Validation Images ({len(v_gt20)} classes): {', '.join(v_gt20)}\n\n")
        
    print(f"Saved brackets summary to {summary_path}")

if __name__ == "__main__":
    main()
