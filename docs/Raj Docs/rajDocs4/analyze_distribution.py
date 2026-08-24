import os
import glob
import pandas as pd
import numpy as np
import yaml
import matplotlib.pyplot as plt
import seaborn as sns

def parse_split_annotations(dataset_root, split_name, class_names):
    labels_dir = os.path.join(dataset_root, split_name, "labels")
    images_dir = os.path.join(dataset_root, split_name, "images")
    
    if not os.path.exists(labels_dir):
        print(f"Directory not found: {labels_dir}")
        return {}, {}
        
    label_files = glob.glob(os.path.join(labels_dir, "*.txt"))
    
    class_img_counts = {cls_id: 0 for cls_id in class_names.keys()}
    class_ann_counts = {cls_id: 0 for cls_id in class_names.keys()}
    
    for lbl_path in label_files:
        with open(lbl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        classes_in_file = set()
        for line in lines:
            parts = line.strip().split()
            if parts and parts[0].isdigit():
                cls_id = int(parts[0])
                if cls_id in class_ann_counts:
                    class_ann_counts[cls_id] += 1
                    classes_in_file.add(cls_id)
                    
        for cls_id in classes_in_file:
            class_img_counts[cls_id] += 1
            
    return class_img_counts, class_ann_counts

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")
    output_dir = script_dir
    wacv_fig_dir = os.path.join(output_dir, "wacv_figures")
    os.makedirs(wacv_fig_dir, exist_ok=True)
    
    with open(data_yaml_path, "r", encoding="utf-8") as f:
        data_config = yaml.safe_load(f)
        
    raw_names = data_config.get("names", {})
    if isinstance(raw_names, list):
        class_names = {idx: name for idx, name in enumerate(raw_names)}
    else:
        class_names = {int(idx): name for idx, name in raw_names.items()}
        
    dataset_root = os.path.join(base_dir, "dataset", "custom_training_data")
    
    splits = ["train", "valid", "test"]
    split_data = {}
    
    for split in splits:
        print(f"Parsing annotations for split: {split}...")
        img_counts, ann_counts = parse_split_annotations(dataset_root, split, class_names)
        split_data[split] = {"images": img_counts, "annotations": ann_counts}
        
    rows = []
    for cls_id, cls_name in sorted(class_names.items()):
        tr_img = split_data["train"]["images"].get(cls_id, 0)
        tr_ann = split_data["train"]["annotations"].get(cls_id, 0)
        val_img = split_data["valid"]["images"].get(cls_id, 0)
        val_ann = split_data["valid"]["annotations"].get(cls_id, 0)
        tst_img = split_data["test"]["images"].get(cls_id, 0)
        tst_ann = split_data["test"]["annotations"].get(cls_id, 0)
        
        tot_img = tr_img + val_img + tst_img
        tot_ann = tr_ann + val_ann + tst_ann
        
        rows.append({
            "class_id": cls_id,
            "class_name": cls_name,
            "train_images": tr_img,
            "train_annotations": tr_ann,
            "val_images": val_img,
            "val_annotations": val_ann,
            "test_images": tst_img,
            "test_annotations": tst_ann,
            "total_images": tot_img,
            "total_annotations": tot_ann
        })
        
    df = pd.DataFrame(rows)
    csv_path = os.path.join(output_dir, "class_distribution.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved distribution CSV to {csv_path}")
    
    # Calculate statistics for each split
    stats_rows = []
    for col in ["train_images", "val_images", "test_images", "total_images", 
                "train_annotations", "val_annotations", "test_annotations", "total_annotations"]:
        data_series = df[col]
        stats_rows.append({
            "metric": col,
            "min": int(data_series.min()),
            "max": int(data_series.max()),
            "mean": round(float(data_series.mean()), 2),
            "median": round(float(data_series.median()), 2),
            "std": round(float(data_series.std()), 2)
        })
        
    stats_df = pd.DataFrame(stats_rows)
    stats_csv_path = os.path.join(output_dir, "class_distribution_statistics.csv")
    stats_df.to_csv(stats_csv_path, index=False)
    print(f"Saved distribution statistics to {stats_csv_path}")
    
    # Validation image brackets
    val_zero = df[df["val_images"] == 0]["class_name"].tolist()
    val_lt5 = df[(df["val_images"] > 0) & (df["val_images"] < 5)]["class_name"].tolist()
    val_5_20 = df[(df["val_images"] >= 5) & (df["val_images"] <= 20)]["class_name"].tolist()
    val_gt20 = df[df["val_images"] > 20]["class_name"].tolist()
    
    with open(os.path.join(output_dir, "validation_brackets_summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"Validation Image Distribution Brackets:\n")
        f.write(f"Zero Validation Images ({len(val_zero)} classes): {', '.join(val_zero)}\n\n")
        f.write(f"<5 Validation Images ({len(val_lt5)} classes): {', '.join(val_lt5)}\n\n")
        f.write(f"5-20 Validation Images ({len(val_5_20)} classes): {', '.join(val_5_20)}\n\n")
        f.write(f">20 Validation Images ({len(val_gt20)} classes): {', '.join(val_gt20)}\n\n")
        
    print("Saved validation brackets summary.")
    
    # Generate Plot
    plt.figure(figsize=(16, 6))
    top_30 = df.sort_values(by="total_images", ascending=False).head(30)
    sns.barplot(data=top_30, x="class_name", y="total_images", hue="class_name", legend=False, palette="viridis")
    plt.xticks(rotation=90, fontsize=9)
    plt.title("Top 30 Classes by Total Image Count (NutriX Core Dataset)")
    plt.xlabel("Class Name")
    plt.ylabel("Image Count")
    plt.tight_layout()
    plot_path = os.path.join(output_dir, "class_distribution_plot.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"Saved distribution plot to {plot_path}")

if __name__ == "__main__":
    main()
