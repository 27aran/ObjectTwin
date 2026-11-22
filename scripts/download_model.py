"""Download the DINOv2 weights into models/dinov2-base (bundled into the exe).

    uv run python scripts/download_model.py [--force]

The folder contains ``config.json`` + ``model.safetensors`` (~350 MB) and is ignored by
git. With it present, the application and the CLI also work offline from source.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from objecttwin.resources import MODEL_ID, bundled_model_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()

    target = bundled_model_dir()
    if (target / "config.json").is_file() and not args.force:
        print(f"Model already present: {target}")
        return 0

    from transformers import Dinov2Model

    print(f"Downloading {MODEL_ID} ...")
    model = Dinov2Model.from_pretrained(MODEL_ID)
    if target.exists():
        shutil.rmtree(target)
    model.save_pretrained(target, safe_serialization=True)
    size_mb = sum(f.stat().st_size for f in target.iterdir()) / 1e6
    print(f"Saved to {target} ({size_mb:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
