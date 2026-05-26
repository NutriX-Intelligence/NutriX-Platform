import os
import shutil
from typing import Dict, Any, List, Optional
from backend.services.ingestion.cv_engine import MealSession

class CalCountHitlEngine:
    def __init__(self):
        self.dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../dataset"))
        self.pending_dir = os.path.join(self.dataset_dir, "pending")
        self.trained_dir = os.path.join(self.dataset_dir, "trained")
        self.classes_file = os.path.join(self.dataset_dir, "classes.txt")

        # Make sure folders exist
        os.makedirs(self.pending_dir, exist_ok=True)
        os.makedirs(self.trained_dir, exist_ok=True)
        
        # Ensure classes.txt exists
        if not os.path.exists(self.classes_file):
            # Seed it with standard items + some Indian specialties
            with open(self.classes_file, "w") as f:
                f.write("\n".join(["apple", "banana", "orange", "roti", "cucumber", "tomato", "mango"]) + "\n")

    def _get_or_create_class_id(self, food_name: str) -> int:
        """Finds or appends a food class to classes.txt and returns its 0-indexed ID."""
        food_name = food_name.lower().strip().replace(" ", "_")
        
        if not os.path.exists(self.classes_file):
            with open(self.classes_file, "w") as f:
                f.write(food_name + "\n")
            return 0

        with open(self.classes_file, "r") as f:
            classes = [line.strip() for line in f.readlines() if line.strip()]

        if food_name in classes:
            return classes.index(food_name)
        
        # Append class
        classes.append(food_name)
        with open(self.classes_file, "w") as f:
            f.write("\n".join(classes) + "\n")
        return len(classes) - 1

    def apply_user_correction(
        self,
        session: MealSession,
        addition_index: int,
        corrected_food_name: str,
        pending_image_path: str
    ) -> Dict[str, Any]:
        """
        Applies a user correction to a meal session, generates a YOLO annotation, 
        and moves the image to the training directory.
        """
        if addition_index >= len(session.history):
            raise IndexError("Addition index out of range for session history.")

        addition = session.history[addition_index]
        
        # Update the session record
        old_name = addition.food_name
        addition.food_name = corrected_food_name
        addition.confidence = 1.0  # Set to 1.0 since it is user-verified

        # Get or create the YOLO class ID
        class_id = self._get_or_create_class_id(corrected_food_name)

        # Generate Bounding Box in YOLO format: class_id x_center y_center width height (normalized)
        if addition.bounding_box:
            # We had a fallback bounding box from YOLO [xmin, ymin, xmax, ymax]
            xmin, ymin, xmax, ymax = addition.bounding_box
            x_center = (xmin + xmax) / 2.0
            y_center = (ymin + ymax) / 2.0
            width = xmax - xmin
            height = ymax - ymin
        else:
            # Default center box fallback (70% width/height of the frame)
            x_center = 0.5
            y_center = 0.5
            width = 0.7
            height = 0.7
            addition.bounding_box = [0.15, 0.15, 0.85, 0.85] # Store normalized xmin, ymin, xmax, ymax

        yolo_annotation_line = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"

        # Prepare filenames
        base_filename = os.path.basename(pending_image_path)
        name_no_ext, _ = os.path.splitext(base_filename)
        
        dest_image_path = os.path.join(self.trained_dir, base_filename)
        dest_annotation_path = os.path.join(self.trained_dir, f"{name_no_ext}.txt")

        # Write annotation file
        with open(dest_annotation_path, "w") as f:
            f.write(yolo_annotation_line)

        # Move image from pending to trained
        if os.path.exists(pending_image_path):
            shutil.move(pending_image_path, dest_image_path)
        else:
            print(f"[HitL Engine] Warning: Pending image not found at {pending_image_path}")

        print(f"[HitL Engine] Corrected {old_name} -> {corrected_food_name}. Annotation written to {dest_annotation_path}")

        return {
            "status": "success",
            "session_id": session.session_id,
            "corrected_item": corrected_food_name,
            "yolo_class_id": class_id,
            "image_moved_to": dest_image_path,
            "annotation_created_at": dest_annotation_path,
            "session": session.to_dict()
        }
