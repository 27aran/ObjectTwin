# PyInstaller spec for ObjectTwin.exe (one-folder, windowed).
#
# Do not call directly - use `python scripts/build_exe.py`, which prepares the build
# environment and the model weights first.

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH is injected by PyInstaller
SRC = ROOT / "src"
MODEL_DIR = ROOT / "models" / "dinov2-base"
ICON = SRC / "objecttwin" / "assets" / "objecttwin.ico"

if not (MODEL_DIR / "config.json").is_file():
    raise SystemExit(f"Model not found in {MODEL_DIR} - run scripts/download_model.py first")

datas = [
    (str(MODEL_DIR), "models/dinov2-base"),
    (str(SRC / "objecttwin" / "assets"), "objecttwin/assets"),
]
# transformers checks the versions of these packages at import time -> needs their metadata.
for package in (
    "transformers",
    "tqdm",
    "regex",
    "packaging",
    "filelock",
    "numpy",
    "tokenizers",
    "huggingface-hub",
    "safetensors",
    "pyyaml",
    "torch",
    "objecttwin",
):
    datas += copy_metadata(package)

hiddenimports = [
    "transformers.models.dinov2",
    "transformers.models.dinov2.configuration_dinov2",
    "transformers.models.dinov2.modeling_dinov2",
    *collect_submodules("imagecodecs"),  # tifffile loads codecs dynamically
]

# transformers/models/__init__.py imports all ~560 architectures under `if TYPE_CHECKING`.
# At runtime they are loaded lazily, but PyInstaller's static analysis follows those
# imports - doubling the build time and bloating the bundle. Only DINOv2 (+ the `auto`
# registry, referenced by transformers internals) is needed.
_KEEP_MODELS = {"dinov2", "auto"}
_models_dir = Path(importlib.util.find_spec("transformers.models").origin).parent
unused_models = sorted(
    f"transformers.models.{d.name}"
    for d in _models_dir.iterdir()
    if d.is_dir() and not d.name.startswith("_") and d.name not in _KEEP_MODELS
)

excludes = [
    *unused_models,
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "jax",
    "flax",
    "sklearn",
    "pandas",
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    # torch / transformers inspect their own source code at runtime -> ship the .py files.
    module_collection_mode={"torch": "pyz+py", "transformers": "pyz+py"},
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ObjectTwin",
    icon=str(ICON),
    console=False,
    upx=False,  # UPX breaks CUDA/torch DLLs and slows start-up
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="ObjectTwin",
)
