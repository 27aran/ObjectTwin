# Third-party components

`ObjectTwin.exe` bundles the following third-party software and model weights. Their
license texts are shipped in the package metadata inside the `_internal` folder
(`*.dist-info`). This list is informational and not legal advice.

| Component | Version (0.1.0 build) | License | Notes |
|-----------|-----------------------|---------|-------|
| DINOv2 ViT-B/14 weights (`facebook/dinov2-base`, Meta AI) | – | Apache-2.0 | bundled model |
| PyTorch | 2.14 (cu126) / 2.15 (cpu) | BSD-3-Clause and others (Apache-2.0, MIT, BSL-1.0, Zlib, …) | |
| NVIDIA CUDA runtime, cuBLAS, cuDNN (inside the PyTorch CUDA wheel) | 12.6 / 9 | NVIDIA Software License Agreement (redistributable components) | GPU build only |
| Hugging Face transformers | 5.24 | Apache-2.0 | |
| huggingface_hub, safetensors, tokenizers | 2.4 / 0.8 / 0.23 | Apache-2.0 | |
| Qt for Python (PySide6-Essentials, shiboken6) and Qt 6 | 6.12 | LGPL-3.0-only | dynamically linked, shipped as separate DLLs, replaceable |
| NumPy | 2.4 | BSD-3-Clause and others | |
| Pillow | 13.0 | MIT-CMU (HPND) | |
| tifffile | 2026.3 | BSD-3-Clause | |
| imagecodecs (incl. bundled codec libraries) | 2026.3 | BSD-3-Clause; codecs under their own permissive licenses | |
| tqdm | 4.70 | MPL-2.0 AND MIT | |
| regex, packaging, filelock, PyYAML | – | Apache-2.0 / BSD / MIT | |
| Python | 3.11 | PSF License | |

**LGPL (Qt / PySide6):** the Qt libraries are used unmodified and loaded dynamically
from the `_internal` folder; users may replace them with compatible versions. The Qt
source code is available at <https://download.qt.io/>.

To regenerate the version / license list from a build environment:

```powershell
uv run python -c "import importlib.metadata as m; [print(d.metadata['Name'], d.version, d.metadata.get('License-Expression') or '') for d in m.distributions()]"
```
