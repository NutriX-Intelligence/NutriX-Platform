"""
Integration check for MS2 (and the MS1 -> MS2 fallback). Run with MS2 (and optionally MS1) up.

  PYTHONPATH=. python scripts/test_ms2.py --image path/to/frame.jpg --weight 180
  PYTHONPATH=. python scripts/test_ms2.py --image path/to/lassi.jpg --weight 200 --via-ms1
  PYTHONPATH=. python scripts/test_ms2.py --lookup "paneer tikka" --lookup "murgh makhani"
"""
import argparse
import json
import subprocess
import sys
import time

import httpx

MS1 = "http://localhost:8001"
MS2 = "http://localhost:8003"


def gpu_mem() -> str:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], text=True
        ).strip()
        used, total = (int(x) for x in out.split(","))
        return f"{used} / {total} MiB ({used / total:.0%})"
    except Exception:
        return "n/a"


def show(title: str, r: httpx.Response, started: float) -> None:
    print(f"\n== {title}  [{r.status_code}, {time.time() - started:.2f}s]  GPU {gpu_mem()}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text[:500])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--weight", type=float, default=150.0)
    ap.add_argument("--yolo-hint")
    ap.add_argument("--lookup", action="append", default=[])
    ap.add_argument("--via-ms1", action="store_true", help="POST the frame to MS1 weight-frame instead of MS2 directly")
    args = ap.parse_args()

    print(f"GPU before: {gpu_mem()}")
    with httpx.Client(timeout=60) as c:
        h = c.get(f"{MS2}/health").json()
        print("MS2 health:", json.dumps(h.get("checks", {}).get("vlm"), indent=2))

        if args.image:
            with open(args.image, "rb") as f:
                img = f.read()
            t = time.time()
            if args.via_ms1:
                r = c.post(f"{MS1}/api/v1/ingest/weight-frame", files={"image": ("f.jpg", img, "image/jpeg")},
                           data={"weight": str(args.weight)}, headers={"X-User-ID": "1"})
                show("MS1 weight-frame", r, t)
            else:
                data = {"weight": str(args.weight), **({"yolo_hint": args.yolo_hint} if args.yolo_hint else {})}
                r = c.post(f"{MS2}/api/v1/llm/vision-infer", files={"image": ("f.jpg", img, "image/jpeg")}, data=data)
                show("MS2 vision-infer", r, t)

        for name in args.lookup:
            t = time.time()
            show(f"MS2 lookup '{name}'", c.post(f"{MS2}/api/v1/llm/lookup", json={"food_name": name}), t)

    print(f"\nGPU after: {gpu_mem()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
