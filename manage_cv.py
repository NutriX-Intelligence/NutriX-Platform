import os
import sys
import argparse
import shutil

# Ensure backend package can be imported when running from the root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.ingestion.cv_engine import NutriXCVEngine, MealSession
from backend.services.ingestion.hitl_engine import NutriXHitlEngine
from backend.services.ingestion.retrain_yolo import run_retraining

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOM_WEIGHTS = os.path.join(BASE_DIR, "backend", "services", "ingestion", "nutrix_yolo_custom.pt")
RETRAINED_WEIGHTS = os.path.join(BASE_DIR, "backend", "services", "ingestion", "yolov8_retrained.pt")

def get_best_available_weights():
    if os.path.exists(RETRAINED_WEIGHTS):
        print(f"[Model] Using retrained weights: {RETRAINED_WEIGHTS}")
        return RETRAINED_WEIGHTS
    elif os.path.exists(CUSTOM_WEIGHTS):
        print(f"[Model] Using baseline custom weights: {CUSTOM_WEIGHTS}")
        return CUSTOM_WEIGHTS
    else:
        print("[Warning] No custom or retrained weights found. Falling back to default 'yolov8n.pt'")
        return "yolov8n.pt"

def run_test_model(image_path, confidence_threshold=0.5):
    if not os.path.exists(image_path):
        print(f"[Error] Image not found: {image_path}")
        return
        
    weights = get_best_available_weights()
    print(f"\n--- Running Inference on {image_path} ---")
    
    # Initialize engine
    engine = NutriXCVEngine(model_path=weights, confidence_threshold=confidence_threshold, mock_mode=False)
    
    # Run the model directly
    from ultralytics import YOLO
    model = YOLO(weights)
    results = model(image_path)
    result = results[0]
    
    # Save the annotated result
    output_filename = "annotated_" + os.path.basename(image_path)
    output_path = os.path.join(BASE_DIR, output_filename)
    result.save(filename=output_path)
    
    print("\n--- Detected Objects ---")
    if len(result.boxes) == 0:
        print("No objects detected.")
    else:
        for box in result.boxes:
            class_id = int(box.cls[0])
            name = result.names[class_id]
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            print(f"- {name.upper()} (Confidence: {conf*100:.1f}%)")
            print(f"  Box: {xyxy}")
            
    print(f"\n[Success] Annotated image saved to: {output_path}")

def run_test_retraining(epochs=3):
    print("\n--- Starting Retraining fine-tuning ---")
    success = run_retraining(epochs=epochs)
    if success:
        print("🎉 Retraining completed successfully!")
    else:
        print("❌ Retraining failed or was aborted.")

def run_hitl_workflow(image_path, confidence_threshold=0.75):
    if not os.path.exists(image_path):
        print(f"[Error] Image not found: {image_path}")
        return

    weights = get_best_available_weights()
    print("\n--- STEP 1: Running Initial Detection ---")
    cv_engine = NutriXCVEngine(model_path=weights, confidence_threshold=confidence_threshold, mock_mode=False)
    hitl_engine = NutriXHitlEngine()
    session = MealSession()

    # Process image (simulate putting it on scale with weight 250g)
    success, res = cv_engine.process_scale_event(image_path, current_weight=250.0, session=session)
    
    if success and res["status"] == "identified":
        print(f"[Result] Model successfully recognized the item as: {res['addition']['food_name'].upper()} ({res['addition']['confidence']*100:.1f}%)")
        print("To test the HitL loop, please use an image of something the model DOES NOT recognize or lower the confidence threshold.")
        return

    print(f"\n[Result] Detection Failed! Status: {res['status']}. Reason: {res['reason']}")
    print(f"Image successfully moved to pending queue: {res['pending_image_path']}")

    # 2. Simulate User Correction
    print("\n--- STEP 2: Human-in-the-Loop Correction ---")
    print(f"The item was added to session history as '{res['fallback_class'] or 'unidentified_item'}'.")
    
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
    run_now = input("Trigger retraining fine-tuning now? (y/n) [y]: ").strip().lower()
    if run_now == 'n':
        print("Retraining skipped.")
        return
        
    epochs_input = input("Enter number of epochs [3]: ").strip()
    epochs = int(epochs_input) if epochs_input.isdigit() else 3
    
    print(f"Fine-tuning model weights for {epochs} epoch(s)...")
    retrain_success = run_retraining(epochs=epochs)
    
    if not retrain_success:
        print("[Error] Retraining failed.")
        return
    print("Retraining completed! New weights saved.")

    # 4. Re-run inference to prove it now works
    print("\n--- STEP 4: Verifying the Retrained Model ---")
    retrained_weights = os.path.join(BASE_DIR, "backend", "services", "ingestion", "yolov8_retrained.pt")
    
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

def interactive_menu():
    while True:
        print("\n====================================")
        print("     NutriX CV & HITL CLI         ")
        print("====================================")
        print("1. Simply Test the Model (Inference)")
        print("2. Test Retraining (Fine-Tuning)")
        print("3. Test HitL Workflow (Interactive)")
        print("4. Exit")
        print("====================================")
        
        choice = input("Enter choice (1-4): ").strip()
        if choice == "1":
            img = input("Enter image path: ").strip()
            conf = input("Enter confidence threshold [0.5]: ").strip()
            conf_val = float(conf) if conf else 0.5
            run_test_model(img, conf_val)
        elif choice == "2":
            epochs = input("Enter number of epochs [3]: ").strip()
            epochs_val = int(epochs) if epochs.isdigit() else 3
            run_test_retraining(epochs_val)
        elif choice == "3":
            img = input("Enter image path: ").strip()
            conf = input("Enter confidence threshold [0.75]: ").strip()
            conf_val = float(conf) if conf else 0.75
            run_hitl_workflow(img, conf_val)
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice, try again.")

def main():
    parser = argparse.ArgumentParser(description="NutriX CV and HITL Management Script")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # Sub-command: test
    parser_test = subparsers.add_parser("test", help="Test the model (inference)")
    parser_test.add_argument("image_path", type=str, help="Path to image file")
    parser_test.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    
    # Sub-command: retrain
    parser_retrain = subparsers.add_parser("retrain", help="Run retraining / fine-tuning")
    parser_retrain.add_argument("--epochs", type=int, default=3, help="Number of epochs to train")
    
    # Sub-command: hitl
    parser_hitl = subparsers.add_parser("hitl", help="Run human-in-the-loop workflow")
    parser_hitl.add_argument("image_path", type=str, help="Path to image file")
    parser_hitl.add_argument("--conf", type=float, default=0.75, help="Confidence threshold")
    
    args = parser.parse_args()
    
    if args.command is None:
        interactive_menu()
    elif args.command == "test":
        run_test_model(args.image_path, args.conf)
    elif args.command == "retrain":
        run_test_retraining(args.epochs)
    elif args.command == "hitl":
        run_hitl_workflow(args.image_path, args.conf)

if __name__ == "__main__":
    main()
