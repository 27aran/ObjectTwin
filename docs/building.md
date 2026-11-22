# Building `ObjectTwin.exe`

## TL;DR

```powershell
python scripts/build_exe.py --zip        # GPU build (CUDA 12.6) -> dist\ObjectTwin-cu126.zip
python scripts/build_exe.py --cpu --zip  # CPU-only build        -> dist\ObjectTwin-cpu.zip
```

Requirements: Windows 10/11 x64, [uv](https://docs.astral.sh/uv/) on `PATH`, internet
access for the first build (PyTorch wheels, model weights). **No GPU is needed to build
the GPU variant** – the CUDA runtime ships inside the PyTorch wheel.

**Duration:** 40–50 min per variant on a laptop (Core Ultra 7), most of it PyInstaller
analysing the thousands of modules of PyTorch; the first GPU build additionally
downloads ~2.5 GB of PyTorch wheels. Real-time virus scanning of the project folder
slows this down noticeably.

## What the script does

1. Creates a **separate** virtual environment `.venv-build-<variant>` with the chosen
   PyTorch flavour and PyInstaller (`uv sync --extra <variant> --no-dev --group build`).
   The development environment `.venv` is not touched.
2. Downloads the model weights once into `models/dinov2-base`
   (`scripts/download_model.py`, ~350 MB, git-ignored).
3. Runs PyInstaller with [`packaging/objecttwin.spec`](../packaging/objecttwin.spec) →
   `dist/<variant>/ObjectTwin/`.
4. Runs `ObjectTwin.exe --self-test` and prints the report (exit code ≠ 0 fails the build).
5. With `--zip`: packs the folder into `dist/ObjectTwin-<variant>.zip`.

## Variants

| Variant          | Command                        | PyTorch           | Runs on                                      |
|------------------|--------------------------------|-------------------|----------------------------------------------|
| `cu126` (default)| `build_exe.py`                 | CUDA 12.6         | NVIDIA GPU (driver ≥ 525, Maxwell … Hopper incl. Quadro RTX 4000); falls back to CPU automatically |
| `cpu`            | `build_exe.py --cpu`           | CPU only          | any x64 machine – much smaller, slower        |

Measured sizes (v0.1.0): `cu126` folder 4.7 GB, zip 3.0 GB · `cpu` folder 1.0 GB.
Start-up: the window appears immediately; the model loads in the background
(first start after unpacking ~1 min because the virus scanner checks the new DLLs,
afterwards ~15–20 s on a laptop CPU, faster with a GPU).

## Packaging decisions

| Decision | Reason |
|----------|--------|
| **One-folder**, not one-file | A one-file exe would unpack several GB into `%TEMP%` on *every* start (30–60 s). The folder starts in seconds. |
| Model weights **bundled** (`_internal/models/dinov2-base`) | Works offline; `HF_HUB_OFFLINE` is set automatically when a local model is used. |
| `console=False` (windowed) | No console window. Logs go to `%LOCALAPPDATA%\ObjectTwin\logs`. |
| `torch` / `transformers` collected as `pyz+py` | Both inspect their own source code at runtime. |
| Package **metadata** copied (`copy_metadata`) | `transformers` checks dependency versions via `importlib.metadata` on import. |
| `imagecodecs` submodules as hidden imports | `tifffile` imports codecs (LZW, JPEG, …) dynamically. |
| Unused `transformers.models.*` excluded | `transformers/models/__init__.py` imports all ~560 architectures under `if TYPE_CHECKING`; only `dinov2` (+ `auto`) is shipped. Saves ~55 MB. |
| No UPX | UPX corrupts CUDA DLLs and slows start-up. |
| `PySide6-Essentials` instead of `PySide6` | Avoids shipping WebEngine & co. (hundreds of MB). |

## Distributing

Copy/unzip the whole `ObjectTwin` folder anywhere (e.g. `C:\Tools\ObjectTwin`) and
start `ObjectTwin.exe`. No installation, no admin rights, no Python needed.

## Verifying an installation – `--self-test`

```powershell
ObjectTwin.exe --self-test
```

Runs without a window and writes `%LOCALAPPDATA%\ObjectTwin\logs\selftest.txt`:

```
[ OK ] PyTorch / CUDA: torch 2.14.1+cu126, CUDA build 12.6, GPU: Quadro RTX 4000 (sm_75)
[ OK ] Load model: ...\_internal\models\dinov2-base on Quadro RTX 4000 (CUDA), descriptor hybrid
[ OK ] 16-bit TIFF -> embedding: dim 49920, sim(rotated)=0.88, ...
[ OK ] Throughput: ... images/s
[ OK ] Qt: PySide6 6.x
RESULT: PASSED
```

Exit code 0 = everything works. If the GPU line says *no usable GPU*, the NVIDIA driver
is missing or older than 525 – the application still works on the CPU.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Model not found ... run scripts/download_model.py first` | the script does this automatically; check internet access |
| Self-test `FAIL` with `ModuleNotFoundError` | add the module to `hiddenimports` in the spec |
| `PackageNotFoundError` for some package | add it to the `copy_metadata` list in the spec |
| GPU not used on the target machine | update the NVIDIA driver (≥ 525), run `--self-test` |
| Want a different model | set `OBJECTTWIN_MODEL` (folder or HF id) or change `MODEL_ID` in `objecttwin/resources.py` and rebuild |
