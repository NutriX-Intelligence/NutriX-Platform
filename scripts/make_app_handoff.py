"""
Build the package for the app developer: dist/nutrix_app_handoff.zip

    PYTHONPATH=. python scripts/make_app_handoff.py --base-url https://xxxx.trycloudflare.com

It regenerates the OpenAPI spec first, writes the base URL into the handoff page and the .http file, and contains
ONLY the five documents (never .env, datasets, model weights or source code).
"""
import argparse
import re
import zipfile
from pathlib import Path

from scripts.export_openapi import main as export_openapi

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "docs/APP_HANDOFF.md": "APP_HANDOFF.md",
    "docs/APP_BUILD_GUIDE.md": "APP_BUILD_GUIDE.md",
    "docs/API_CONTRACT.md": "API_CONTRACT.md",
    "docs/api/openapi_ms3.json": "openapi_ms3.json",
    "docs/api/nutrix_requests.http": "nutrix_requests.http",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="", help="the gateway URL the developer should use (https://... or http://<LAN-IP>:8000)")
    ap.add_argument("--email", default="dev@nutrix.dev")
    ap.add_argument("--password", default="nutrix123")
    args = ap.parse_args()

    export_openapi()

    out = ROOT / "dist" / "nutrix_app_handoff.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in FILES.items():
            text = (ROOT / src).read_text(encoding="utf-8")
            if name == "APP_HANDOFF.md" and args.base_url:
                text = re.sub(r"<<FILL IN:[^>]*>>", args.base_url, text)
                text = text.replace("dev@nutrix.dev   /   nutrix123", f"{args.email}   /   {args.password}")
            if name == "nutrix_requests.http":
                if args.base_url:
                    text = text.replace("@host = http://localhost:8000", f"@host = {args.base_url}")
                text = text.replace("@email = dev@nutrix.dev", f"@email = {args.email}").replace("@password = nutrix123", f"@password = {args.password}")
            z.writestr(name, text)
    print(f"\nWrote {out} ({out.stat().st_size / 1024:.0f} KB) containing: {', '.join(FILES.values())}")
    if "<<FILL IN" in zipfile.ZipFile(out).read("APP_HANDOFF.md").decode():
        print("NOTE: no --base-url given; the developer will see a placeholder for the backend address.")


if __name__ == "__main__":
    main()
