"""Shared helpers for the dataset seeders."""
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# The ONE canonical dataset location (git-ignored). Fast-food workbooks live in DATA_DIR / "fast_food".
DATA_DIR = BASE_DIR / "dataset" / "ms3_datasets"


def require_files(*names: str, base: Optional[Path] = None) -> None:
    """Fail loudly when an expected dataset file is missing (seeders used to skip silently)."""
    base = base or DATA_DIR
    missing = [n for n in names if not (base / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing dataset file(s) in {base}: {', '.join(missing)}. "
            "Copy them there (see docs/tasks/tasks5.md, task 5.7.1) and re-run the seeders."
        )
