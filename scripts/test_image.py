import os
import sys
from ultralytics import YOLO
import cv2

def main():
    if len(sys.argv) < 2:
        print("[Usage] Please provide the path to your test image.")
        print("Example: .venv\\Scripts\\python test_image.py my_food.jpg")
        return

    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(f"[Error] Image file not found at: {img_path}")
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    model_path = os.path.join(base_dir, "backend", "services", "ingestion", "nutrix_yolo_custom.pt")

    if not os.path.exists(model_path):
        print(f"[Error] Custom model weights not found at: {model_path}")
        return

    print(f"[Model] Loading custom YOLOv8 weights from {model_path}...")
    model = YOLO(model_path)

    print(f"[Inference] Processing image: {img_path}...")
    # Run inference
    results = model(img_path)

    # YOLOv8 returns a list of Results. We take the first one.
    result = results[0]

    # Save the annotated image
    output_filename = "annotated_" + os.path.basename(img_path)
    output_path = os.path.join(base_dir, output_filename)
    
    # Save the result image with boxes drawn
    result.save(filename=output_path)
    print(f"[Success] Bounding boxes drawn! Annotated image saved to: {output_path}")

    # Print the detected objects and their confidences
    print("\n--- Detected Foods ---")
    if len(result.boxes) == 0:
        print("No food items detected.")
    else:
        for idx, box in enumerate(result.boxes):
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            confidence = float(box.conf[0])
            bbox = box.xyxy[0].tolist() # [xmin, ymin, xmax, ymax]
            print(f"[{idx + 1}] {class_name.upper()} (Confidence: {confidence * 100:.1f}%)")
            print(f"    Bounding Box: {bbox}")

if __name__ == "__main__":
    main()
