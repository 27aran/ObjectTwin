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

## Module (geplant)

| Modul                     | Verantwortung                                              |
|---------------------------|------------------------------------------------------------|
| `objecttwin.imageio`      | Bilder laden, TIFF-Sonderfälle, Normalisierung auf RGB     |
| `objecttwin.embedder`     | DINOv2 laden (gebündelt oder Download), Embeddings berechnen |
| `objecttwin.search`       | Ordner rekursiv scannen, Ähnlichkeiten berechnen, Ranking  |
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
