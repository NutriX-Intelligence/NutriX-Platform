import os
from ultralytics import YOLO

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_yaml_path = os.path.join(base_dir, "dataset", "custom_training_data", "data.yaml")

    # Guard clause: Ensure data is downloaded and combined first
    if not os.path.exists(data_yaml_path):
        print("[Error] Combined dataset not found!")
        print(f"Please run the download script first: .venv\\Scripts\\python download_and_combine_datasets.py")
        return

    import torch
    cuda_available = torch.cuda.is_available()
    device = 0 if cuda_available else "cpu"
    
    # Lock in B.Tech custom overrides for top-down scale settings
    # 30 epochs is standard and highly effective for fine-tuning a pre-trained model
    epochs = 30
    imgsz = 640
    batch_size = 16 if cuda_available else 8  # Use larger batch size on GPU
    
    print(f"[Training] CUDA (NVIDIA GPU) Available: {cuda_available}")
    print(f"[Training] Using Device: {device}")
    print(f"[Training] Loading base pre-trained model (yolov8n.pt)...")
    model = YOLO("yolov8n.pt")
    
    print(f"[Training] Beginning fine-tuning on custom data for {epochs} epochs...")
    print(f"Data config: {data_yaml_path}")
    print("Using augmentations: rotational invariance (180 deg), vertical flips, no perspective distortion.")
    
    # Train the custom model
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device=device,
        workers=4 if cuda_available else 0, # Utilize multi-core dataloading on GPU
        project=os.path.join(base_dir, "runs"),
        name="calcount_custom_model",
        # Hyperparameter overrides for fixed-arm overhead camera:
        degrees=180.0,    # Maximize rotational invariance (360 degrees)
        scale=0.2,        # Scale images up/down by 20% to simulate portion sizes
        perspective=0.0,  # Turn off perspective distortion (camera is fixed straight down)
        fliplr=0.5,       # Flip horizontally (50% probability)
        flipud=0.5        # Flip vertically (50% probability)
    )

    print("\n🎉 Training complete!")
    best_weights = os.path.join(base_dir, "runs", "calcount_custom_model", "weights", "best.pt")
    if os.path.exists(best_weights):
        print(f"Your fine-tuned model weights are saved at: {best_weights}")
        # Copy to ingestion service for deployment
        target_path = os.path.join(base_dir, "backend", "services", "ingestion", "calcount_yolo_custom.pt")
        import shutil
        shutil.copy(best_weights, target_path)
        print(f"Deployed weights to ingestion service: {target_path}")
    else:
        print("[Error] Could not find trained weights. Check the 'runs/' directory.")

if __name__ == "__main__":
    main()
