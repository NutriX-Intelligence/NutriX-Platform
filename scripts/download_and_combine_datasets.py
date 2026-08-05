import os
import shutil
import yaml
from roboflow import Roboflow

def clean_temp_dirs(temp_dirs):
    """Removes temporary directories used for downloads."""
    for folder in temp_dirs:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"[Cleanup] Removed temporary folder: {folder}")

def parse_dataset_classes(dataset_path: str) -> dict:
    """Reads the data.yaml file from a Roboflow dataset and extracts the class names dict."""
    yaml_path = os.path.join(dataset_path, "data.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Could not find data.yaml at {dataset_path}")
    
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Roboflow data.yaml usually has a 'names' list or dictionary
    names = config.get("names", {})
    if isinstance(names, list):
        return {idx: name.lower().strip() for idx, name in enumerate(names)}
    elif isinstance(names, dict):
        return {int(idx): name.lower().strip() for idx, name in names.items()}
    else:
        raise ValueError(f"Unexpected names format in data.yaml at {dataset_path}")

def merge_and_remap(src_dir: str, dest_dir: str, local_classes: dict, global_classes: dict, split: str):
    """
    Copies images and remaps class IDs in label text files from src_dir to dest_dir.
    'split' is either 'train', 'valid', or 'test'.
    """
    src_images = os.path.join(src_dir, split, "images")
    src_labels = os.path.join(src_dir, split, "labels")
    
    dest_images = os.path.join(dest_dir, split, "images")
    dest_labels = os.path.join(dest_dir, split, "labels")
    
    os.makedirs(dest_images, exist_ok=True)
    os.makedirs(dest_labels, exist_ok=True)

    if not os.path.exists(src_images) or not os.path.exists(src_labels):
        print(f"[Warning] Missing split folders in {src_dir} for split: {split}. Skipping.")
        return

    image_files = [f for f in os.listdir(src_images) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Merging {len(image_files)} files from {os.path.basename(src_dir)} ({split})...")

    for img_name in image_files:
        # Copy Image
        src_img_path = os.path.join(src_images, img_name)
        dest_img_path = os.path.join(dest_images, img_name)
        shutil.copy2(src_img_path, dest_img_path)

        # Process matching Label
        name_no_ext, _ = os.path.splitext(img_name)
        lbl_name = f"{name_no_ext}.txt"
        src_lbl_path = os.path.join(src_labels, lbl_name)
        dest_lbl_path = os.path.join(dest_labels, lbl_name)

        if not os.path.exists(src_lbl_path):
            continue

        # Remap Class IDs inside label file
        new_lines = []
        with open(src_lbl_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    local_class_id = int(parts[0])
                    # Get class name from local mapping
                    class_name = local_classes.get(local_class_id)
                    if class_name:
                        # Get new class ID from global mapping
                        global_class_id = global_classes[class_name]
                        parts[0] = str(global_class_id)
                        new_lines.append(" ".join(parts) + "\n")
                    else:
                        print(f"[Warning] Class ID {local_class_id} not found in local map for {src_dir}")
        
        with open(dest_lbl_path, "w") as f:
            f.writelines(new_lines)

def main():
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        print("[Error] ROBOFLOW_API_KEY environment variable not set.")
        print("Please run: $env:ROBOFLOW_API_KEY='your-key-here' and run this script again.")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_root = os.path.join(base_dir, "dataset")
    combined_dest = os.path.join(dataset_root, "custom_training_data")

    # Define temporary folders for downloading each dataset
    temp_veg_fruit = os.path.join(dataset_root, "temp_combined_fruits_veg")
    temp_ingredients = os.path.join(dataset_root, "temp_food_ingredients")
    temp_indianfood = os.path.join(dataset_root, "temp_indianfoodnet")

    print("[Roboflow] Initializing SDK...")
    rf = Roboflow(api_key=api_key)

    # 1. Download Datasets
    try:
        print("\n--- Downloading: Combined Vegetables & Fruits ---")
        proj1 = rf.workspace("yolo-jpkho").project("combined-vegetables-fruits")
        # Version 1 is standard, adjust if needed
        proj1.version(1).download("yolov8", location=temp_veg_fruit)

        print("\n--- Downloading: FOOD-INGREDIENTS ---")
        proj2 = rf.workspace("food-recipe-ingredient-images-0gnku").project("food-ingredients-dataset")
        proj2.version(1).download("yolov8", location=temp_ingredients)

        print("\n--- Downloading: IndianFoodNet ---")
        proj3 = rf.workspace("indianfoodnet").project("indianfoodnet")
        proj3.version(1).download("yolov8", location=temp_indianfood)
    except Exception as e:
        print(f"[Error] Failed during Roboflow download: {e}")
        clean_temp_dirs([temp_veg_fruit, temp_ingredients, temp_indianfood])
        return

    # 2. Parse Class Lists and Build Global Mapping
    print("\n--- Parsing Class Configurations ---")
    classes1 = parse_dataset_classes(temp_veg_fruit)
    classes2 = parse_dataset_classes(temp_ingredients)
    classes3 = parse_dataset_classes(temp_indianfood)

    print(f"Dataset 1 Classes: {classes1}")
    print(f"Dataset 2 Classes: {classes2}")
    print(f"Dataset 3 Classes: {classes3}")

    # Build unique set of class names (case-insensitive and trimmed)
    all_class_names = set(classes1.values()) | set(classes2.values()) | set(classes3.values())
    global_classes = {name: idx for idx, name in enumerate(sorted(all_class_names))}
    print(f"\nCreated Consolidated Global Class Mapping ({len(global_classes)} classes):")
    for name, idx in global_classes.items():
        print(f"  {idx}: {name}")

    # 3. Clean and initialize destination directories
    if os.path.exists(combined_dest):
        shutil.rmtree(combined_dest)
    os.makedirs(combined_dest, exist_ok=True)

    # 4. Merge and Remap for each split (train, valid, test)
    splits = ["train", "valid", "test"]
    for split in splits:
        # Roboflow valid splits are sometimes named 'valid' or 'validation'.
        # The YOLOv8 download typically structures them as 'train', 'valid', 'test'.
        merge_and_remap(temp_veg_fruit, combined_dest, classes1, global_classes, split)
        merge_and_remap(temp_ingredients, combined_dest, classes2, global_classes, split)
        merge_and_remap(temp_indianfood, combined_dest, classes3, global_classes, split)

    # 5. Generate unified data.yaml
    final_yaml_path = os.path.join(combined_dest, "data.yaml")
    
    # Paths in data.yaml should be relative to the yaml file location or absolute.
    # YOLOv8 standard: 'path' points to the dataset root, 'train'/'val'/etc. point to subfolders.
    yaml_config = {
        "path": os.path.abspath(combined_dest),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "names": {idx: name for name, idx in global_classes.items()}
    }

    with open(final_yaml_path, "w") as f:
        yaml.safe_dump(yaml_config, f, default_flow_style=False)
    print(f"\n[Success] Combined data.yaml created at {final_yaml_path}")

    # 6. Cleanup temp folders to save disk space
    clean_temp_dirs([temp_veg_fruit, temp_ingredients, temp_indianfood])
    print("\n🎉 Combined Dataset Setup Complete!")

if __name__ == "__main__":
    main()
