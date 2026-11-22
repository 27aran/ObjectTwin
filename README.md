# ObjectTwin

ObjectTwin finds the image in a (nested) folder structure that **looks most similar**
to a reference image. It is built on Meta AI's self-supervised vision model
[DINOv2](https://github.com/facebookresearch/dinov2).

The end product is a standalone Windows application (`ObjectTwin.exe`) with a simple
user interface:

1. Select a reference image (TIFF is fully supported, as well as PNG, JPEG, BMP, …)
2. Check the preview
3. Select a search folder – all subfolders are searched recursively
4. Start the search → list of candidates, ranked by similarity, with a confidence
   verdict (*confident* / *ambiguous – compare the alternatives* / *no good match*)

## Status

| Step | Content                                      | State   |
|------|----------------------------------------------|---------|
| 1    | Project scaffold, tooling, docs              | ✅      |
| 2    | Image loading incl. TIFF                     | ✅      |
| 3    | DINOv2 embeddings & similarity search        | ✅      |
| 4    | Confidence estimation (uncertainty)          | ✅      |
| 5    | GUI (selection, preview, search, results)    | planned |
| 6    | Build as `.exe` (PyInstaller)                | planned |
| 7    | User & developer documentation               | planned |

## Development

Requirements: Windows 10/11, [uv](https://docs.astral.sh/uv/) (installs Python 3.11 on demand).

```powershell
uv sync --extra cpu      # create virtual environment + install dependencies (CPU PyTorch)
uv run pytest            # fast tests (no model download)
uv run pytest -m model   # tests with the real DINOv2 model (downloads weights once)
uv run ruff check        # linting
uv run ruff format       # formatting
uv run objecttwin        # start the application
```

PyTorch is installed as one of two mutually exclusive extras:

| Extra   | Command                    | Use                                                   |
|---------|----------------------------|-------------------------------------------------------|
| `cpu`   | `uv sync --extra cpu`      | development, machines without NVIDIA GPU (small)      |
| `cu126` | `uv sync --extra cu126`    | NVIDIA GPU via CUDA 12.6 (large, ~2.5 GB)             |

The application always picks the GPU automatically when one is available and falls back
to the CPU otherwise.

### Command line

The search can also be run without the GUI:

```powershell
uv run python -m objecttwin.cli path\to\query.tif path\to\folder --top 5
```

Example output:

```
Verdict: AMBIGUOUS  (plausible candidates: 2, margin: 0.0127, z: 4.8, query variants: 9)
rank   score   ± std  votes  path
  1*  0.8004 ±0.0199   100%  data\batch_0\img_017_variant.tif
  2*  0.7877 ±0.0193     0%  data\batch_1\set_2\img_017.tif
  3   0.7126 ±0.0167     0%  data\batch_0\set_1\img_004.tif
(* = plausible: not significantly worse than the best match)
```

| Option          | Meaning                                                                     |
|-----------------|-----------------------------------------------------------------------------|
| `--top N`       | number of candidates to list (default 10)                                   |
| `--descriptor`  | `hybrid` (default), `global` or `spatial` – see [architecture](docs/architecture.md#descriptors) |
| `--no-augment`  | skip query augmentation (faster, no stability / vote estimates)             |
| `--model`       | Hugging Face name or local folder (default `facebook/dinov2-base`)          |
| `--device`      | `cuda` or `cpu` (default: automatic)                                        |
| `-v`            | debug logging                                                               |

## Project structure

```
ObjectTwin/
├── src/objecttwin/   # application code (package)
├── tests/            # pytest tests
├── docs/             # documentation
├── pyproject.toml    # metadata, dependencies, tool configuration
└── README.md
```

Architecture details: [docs/architecture.md](docs/architecture.md)
