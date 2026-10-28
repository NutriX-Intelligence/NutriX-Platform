"""
Export MS3's OpenAPI document for the app team (canonical /api/v1 routes only; the legacy aliases are hidden).

    PYTHONPATH=. python scripts/export_openapi.py            # writes docs/api/openapi_ms3.json
"""
import json
from pathlib import Path

from ms3_user.main import app


def main() -> None:
    spec = app.openapi()
    out = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi_ms3.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    paths = spec.get("paths", {})
    print(f"Wrote {out} ({len(paths)} paths, {sum(len(v) for v in paths.values())} operations)")


if __name__ == "__main__":
    main()
