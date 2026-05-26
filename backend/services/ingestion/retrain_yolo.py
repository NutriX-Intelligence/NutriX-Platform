import os
import yaml
from ultralytics import YOLO

def generate_data_yaml(dataset_dir: str, classes_file: str, yaml_path: str):
    """Generates the data.yaml file required by YOLOv8 for training."""
    dataset_dir = os.path.abspath(dataset_dir)
    classes_file = os.path.abspath(classes_file)
    
    if not os.path.exists(classes_file):
        raise FileNotFoundError(f"Classes file not found at {classes_file}")

    with open(classes_file, "r") as f:
        classes = [line.strip() for line in f.readlines() if line.strip()]

    # Construct the YAML dictionary
    # YOLOv8 expects paths to be absolute or relative to the 'path' key
    data = {
        "path": dataset_dir,
        "train": "trained",  # Relative to 'path'
        "val": "trained",    # For simple capstone retraining, we validation on the same set
        "names": {i: name for i, name in enumerate(classes)}
    }

    with open(yaml_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    
    print(f"[Retraining] Generated data.yaml at {yaml_path}")
    return len(classes)

def run_retraining(epochs: int = 1):
    """Executes YOLOv8 fine-tuning on the user-corrected dataset."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    dataset_dir = os.path.join(base_dir, "dataset")
    classes_file = os.path.join(dataset_dir, "classes.txt")
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    trained_images_dir = os.path.join(dataset_dir, "trained")

    # Guard clause: Verify there is training data
    if not os.path.exists(trained_images_dir):
        print("[Retraining] Aborted: 'trained' directory does not exist.")
        return False
        
    image_files = [f for f in os.listdir(trained_images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    if len(image_files) == 0:
        print("[Retraining] Aborted: No images found in 'trained' directory to train on.")
        return False

    print(f"[Retraining] Found {len(image_files)} training images. Preparing data.yaml...")
    num_classes = generate_data_yaml(dataset_dir, classes_file, yaml_path)

    print(f"[Retraining] Loading base model (yolov8n.pt)...")
    # Load model
    model = YOLO("yolov8n.pt")

    print(f"[Retraining] Starting training for {epochs} epoch(s) on CPU...")
    # Train using CPU, small image sizes, and low batch sizes for quick execution
    # Incorporating custom capstone hyperparameters for top-down scale plate detection:
    results = model.train(
        data=yaml_path,
        epochs=epochs,
        imgsz=320,
        batch=2,
        device="cpu",
        workers=0,  # avoid multiprocessing issues during simple local tests on Windows
        project=os.path.join(base_dir, "runs"),
        name="calcount_retrain",
        # Custom augmentations for top-down fixed-arm plate setting
        degrees=180.0,    # Maximize rotational invariance (food can be rotated any way)
        scale=0.2,        # Scale down/up by 20% to simulate portion sizes
        perspective=0.0,  # Turn OFF perspective distortion since camera arm is fixed
        fliplr=0.5,       # Flip horizontally (50% probability)
        flipud=0.5        # Flip vertically (50% probability - crucial for top-down views)
    )

    # Save the retrained model weights to our ingestion engine
    best_weights_path = os.path.join(base_dir, "runs", "calcount_retrain", "weights", "best.pt")
    target_weights_path = os.path.join(os.path.dirname(__file__), "yolov8_retrained.pt")
    
    if os.path.exists(best_weights_path):
        import shutil
        shutil.copy(best_weights_path, target_weights_path)
        print(f"[Retraining] Training complete! Best weights saved to: {target_weights_path}")
        return True
    else:
        print("[Retraining] Error: Could not locate trained weights at runs/calcount_retrain/weights/best.pt")
        return False

if __name__ == "__main__":
    run_retraining(epochs=1)
