# ObjectTwin

ObjectTwin finds the image in a (nested) folder structure that **looks most similar**
to a reference image. It is built on Meta AI's self-supervised vision model
[DINOv2](https://github.com/facebookresearch/dinov2).

The end product is a standalone Windows application (`ObjectTwin.exe`) with a simple
user interface:

1. Select a reference image (TIFF is fully supported, as well as PNG, JPEG, BMP, …)
2. Check the preview
3. Select a search folder – all subfolders are searched recursively
4. Start the search → list of matches, ranked by similarity

## Status

| Step | Content                                      | State   |
|------|----------------------------------------------|---------|
| 1    | Project scaffold, tooling, docs              | ✅      |
| 2    | Image loading incl. TIFF                     | ✅      |
| 3    | DINOv2 embeddings & similarity search        | planned |
| 4    | GUI (selection, preview, search, results)    | planned |
| 5    | Build as `.exe` (PyInstaller)                | planned |
| 6    | User & developer documentation               | planned |

## Development

Requirements: Windows 10/11, [uv](https://docs.astral.sh/uv/) (installs Python 3.11 on demand).

```powershell
uv sync            # create virtual environment + install dependencies
uv run pytest      # tests
uv run ruff check  # linting
uv run ruff format # formatting
uv run objecttwin  # start the application
```

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
