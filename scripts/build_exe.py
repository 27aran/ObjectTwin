"""Build ObjectTwin.exe (PyInstaller, one-folder).

    python scripts/build_exe.py            # GPU build (CUDA 12.6, falls back to CPU)
    python scripts/build_exe.py --cpu      # CPU-only build (much smaller)
    python scripts/build_exe.py --zip      # additionally create a .zip for distribution

Steps:
1. create/refresh a *separate* virtual environment ``.venv-build-<variant>`` with the
   chosen PyTorch variant + PyInstaller (the development ``.venv`` stays untouched),
2. download the model weights into ``models/`` (once),
3. run PyInstaller -> ``dist/<variant>/ObjectTwin/ObjectTwin.exe``,
4. run ``ObjectTwin.exe --self-test`` and print the report,
5. optionally zip the folder.

Only needs ``uv`` on PATH; uses nothing but the standard library itself.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = "ObjectTwin"


def run(cmd: list[str], env: dict[str, str]) -> None:
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def folder_size_mb(folder: Path) -> float:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6


def self_test(exe: Path) -> bool:
    report = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP / "logs" / "selftest.txt"
    report.unlink(missing_ok=True)
    print(f"\n>>> {exe} --self-test", flush=True)
    code = subprocess.run([str(exe), "--self-test"], cwd=exe.parent).returncode
    if report.is_file():
        print(report.read_text(encoding="utf-8"))
    else:
        print(f"(no report found at {report})")
    return code == 0


def make_zip(folder: Path, target: Path) -> None:
    print(f"\n>>> zipping to {target} ...", flush=True)
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                zf.write(file, Path(APP) / file.relative_to(folder))
    print(f"    {target.stat().st_size / 1e6:.0f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ObjectTwin.exe")
    parser.add_argument("--cpu", action="store_true", help="CPU-only PyTorch (small build)")
    parser.add_argument("--zip", action="store_true", help="also create a zip archive")
    parser.add_argument("--skip-self-test", action="store_true")
    args = parser.parse_args()

    if shutil.which("uv") is None:
        print("uv not found on PATH - see https://docs.astral.sh/uv/", file=sys.stderr)
        return 2

    variant = "cpu" if args.cpu else "cu126"
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(ROOT / f".venv-build-{variant}")}
    started = time.perf_counter()

    run(["uv", "sync", "--extra", variant, "--no-dev", "--group", "build"], env)
    run(["uv", "run", "--no-sync", "python", "scripts/download_model.py"], env)
    run(
        [
            "uv", "run", "--no-sync", "pyinstaller", "packaging/objecttwin.spec",
            "--noconfirm", "--clean",
            "--distpath", f"dist/{variant}",
            "--workpath", f"build/{variant}",
        ],
        env,
    )  # fmt: skip

    folder = ROOT / "dist" / variant / APP
    exe = folder / f"{APP}.exe"
    print(f"\nBuilt {exe} ({folder_size_mb(folder):.0f} MB)")

    ok = True
    if not args.skip_self_test:
        ok = self_test(exe)
        print("Self-test PASSED" if ok else "Self-test FAILED")

    if args.zip and ok:
        make_zip(folder, ROOT / "dist" / f"{APP}-{variant}.zip")

    print(f"\nDone in {(time.perf_counter() - started) / 60:.1f} min")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
