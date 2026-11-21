# ObjectTwin

ObjectTwin findet in einer (verschachtelten) Ordnerstruktur das Bild, das einem
Referenzbild **visuell am ähnlichsten** ist. Grundlage ist das selbstüberwachte
Vision-Modell [DINOv2](https://github.com/facebookresearch/dinov2) von Meta AI.

Das Ergebnis ist eine eigenständige Windows-Anwendung (`ObjectTwin.exe`) mit einer
einfachen Oberfläche:

1. Referenzbild auswählen (TIFF wird vollständig unterstützt, außerdem PNG, JPEG, BMP, …)
2. Vorschau prüfen
3. Suchordner auswählen – alle Unterordner werden rekursiv durchsucht
4. Suche starten → Trefferliste, sortiert nach Ähnlichkeit

## Status

| Schritt | Inhalt                                   | Stand   |
|---------|------------------------------------------|---------|
| 1       | Projektgerüst, Tooling, Doku-Grundlage   | ✅      |
| 2       | Bild-Laden inkl. TIFF                    | geplant |
| 3       | DINOv2-Embeddings & Ähnlichkeitssuche    | geplant |
| 4       | GUI (Auswahl, Vorschau, Suche, Treffer)  | geplant |
| 5       | Build als `.exe` (PyInstaller)           | geplant |
| 6       | Benutzer- & Entwicklerdokumentation      | geplant |

## Entwicklung

Voraussetzungen: Windows 10/11, [uv](https://docs.astral.sh/uv/) (installiert Python 3.11 bei Bedarf selbst).

```powershell
uv sync            # virtuelle Umgebung + Abhängigkeiten installieren
uv run pytest      # Tests
uv run ruff check  # Linting
uv run ruff format # Formatierung
uv run objecttwin  # Anwendung starten
```

## Projektstruktur

```
ObjectTwin/
├── src/objecttwin/   # Anwendungscode (Package)
├── tests/            # pytest-Tests
├── docs/             # Dokumentation
├── pyproject.toml    # Metadaten, Abhängigkeiten, Tool-Konfiguration
└── README.md
```

Details zum Aufbau: [docs/architecture.md](docs/architecture.md)
