import os
import sys
from ultralytics import YOLO
import cv2

def run_inference(image_path):
    # Ensure the image exists
    if not os.path.exists(image_path):
        print(f"Error: Image not found at '{image_path}'")
        sys.exit(1)

    # Resolve paths for the model weights
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    retrained_weights = os.path.join(base_dir, "backend", "services", "ingestion", "yolov8_retrained.pt")
    custom_weights = os.path.join(base_dir, "backend", "services", "ingestion", "nutrix_yolo_custom.pt")

    # Select the best available model
    if os.path.exists(custom_weights):
        model_path = custom_weights
        print(f"[Info] Loading custom baseline model from: {model_path}")
    elif os.path.exists(retrained_weights):
        model_path = retrained_weights
        print(f"[Info] Loading retrained model from: {model_path}")
    else:
        model_path = "yolov8n.pt"
        print(f"[Warning] No custom weights found. Using default coco weights: {model_path}")

    # 1. Load the YOLOv8 model
    model = YOLO(model_path)

    # 2. Run inference on the image
    print(f"[Inference] Running model on: {image_path}")
    results = model(image_path)

    # YOLOv8 returns a list of Results objects (one per image passed)
    result = results[0]

    # 3. Print out detection details
    print("\n" + "="*40)
    print("           DETECTION RESULTS")
    print("="*40)
    
    if len(result.boxes) == 0:
        print("No items detected.")
    else:
        for idx, box in enumerate(result.boxes, 1):
            # Get class ID, name, confidence, and coordinates
            class_id = int(box.cls[0])
            class_name = result.names[class_id]
            confidence = float(box.conf[0])
            # xyxy coordinate format: [xmin, ymin, xmax, ymax] in pixels
            bbox = box.xyxy[0].tolist()
            
            print(f"[{idx}] {class_name.upper()} ({confidence*100:.2f}% confidence)")
            print(f"    Bounding Box (xyxy): {[round(coord, 1) for coord in bbox]}")
    print("="*40)

    # 4. Save the annotated image (saves with drawn bounding boxes)
    output_dir = os.path.join(base_dir, "inference_outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    output_filename = "annotated_" + os.path.basename(image_path)
    output_path = os.path.join(output_dir, output_filename)
    
    # Save the annotated visual output
    result.save(filename=output_path)
    print(f"\n[Success] Annotated image saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inference_demo.py <path_to_image>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    run_inference(img_path)
