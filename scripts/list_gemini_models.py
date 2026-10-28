"""
List the Gemini models your API key can call with generateContent (model names get retired often).

    PYTHONPATH=. python scripts/list_gemini_models.py

Put one of the printed names in .env as GEMINI_MODEL (and optionally others in GEMINI_FALLBACK_MODELS).
"""
import sys

import httpx

from shared import db as _env  # noqa: F401  (loads .env)
from ms3_user.services import gemini_client


def main() -> int:
    key = gemini_client.api_key()
    if not key:
        print("GEMINI_API_KEY is not set in .env")
        return 1
    try:
        r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models",
                      params={"pageSize": 200}, headers={"x-goog-api-key": key}, timeout=15)
    except httpx.HTTPError as e:
        print(f"Could not reach Google: {type(e).__name__}")
        return 1
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {gemini_client._error_message(r)}")
        return 1
    usable = sorted(m["name"].removeprefix("models/") for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", []))
    print(f"Configured: GEMINI_MODEL={gemini_client.models()[0]}  fallbacks={gemini_client.models()[1:]}")
    print(f"\n{len(usable)} model(s) support generateContent for this key:")
    for name in usable:
        mark = "  <- configured" if name in gemini_client.models() else ""
        print(f"  {name}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
