# Architektur

## Ziel

Gegeben ein Referenzbild *q* und ein Wurzelordner *R*: finde unter allen Bildern in *R*
(rekursiv) dasjenige, dessen Inhalt *q* am ähnlichsten ist – unabhängig von Dateiname,
Auflösung oder Bittiefe.

## Ansatz

1. **Laden & Normalisieren** – Jedes Bild (insbesondere TIFF mit 8/16/32 bit, Graustufen,
   mehreren Kanälen oder Seiten) wird in ein einheitliches 8-bit-RGB-Bild überführt.
2. **Embedding** – DINOv2 (Vision Transformer) erzeugt pro Bild einen globalen
   Merkmalsvektor (CLS-Token). Die Vektoren werden L2-normalisiert.
3. **Vergleich** – Ähnlichkeit = Kosinus-Ähnlichkeit = Skalarprodukt der normierten
   Vektoren. Höchster Wert = ähnlichstes Bild.

DINOv2 eignet sich besonders, weil es ohne Labels trainiert wurde und dadurch
allgemeine visuelle Merkmale (Form, Textur, Struktur) gut erfasst – ideal für
Bild-zu-Bild-Retrieval.

## Module

| Modul                     | Verantwortung                                              |
|---------------------------|------------------------------------------------------------|
| `objecttwin.imageio`      | Bilder finden & laden, TIFF-Sonderfälle, Normalisierung auf RGB |
| `objecttwin.embedder`     | DINOv2 laden (gebündelt oder Download), Embeddings berechnen |
| `objecttwin.search`       | Ähnlichkeiten berechnen, Ranking                           |
| `objecttwin.gui`          | PySide6-Oberfläche, Hintergrund-Worker für die Suche       |
| `objecttwin.__main__`     | Einstiegspunkt                                             |

Die Kernlogik (`imageio`, `embedder`, `search`) ist GUI-unabhängig und separat testbar.

## Technologie

| Bereich       | Wahl                     | Begründung                                         |
|---------------|--------------------------|----------------------------------------------------|
| Sprache       | Python 3.11              | Ökosystem für PyTorch / DINOv2                     |
| Paketmanager  | uv                       | schnell, reproduzierbar (`uv.lock`)                |
| Modell        | DINOv2 via `transformers`| offizielle Gewichte, offline bündelbar             |
| TIFF          | Pillow + `tifffile`      | `tifffile` deckt 16/32-bit- & wissenschaftliche TIFFs ab |
| GUI           | PySide6 (Qt)             | native Optik, Threads, gute PyInstaller-Unterstützung |
| Paketierung   | PyInstaller              | erzeugt eigenständige `.exe`                       |

## Bild-Laden (`objecttwin.imageio`)

`load_image(path)` liefert immer ein 8-bit-RGB-Bild (`PIL.Image`).

| Fall                                  | Behandlung                                                   |
|---------------------------------------|--------------------------------------------------------------|
| TIFF (alle Varianten)                 | zuerst `tifffile` (+ `imagecodecs` für LZW, JPEG, Deflate …), bei Fehler Pillow |
| 16/32-bit-Integer, Float              | Kontraststreckung auf 0–255 (0,5 %- bis 99,5 %-Perzentil, robust gegen Ausreißer-Pixel) |
| NaN / ±Inf                            | werden auf den Rand des Wertebereichs gesetzt                |
| Graustufen / Grau + Alpha             | auf 3 identische Kanäle erweitert                            |
| Planares TIFF `(C, H, W)`             | in `(H, W, C)` umgeordnet                                    |
| Mehrseitig / Z-Stack / Pyramide       | erste Seite bzw. erste Ebene in voller Auflösung             |
| `MinIsWhite`-TIFF                     | invertiert                                                   |
| Transparenz (PNG, GIF …)              | auf weißen Hintergrund gelegt                                |
| JPEG mit EXIF-Drehung                 | Drehung wird angewendet                                      |

`find_images(root)` durchsucht `root` rekursiv und liefert alle unterstützten Dateien
(`.tif .tiff .png .jpg .jpeg .bmp .gif .webp`, Groß-/Kleinschreibung egal) in fester,
sortierter Reihenfolge.
