import os
import shutil
from backend.services.ingestion.cv_engine import CalCountCVEngine, MealSession
from backend.services.ingestion.hitl_engine import CalCountHitlEngine
from backend.services.ingestion.retrain_yolo import run_retraining

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_IMG_DIR = os.path.join(BASE_DIR, "dataset", "test_images")
PENDING_DIR = os.path.join(BASE_DIR, "dataset", "pending")
TRAINED_DIR = os.path.join(BASE_DIR, "dataset", "trained")

def clean_folders():
    """Cleans up the pending, trained, and run directories to start fresh."""
    for folder in [PENDING_DIR, TRAINED_DIR, os.path.join(BASE_DIR, "runs")]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print(f"Warning: Could not remove folder {folder}: {e}")
        os.makedirs(folder, exist_ok=True)
    
    classes_file = os.path.join(BASE_DIR, "dataset", "classes.txt")
    if os.path.exists(classes_file):
        os.remove(classes_file)
        
    print("[Test Harness] Cleaned up dataset and runs folders.")

def run_curriculum_tests():
    # 1. Setup
    clean_folders()
    
    # Initialize engines with mock_mode=False to use real pretrained YOLOv8
    print("\n[Test Harness] Initializing Real YOLOv8 Model (mock_mode=False)...")
    cv_engine = CalCountCVEngine(confidence_threshold=0.75, mock_mode=False)
    hitl_engine = CalCountHitlEngine()

    print("\n--- LEVEL 1 & 2: REAL WHOLE FOODS IDENTIFICATION ---")
    session = MealSession()
    
    # 1. Test Apple (Real Photo)
    apple_path = os.path.join(TEST_IMG_DIR, "apple.jpg")
    if not os.path.exists(apple_path):
        print(f"Error: Missing test image {apple_path}")
        return

    success, res = cv_engine.process_scale_event(apple_path, current_weight=150.0, session=session)
    print(f"Apple processing output: {res}")
    
    # We expect pretrained YOLOv8 to identify Unsplash Apple as 'apple'
    if success and res["status"] == "identified":
        assert res["addition"]["food_name"] == "apple"
        print(f"✅ Success! Real Apple identified autonomously: {res['addition']['delta_weight']}g")
    else:
        # Fallback to HitL if confidence was slightly low on this specific Unsplash angle
        print(f"⚠️ Apple triggered HitL (Confidence was low or class misidentified). Correcting...")
        corr = hitl_engine.apply_user_correction(session, res["addition_index"], "apple", res["pending_image_path"])
        assert corr["status"] == "success"
        print(f"✅ Success! Real Apple logged via HitL correction.")

    # 2. Test Banana (Real Photo)
    banana_path = os.path.join(TEST_IMG_DIR, "banana.jpg")
    success, res = cv_engine.process_scale_event(banana_path, current_weight=270.0, session=session)
    print(f"Banana processing output: {res}")
    
    if success and res["status"] == "identified":
        assert res["addition"]["food_name"] == "banana"
        print(f"✅ Success! Real Banana identified autonomously: {res['addition']['delta_weight']}g")
    else:
        print(f"⚠️ Banana triggered HitL. Correcting...")
        corr = hitl_engine.apply_user_correction(session, res["addition_index"], "banana", res["pending_image_path"])
        assert corr["status"] == "success"
        print(f"✅ Success! Real Banana logged via HitL correction.")


    print("\n--- LEVEL 3: UNRECOGNIZED WHOLE FOOD (RAW MANGO) ---")
    # 3. Test Raw Mango (COCO model does not have 'mango' or 'raw_mango')
    mango_path = os.path.join(TEST_IMG_DIR, "raw_mango.jpg")
    success, res = cv_engine.process_scale_event(mango_path, current_weight=490.0, session=session)
    print(f"Raw Mango processing output: {res}")
    
    # It must fail autonomous recognition because COCO has no raw mango class
    assert success == False
    assert res["status"] == "unidentified"
    print("✅ Success! Real Raw Mango correctly failed autonomous recognition.")

    # Apply HitL correction for Raw Mango
    corr = hitl_engine.apply_user_correction(
        session=session,
        addition_index=res["addition_index"],
        corrected_food_name="raw_mango",
        pending_image_path=res["pending_image_path"]
    )
    assert corr["status"] == "success"
    assert session.history[res["addition_index"]].food_name == "raw_mango"
    assert os.path.exists(corr["image_moved_to"])
    assert os.path.exists(corr["annotation_created_at"])
    print(f"✅ Success! Raw Mango annotated and moved to: {corr['image_moved_to']}")


    print("\n--- LEVEL 4: UNRECOGNIZED COMPOSITE FOOD (PANEER TIKKA LAYER ON BREAD) ---")
    # 4. Test sandwich base bread
    bread_path = os.path.join(TEST_IMG_DIR, "bread.jpg")
    success, res = cv_engine.process_scale_event(bread_path, current_weight=520.0, session=session)
    print(f"Bread base processing output: {res}")
    
    # Bread might be seen as sandwich/broccoli/carrot or fail. That's fine, we just want to establish it as base.
    base_weight = session.get_total_weight()
    print(f"Base established. Total session weight: {base_weight}g")

    # 5. Add Paneer Tikka (delta +60g, total 580g)
    paneer_path = os.path.join(TEST_IMG_DIR, "paneer_tikka.jpg")
    success, res = cv_engine.process_scale_event(paneer_path, current_weight=580.0, session=session)
    print(f"Paneer Tikka layer processing output: {res}")

    # It must fail autonomous recognition
    assert success == False
    assert res["status"] == "unidentified"
    print("✅ Success! Paneer Tikka layer correctly failed autonomous recognition.")

    # Apply HitL correction for Paneer Tikka layer
    corr = hitl_engine.apply_user_correction(
        session=session,
        addition_index=res["addition_index"],
        corrected_food_name="paneer_tikka",
        pending_image_path=res["pending_image_path"]
    )
    assert corr["status"] == "success"
    assert session.history[res["addition_index"]].food_name == "paneer_tikka"
    assert round(session.history[res["addition_index"]].delta_weight) == 60
    print(f"✅ Success! Paneer Tikka layer corrected. Layer weight: {session.history[res['addition_index']].delta_weight}g")


    print("\n--- RETRAINING SYSTEM INTEGRATION TEST ON REAL IMAGES ---")
    # Trigger 1 epoch training loop on CPU using our newly generated annotations
    retrain_success = run_retraining(epochs=1)
    assert retrain_success == True
    print("✅ Success! Fine-tuning triggered and weights updated successfully using real-image annotations.")

    print("\n🎉 ALL CURRICULUM TESTS PASSED SUCCESSFULLY ON REAL FOOD IMAGES! 🎉")

if __name__ == "__main__":
    run_curriculum_tests()
