import os
import uuid
import time
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image
import cv2
import numpy as np

# We'll import ultralytics only when needed to prevent load delays
# and to make sure it loads after installation finishes.

class IngredientAddition:
    def __init__(self, food_name: str, delta_weight: float, confidence: float, bounding_box: Optional[List[float]] = None):
        self.food_name = food_name
        self.delta_weight = delta_weight
        self.confidence = confidence
        self.bounding_box = bounding_box  # [x_min, y_min, x_max, y_max] normalized
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "food_name": self.food_name,
            "delta_weight": round(self.delta_weight, 2),
            "confidence": round(self.confidence, 4),
            "bounding_box": self.bounding_box,
            "timestamp": self.timestamp
        }

class MealSession:
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.history: List[IngredientAddition] = []
        self.last_stable_weight: float = 0.0
        self.created_at = time.time()

    def add_ingredient(self, food_name: str, delta_weight: float, confidence: float, bounding_box: Optional[List[float]] = None):
        addition = IngredientAddition(food_name, delta_weight, confidence, bounding_box)
        self.history.append(addition)
        return addition

    def get_total_weight(self) -> float:
        return sum(add.delta_weight for add in self.history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_weight": round(self.get_total_weight(), 2),
            "history": [add.to_dict() for add in self.history],
            "created_at": self.created_at
        }

class MockBox:
    def __init__(self, cls: int, conf: float, xyxy: List[float]):
        self.cls = [cls]
        self.conf = [conf]
        self.xyxy = [xyxy]

class MockResults:
    def __init__(self, boxes: List[MockBox], names: Dict[int, str]):
        self.boxes = boxes
        self.names = names

class CalCountCVEngine:
    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.8, mock_mode: bool = False):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.mock_mode = mock_mode
        self._model = None
        self.pending_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../dataset/pending"))
        os.makedirs(self.pending_dir, exist_ok=True)

        # Predefined mock mappings for testing curriculum
        self.mock_classes = {
            0: "apple",
            1: "banana",
            2: "roti",
            3: "bread",
            4: "cucumber",
            5: "tomato",
            6: "mango",
            7: "paneer_tikka"
        }

    @property
    def model(self):
        """Lazy load YOLO model to speed up initialization."""
        if self.mock_mode:
            return None
        if self._model is None:
            from ultralytics import YOLO
            # This will download the yolov8n model automatically if not present
            self._model = YOLO(self.model_path)
        return self._model

    def _get_mock_inference(self, image_path: str) -> List[MockResults]:
        """Simulates YOLOv8 inference outputs based on the filename for mock testing."""
        filename = os.path.basename(image_path).lower()
        boxes = []

        # We simulate bounding boxes [xmin, ymin, xmax, ymax]
        if "apple" in filename:
            boxes.append(MockBox(cls=0, conf=0.95, xyxy=[100.0, 100.0, 300.0, 300.0]))
        elif "banana" in filename:
            boxes.append(MockBox(cls=1, conf=0.92, xyxy=[50.0, 150.0, 400.0, 350.0]))
        elif "roti" in filename:
            boxes.append(MockBox(cls=2, conf=0.90, xyxy=[80.0, 80.0, 350.0, 350.0]))
        elif "bread" in filename:
            boxes.append(MockBox(cls=3, conf=0.88, xyxy=[90.0, 90.0, 310.0, 310.0]))
        elif "cucumber" in filename:
            boxes.append(MockBox(cls=4, conf=0.85, xyxy=[120.0, 150.0, 250.0, 280.0]))
        elif "tomato" in filename:
            boxes.append(MockBox(cls=5, conf=0.89, xyxy=[130.0, 110.0, 280.0, 260.0]))
        elif "raw_mango" in filename:
            # Low confidence to trigger Level 3 HitL
            boxes.append(MockBox(cls=6, conf=0.45, xyxy=[100.0, 120.0, 320.0, 300.0]))
        elif "paneer_tikka" in filename:
            # Low confidence to trigger Level 4 HitL
            boxes.append(MockBox(cls=7, conf=0.35, xyxy=[110.0, 110.0, 290.0, 290.0]))
            
        return [MockResults(boxes=boxes, names=self.mock_classes)]

    def process_scale_event(
        self, 
        image_path: str, 
        current_weight: float, 
        session: MealSession
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a new stable weight reading + image from the scale.
        Calculates weight delta and attempts to classify the added item.
        """
        delta_weight = current_weight - session.last_stable_weight
        
        # Check if the delta weight is meaningful (i.e. > 0.5g deviation)
        if delta_weight < 0.5:
            return False, {
                "status": "ignored",
                "reason": f"Negligible or negative weight delta: {delta_weight:.2f}g",
                "session": session.to_dict()
            }

        print(f"[CV Engine] Processing event: stable weight = {current_weight}g, delta = {delta_weight:.2f}g")

        # Run inference (mock or real)
        if self.mock_mode:
            results = self._get_mock_inference(image_path)
            class_names_dict = self.mock_classes
        else:
            results = self.model(image_path, verbose=False)
            class_names_dict = self.model.names

        if not results or len(results[0].boxes) == 0:
            # Nothing detected at all
            return self._handle_failed_detection(image_path, delta_weight, session, reason="No objects detected")

        # Get the highest confidence box
        best_box = None
        highest_conf = -1.0
        
        # Get frame dimensions for box normalization
        img = Image.open(image_path)
        w, h = img.size

        for box in results[0].boxes:
            conf = float(box.conf[0])
            if conf > highest_conf:
                highest_conf = conf
                best_box = box

        # Extract class name and bbox details
        class_id = int(best_box.cls[0])
        class_name = class_names_dict[class_id]
        xyxy = best_box.xyxy[0]  # List in mock, tensor/list in real
        normalized_bbox = [
            xyxy[0] / w,
            xyxy[1] / h,
            xyxy[2] / w,
            xyxy[3] / h
        ]

        # Check confidence threshold
        if highest_conf >= self.confidence_threshold:
            print(f"[CV Engine] Confirmed: {class_name} ({highest_conf*100:.1f}%)")
            # Update session
            addition = session.add_ingredient(
                food_name=class_name,
                delta_weight=delta_weight,
                confidence=highest_conf,
                bounding_box=normalized_bbox
            )
            session.last_stable_weight = current_weight
            return True, {
                "status": "identified",
                "addition": addition.to_dict(),
                "session": session.to_dict()
            }
        else:
            reason = f"Low confidence: {class_name} at {highest_conf*100:.1f}% (Required: {self.confidence_threshold*100}%)"
            return self._handle_failed_detection(
                image_path, 
                delta_weight, 
                session, 
                reason=reason,
                fallback_class=class_name,
                fallback_bbox=normalized_bbox,
                fallback_conf=highest_conf
            )

    def _handle_failed_detection(
        self, 
        image_path: str, 
        delta_weight: float, 
        session: MealSession, 
        reason: str,
        fallback_class: Optional[str] = None,
        fallback_bbox: Optional[List[float]] = None,
        fallback_conf: float = 0.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Saves image to pending dataset and flags for HitL review."""
        print(f"[CV Engine] Detection Failed: {reason}")
        
        timestamp = int(time.time())
        filename = f"{session.session_id}_{timestamp}.jpg"
        dest_path = os.path.join(self.pending_dir, filename)
        
        # Copy image to pending directory
        import shutil
        shutil.copy(image_path, dest_path)

        # We keep the weight delta stored temporarily so that when the user corrects,
        # we know how much weight to allocate. We save the temporary item in the session
        # history as 'unidentified_item' with status pending.
        addition = session.add_ingredient(
            food_name="unidentified_item",
            delta_weight=delta_weight,
            confidence=fallback_conf,
            bounding_box=fallback_bbox
        )
        
        # Even though it's unidentified, we advance the stable weight to accept the next layer.
        # Otherwise, the next addition would calculate a delta based on the weight before this item.
        session.last_stable_weight = session.last_stable_weight + delta_weight

        return False, {
            "status": "unidentified",
            "reason": reason,
            "pending_image_path": dest_path,
            "addition_index": len(session.history) - 1,
            "fallback_class": fallback_class,
            "session": session.to_dict()
        }
