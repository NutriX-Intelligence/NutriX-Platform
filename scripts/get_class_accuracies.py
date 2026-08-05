import os
from ultralytics import YOLO

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    model_path = os.path.join(base_dir, "backend", "services", "ingestion", "nutrix_yolo_custom.pt")
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")

    if not os.path.exists(model_path):
        print(f"[Error] Custom model weights not found at: {model_path}")
        return
    if not os.path.exists(data_yaml_path):
        print(f"[Error] Data config not found at: {data_yaml_path}")
        return

    print("[Validation] Loading model and running validation dataset pass...")
    model = YOLO(model_path)
    
    import torch
    device = 0 if torch.cuda.is_available() else 'cpu'
    
    # Run validation (plots=False to speed up, save_json=False)
    metrics = model.val(data=data_yaml_path, plots=False, save_json=False, device=device)
    
    # Extract class names and maps
    class_names = model.names
    
    # metrics.box.maps contains average precision per class (mAP50-95)
    # metrics.box.ap50 contains AP50 per class
    # metrics.box.p contains precision per class
    # metrics.box.r contains recall per class
    
    ap50_scores = metrics.box.ap50
    precision_scores = metrics.box.p
    recall_scores = metrics.box.r
    present_classes = metrics.ap_class_index # List of global class IDs present in validation

    # Map each present class to its metrics
    class_metrics = {}
    for i, class_id in enumerate(present_classes):
        class_metrics[int(class_id)] = {
            "p": precision_scores[i],
            "r": recall_scores[i],
            "ap50": ap50_scores[i]
        }

    output_lines = []
    output_lines.append(f"{'Class ID':<10} {'Class Name':<30} {'Precision (P)':<15} {'Recall (R)':<15} {'mAP50':<15}\n")
    output_lines.append("-" * 90 + "\n")

    print("\n" + "="*80)
    print(f"{'Class Name':<30} {'Precision':<12} {'Recall':<12} {'mAP50':<12}")
    print("="*80)

    # Sort classes alphabetically by name
    sorted_classes = sorted(class_names.items(), key=lambda item: item[1])

    for class_id, class_name in sorted_classes:
        # Check if the class metrics exist in our mapped dict
        if class_id in class_metrics:
            m = class_metrics[class_id]
            p_str = f"{m['p']:.4f}"
            r_str = f"{m['r']:.4f}"
            m50_str = f"{m['ap50']:.4f}"
        else:
            p_str = "0.0000 (No Val Images)"
            r_str = "0.0000 (No Val Images)"
            m50_str = "0.0000 (No Val Images)"

        print(f"{class_name:<30} {p_str:<12} {r_str:<12} {m50_str:<12}")
        output_lines.append(f"{class_id:<10} {class_name:<30} {p_str:<15} {r_str:<15} {m50_str:<15}\n")

    output_file = os.path.join(base_dir, "class_accuracies.txt")
    with open(output_file, "w") as f:
        f.writelines(output_lines)
        
    print(f"\n[Success] Complete class-by-class report saved to: {output_file}")

if __name__ == "__main__":
    main()
