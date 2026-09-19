from ultralytics import YOLO

model_path = "/home/harsh/Nutrix/backend/services/ingestion/best.pt"
try:
    model = YOLO(model_path)
    import json
    print(json.dumps(model.names))
except Exception as e:
    print(f"Error: {e}")
