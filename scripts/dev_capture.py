#!/usr/bin/env python3
"""
NutriX Development & Testing Capture Utility (Pipeline 2: Software Mode)
=======================================================================
Simulates the ESP32 Smart Scale multipart ingest event without physical hardware.
Supports:
  1. Laptop Webcam: Live camera feed with interactive capture (SPACE) and weight prompt.
  2. Single Image: Send a specific test image with given weight.
  3. Image Folder: Batch test a directory of sample images.

Usage Examples:
  # Webcam mode (press SPACE to capture, terminal prompts for weight)
  python scripts/dev_capture.py --webcam

  # Single image mode
  python scripts/dev_capture.py --image dataset/pending/sample.jpg --weight 120.5

  # Batch directory mode
  python scripts/dev_capture.py --images dataset/pending/ --weight 150.0

  # Target Gateway instead of direct MS1
  python scripts/dev_capture.py --webcam --url http://localhost:8000/api/v1/ingest/weight-frame --token NutriX_ESP32_SECURE_TOKEN
"""

import os
import sys
import time
import json
import argparse
import webbrowser
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_MS1_URL = "http://localhost:8001/api/v1/ingest/weight-frame"
DEFAULT_ANNOTATED_URL = "http://localhost:8001/captures/annotated"


def run_session_reset(user_id: int = 1):
    """Resets today's test session meal logs and Redis macros if shared module is available."""
    try:
        from scripts.reset_test_session import reset_session
        reset_session(user_id=user_id, all_dates=False)
    except Exception as e:
        print(f"[Reset Notice] Auto-reset skipped or unavailable ({e}). Continuing...")


def open_in_browser(url: str):
    """Opens URL in browser, supporting Windows default browser from WSL2 cleanly."""
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    cmd_exe = "/mnt/c/windows/system32/cmd.exe"
                    if os.path.exists(cmd_exe):
                        import subprocess
                        subprocess.run([cmd_exe, "/c", "start", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return
        webbrowser.open(url)
    except Exception:
        pass


def send_frame_to_backend(
    image_bytes: bytes,
    filename: str,
    weight_g: float,
    url: str = DEFAULT_MS1_URL,
    user_id: int = 1,
    device_token: str = None,
    open_browser: bool = True
) -> dict:
    """
    Sends multipart POST request to NutriX ingest endpoint matching ESP32 payload structure.
    """
    headers = {
        "User-ID": str(user_id),
        "X-User-ID": str(user_id),
    }
    if device_token:
        headers["Device-Token"] = device_token
        headers["device-token"] = device_token

    files = {
        "image": (filename, image_bytes, "image/jpeg")
    }
    data = {
        "weight": str(weight_g)
    }

    print(f"\n[Sending] POST {url} | Weight: {weight_g:.1f}g | User: {user_id}...")
    start_time = time.time()

    try:
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        elapsed_ms = (time.time() - start_time) * 1000.0

        if response.status_code == 200:
            result = response.json()
            print("\n" + "="*65)
            print("         NUTRIX INGEST RESULT (HTTP 200 OK)")
            print("="*65)
            print(f"  • Status          : {result.get('status', 'N/A')}")
            print(f"  • Food Identified : {result.get('food_label', 'N/A')}")
            print(f"  • Confidence      : {result.get('confidence', 0.0)}%")
            print(f"  • Weight          : {result.get('weight_g', weight_g)} g")
            print(f"  • Calories        : {result.get('calories', 0.0)} kcal")
            print(f"  • Session ID      : {result.get('session_id', 'N/A')}")
            print(f"  • Latency         : {elapsed_ms:.1f} ms")
            print("="*65)

            if open_browser:
                try:
                    print(f"  [Viewer] Opening {DEFAULT_ANNOTATED_URL} in browser...")
                    open_in_browser(DEFAULT_ANNOTATED_URL)
                except Exception:
                    pass

            return result
        else:
            print(f"\n[ERROR] Request failed with HTTP {response.status_code}: {response.text}")
            return {"error": response.text, "status_code": response.status_code}
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to {url}.")
        print("Make sure MS1 is running:")
        print("  PYTHONPATH=. uvicorn ms1_cv.main:app --host 0.0.0.0 --port 8001 --reload")
        return {"error": "connection_refused"}
    except Exception as e:
        print(f"\n[ERROR] Unexpected error while sending request: {e}")
        return {"error": str(e)}


def prompt_weight(default_weight: float = 150.0) -> float:
    """Interactively prompts user for weight in terminal."""
    try:
        user_input = input(f"\n>>> Enter food weight in grams [default: {default_weight}g]: ").strip()
        if not user_input:
            return float(default_weight)
        return float(user_input)
    except ValueError:
        print(f"  Invalid number entered. Using default {default_weight}g.")
        return float(default_weight)


def run_webcam_mode(args):
    """Interactive webcam capture with OpenCV."""
    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV (cv2) is not installed. Run: pip install opencv-python")
        sys.exit(1)

    print(f"\n[Webcam] Opening camera index {args.camera_id}...")
    cap = cv2.VideoCapture(args.camera_id)

    if not cap.isOpened():
        print(f"\n{'!'*65}")
        print(f"[ERROR] Could not open webcam device (index {args.camera_id}).")
        print("If you are running inside WSL2:")
        print("  WSL2 does not have direct access to laptop webcams without USB pass-through.")
        print("  You have two easy options:")
        print("   1. Run this script in Windows PowerShell / Command Prompt:")
        print("      python scripts\\dev_capture.py --webcam")
        print("      (Windows accesses your camera and talks to MS1 at http://localhost:8001)")
        print("   2. Use sample image mode in WSL:")
        print("      python scripts/dev_capture.py --image <path/to/image.jpg> --weight 150")
        print("      python scripts/dev_capture.py --images dataset/pending/")
        print(f"{'!'*65}\n")
        return

    window_name = "NutriX Dev Capture (SPACE: Capture | Q: Quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    print("\n" + "-"*65)
    print("  WEBCAM ACTIVE")
    print("  • Focus on the 'NutriX Dev Capture' window")
    print("  • Press SPACE to freeze frame and trigger scale ingest")
    print("  • Press 'Q' or ESC to exit")
    print("-"*65)

    capture_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[Warning] Failed to read frame from webcam.")
                time.sleep(0.1)
                continue

            # Display HUD overlay
            hud_frame = frame.copy()
            cv2.rectangle(hud_frame, (0, 0), (hud_frame.shape[1], 40), (20, 20, 20), -1)
            cv2.putText(
                hud_frame,
                "NutriX Scale Sim | SPACE: Capture & Send | Q: Quit",
                (12, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 120),
                2
            )

            cv2.imshow(window_name, hud_frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:  # 'q' or ESC
                print("\n[Webcam] Exiting...")
                break
            elif key == ord(' '):  # SPACE pressed
                capture_count += 1
                print(f"\n[Webcam] Frame #{capture_count} captured!")

                # Visual freeze feedback
                freeze_display = hud_frame.copy()
                cv2.putText(
                    freeze_display,
                    "CAPTURED! Enter weight in terminal...",
                    (12, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 180, 255),
                    2
                )
                cv2.imshow(window_name, freeze_display)
                cv2.waitKey(200)

                # Prompt for weight in terminal
                if args.prompt_weight or args.weight is None:
                    weight_g = prompt_weight(default_weight=args.default_weight)
                else:
                    weight_g = float(args.weight)

                # Encode frame to JPEG
                success, encoded_img = cv2.imencode(".jpg", frame)
                if not success:
                    print("[ERROR] Failed to encode frame to JPEG.")
                    continue

                image_bytes = encoded_img.tobytes()
                filename = f"webcam_capture_{capture_count}_{int(time.time())}.jpg"

                send_frame_to_backend(
                    image_bytes=image_bytes,
                    filename=filename,
                    weight_g=weight_g,
                    url=args.url,
                    user_id=args.user_id,
                    device_token=args.token,
                    open_browser=not args.no_browser
                )
                print("\n[Webcam] Ready for next capture! (SPACE: Capture | Q: Quit)")

    finally:
        cap.release()
        cv2.destroyAllWindows()


def run_single_image_mode(args):
    """Sends a single image file with specified weight."""
    if not os.path.isfile(args.image):
        print(f"[ERROR] Image file not found: {args.image}")
        sys.exit(1)

    weight_g = args.weight
    if weight_g is None:
        if args.prompt_weight:
            weight_g = prompt_weight(default_weight=args.default_weight)
        else:
            weight_g = float(args.default_weight)

    with open(args.image, "rb") as f:
        image_bytes = f.read()

    filename = os.path.basename(args.image)
    send_frame_to_backend(
        image_bytes=image_bytes,
        filename=filename,
        weight_g=float(weight_g),
        url=args.url,
        user_id=args.user_id,
        device_token=args.token,
        open_browser=not args.no_browser
    )


def run_folder_mode(args):
    """Iterates through all images in a folder and sends them."""
    if not os.path.isdir(args.images):
        print(f"[ERROR] Directory not found: {args.images}")
        sys.exit(1)

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = sorted([
        f for f in os.listdir(args.images)
        if os.path.splitext(f.lower())[1] in valid_exts
    ])

    if not image_files:
        print(f"[Warning] No image files found in {args.images}")
        return

    print(f"\n[Folder Mode] Found {len(image_files)} images in {args.images}.")

    weight_g = args.weight or float(args.default_weight)

    for idx, fname in enumerate(image_files, start=1):
        fpath = os.path.join(args.images, fname)
        print(f"\n[{idx}/{len(image_files)}] Processing {fname}...")

        if args.prompt_weight:
            current_weight = prompt_weight(default_weight=weight_g)
        else:
            current_weight = weight_g

        with open(fpath, "rb") as f:
            image_bytes = f.read()

        send_frame_to_backend(
            image_bytes=image_bytes,
            filename=fname,
            weight_g=float(current_weight),
            url=args.url,
            user_id=args.user_id,
            device_token=args.token,
            open_browser=(idx == 1 and not args.no_browser)
        )
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(
        description="NutriX Pipeline 2 Dev Capture Tool (Simulate Smart Scale via Webcam or Images)"
    )
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--webcam", action="store_true", help="Capture live from laptop webcam with SPACE key")
    mode_group.add_argument("--image", type=str, help="Path to a single image to send")
    mode_group.add_argument("--images", type=str, help="Directory containing images to batch send")

    # Parameters
    parser.add_argument("--weight", type=float, default=None, help="Food weight in grams (if omitted, prompts in terminal)")
    parser.add_argument("--default-weight", type=float, default=150.0, help="Default weight if prompted (default: 150.0g)")
    parser.add_argument("--prompt-weight", action="store_true", help="Always prompt for weight in terminal")
    parser.add_argument("--camera-id", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--url", type=str, default=DEFAULT_MS1_URL, help=f"Ingest endpoint URL (default: {DEFAULT_MS1_URL})")
    parser.add_argument("--user-id", type=int, default=1, help="User ID header (default: 1)")
    parser.add_argument("--token", type=str, default=None, help="Device token (optional, needed when calling Gateway directly)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser to annotated viewer after send")
    parser.add_argument("--reset", action="store_true", default=False, help="Reset Postgres/Redis test data before starting (default: disabled to allow meal accumulation)")

    args = parser.parse_args()

    # If targeting Gateway (port 8000) and no token specified, default to standard device token
    if ":8000" in args.url and not args.token:
        args.token = os.environ.get("DEVICE_TOKEN", "NutriX_ESP32_SECURE_TOKEN")

    # Handle auto-reset
    if args.reset:
        run_session_reset(user_id=args.user_id)

    # Route mode
    if args.webcam:
        run_webcam_mode(args)
    elif args.image:
        run_single_image_mode(args)
    elif args.images:
        run_folder_mode(args)


if __name__ == "__main__":
    main()
