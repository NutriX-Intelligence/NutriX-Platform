import os
import sys
import shutil
from backend.services.ingestion.cv_engine import NutriXCVEngine, MealSession
from backend.services.ingestion.hitl_engine import NutriXHitlEngine
from backend.services.ingestion.retrain_yolo import run_retraining

def main():
    if len(sys.argv) < 2:
        print("[Usage] Please provide an image that fails detection (e.g., a raw mango).")
        print("Example: .venv\\Scripts\\python run_hitl_interactive.py mango.jpg")
        return

    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(f"[Error] Image file not found: {img_path}")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Initialize CV Engine (mock_mode=False to run real inference)
    print("\n--- STEP 1: Running Initial Detection ---")
    cv_engine = NutriXCVEngine(confidence_threshold=0.75, mock_mode=False)
    hitl_engine = NutriXHitlEngine()
    session = MealSession()

    # Process image (simulate putting it on scale with weight 250g)
    success, res = cv_engine.process_scale_event(img_path, current_weight=250.0, session=session)
    
    if success and res["status"] == "identified":
        print(f"[Result] Model successfully recognized the item as: {res['addition']['food_name'].upper()} ({res['addition']['confidence']*100:.1f}%)")
        print("To test the HitL loop, please use an image of something the model DOES NOT recognize (like raw mango or paneer tikka).")
        return

    print(f"\n[Result] Detection Failed! Status: {res['status']}. Reason: {res['reason']}")
    print(f"Image successfully moved to pending queue: {res['pending_image_path']}")

    # 2. Simulate User Correction
    print("\n--- STEP 2: Human-in-the-Loop Correction ---")
    print(f"The item was added to session history as '{res['fallback_class'] or 'unidentified_item'}'.")
    
    # Ask the user for input in the console
    user_label = input("Enter the correct name for this food (e.g., 'raw_mango'): ").strip().lower()
    if not user_label:
        print("[Error] Label cannot be empty. Aborting.")
        return

    # Apply correction and generate annotations
    print(f"\nApplying correction '{user_label}'...")
    corr_res = hitl_engine.apply_user_correction(
        session=session,
        addition_index=res["addition_index"],
        corrected_food_name=user_label,
        pending_image_path=res["pending_image_path"]
    )
    print(f"YOLO Annotation created: {corr_res['annotation_created_at']}")
    print(f"Image moved to trained folder: {corr_res['image_moved_to']}")

    # 3. Trigger Retraining
    print("\n--- STEP 3: Retraining the Model (Fine-Tuning) ---")
    print("Fine-tuning model weights on your corrected image...")
    # Train for 3 epochs on the new image (fast on CPU, instant on GPU)
    retrain_success = run_retraining(epochs=3)
    
    if not retrain_success:
        print("[Error] Retraining failed.")
        return
    print("Retraining completed! New weights saved.")

    # 4. Re-run inference to prove it now works
    print("\n--- STEP 4: Verifying the Retrained Model ---")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    # Load the retrained weights (yolov8_retrained.pt is created by run_retraining)
    retrained_weights = os.path.join(base_dir, "backend", "services", "ingestion", "yolov8_retrained.pt")
    
    if not os.path.exists(retrained_weights):
        print(f"[Error] Retrained weights not found at: {retrained_weights}")
        return

    print("Re-running inference with the newly updated model...")
    updated_engine = NutriXCVEngine(model_path=retrained_weights, confidence_threshold=0.5, mock_mode=False)
    
    # Process the image again using the new weights
    success, final_res = updated_engine.process_scale_event(corr_res["image_moved_to"], current_weight=250.0, session=MealSession())
    
    print("\n" + "="*50)
    if success and final_res["status"] == "identified":
        print(f"🎉 SUCCESS! The model now successfully recognizes the image as:")
        print(f"👉 {final_res['addition']['food_name'].upper()} (Confidence: {final_res['addition']['confidence']*100:.1f}%)")
    else:
        print(f"❌ Failed. The model still did not detect the item. Status: {final_res['status']}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
