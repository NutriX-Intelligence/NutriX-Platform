import os
import sys
import requests
from ultralytics import YOLO

# ESP32 Capture URL
ESP32_URL = "http://192.168.29.134/capture"
IMAGE_PATH = "esp32.jpg"

def main():
    # 1. Fetch image from ESP32
    print(f"[ESP32] Fetching image from {ESP32_URL}...")
    try:
        response = requests.get(ESP32_URL, timeout=10)
        response.raise_for_status()
        with open(IMAGE_PATH, "wb") as f:
            f.write(response.content)
        print(f"[ESP32] Image saved successfully to '{IMAGE_PATH}'")
    except Exception as e:
        print(f"[Error] Failed to capture image from ESP32: {e}")
        sys.exit(1)

    # 2. Resolve paths for the model weights
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    retrained_weights = os.path.join(base_dir, "backend", "services", "ingestion", "yolov8_retrained.pt")
    custom_weights = os.path.join(base_dir, "backend", "services", "ingestion", "nutrix_yolo_custom.pt")

    # Select model (prioritizing custom baseline, then retrained, then coco default)
    if os.path.exists(custom_weights):
        model_path = custom_weights
        print(f"[Info] Loading custom baseline model from: {model_path}")
    elif os.path.exists(retrained_weights):
        model_path = retrained_weights
        print(f"[Info] Loading retrained model from: {model_path}")
    else:
        model_path = "yolov8n.pt"
        print(f"[Warning] No custom weights found. Using default coco weights: {model_path}")

    # 3. Load model and run inference
    model = YOLO(model_path)
    print(f"[Inference] Running model on: {IMAGE_PATH}")
    results = model(IMAGE_PATH)
    result = results[0]

    # 4. Print results
    print("\n" + "="*40)
    print("           DETECTION RESULTS")
    print("="*40)
    if len(result.boxes) == 0:
        print("No items detected.")
    else:
        for idx, box in enumerate(result.boxes, 1):
            class_id = int(box.cls[0])
            class_name = result.names[class_id]
            confidence = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            print(f"[{idx}] {class_name.upper()} ({confidence*100:.2f}% confidence)")
            print(f"    Bounding Box (xyxy): {[round(coord, 1) for coord in bbox]}")
    print("="*40)

    # 5. Save the annotated image
    output_dir = os.path.join(base_dir, "inference_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = "annotated_esp32.jpg"
    output_path = os.path.join(output_dir, output_filename)
    
    result.save(filename=output_path)
    print(f"\n[Success] Annotated image saved to: {output_path}")

    # 6. Open the annotated image automatically on Windows
    if sys.platform == "win32":
        try:
            print("[System] Opening annotated image...")
            os.startfile(output_path)
        except Exception as e:
            print(f"[Warning] Could not automatically open image: {e}")

if __name__ == "__main__":
    main()
