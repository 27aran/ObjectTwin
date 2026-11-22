"""Minimal runtime translation (English / German).

A plain dictionary instead of Qt's .ts/.qm tool chain: two languages, a few dozen
strings, switchable at runtime without restart. Every key must exist in every language
(enforced by a unit test).
"""

from __future__ import annotations

LANGUAGES: dict[str, str] = {"en": "English", "de": "Deutsch"}
DEFAULT_LANGUAGE = "en"

_STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ menus
    "menu.file": {"en": "&File", "de": "&Datei"},
    "menu.settings": {"en": "&Settings", "de": "&Einstellungen"},
    "menu.language": {"en": "&Language", "de": "&Sprache"},
    "menu.help": {"en": "&Help", "de": "&Hilfe"},
    "action.open_image": {"en": "Select &reference image…", "de": "&Referenzbild wählen…"},
    "action.choose_folder": {"en": "Select search &folder…", "de": "Such&ordner wählen…"},
    "action.exit": {"en": "E&xit", "de": "&Beenden"},
    "action.open_log": {"en": "Open &log folder", "de": "&Log-Ordner öffnen"},
    "action.about": {"en": "&About ObjectTwin", "de": "&Über ObjectTwin"},
    "action.developer": {"en": "Developer on &LinkedIn", "de": "Entwickler auf &LinkedIn"},
    "action.source": {"en": "Source code on &GitHub", "de": "Quellcode auf &GitHub"},
    # ------------------------------------------------------------------ reference image
    "ref.title": {"en": "Reference image", "de": "Referenzbild"},
    "ref.none": {
        "en": "No image selected\n\nClick “Select image…” or drop a file here",
        "de": "Kein Bild ausgewählt\n\n„Bild wählen…“ klicken oder Datei hierher ziehen",
    },
    "ref.browse": {"en": "Select image…", "de": "Bild wählen…"},
    "ref.info": {"en": "{name} · {w} × {h} px", "de": "{name} · {w} × {h} px"},
    # ------------------------------------------------------------------ candidate
    "cand.title": {"en": "Selected candidate", "de": "Ausgewählter Kandidat"},
    "cand.none": {
        "en": "Select a result below to compare it with the reference image",
        "de": "Ein Ergebnis unten auswählen, um es mit dem Referenzbild zu vergleichen",
    },
    "cand.open": {"en": "Open", "de": "Öffnen"},
    "cand.show_in_folder": {"en": "Show in folder", "de": "Im Ordner zeigen"},
    # ------------------------------------------------------------------ search controls
    "folder.label": {"en": "Search folder:", "de": "Suchordner:"},
    "folder.placeholder": {
        "en": "Folder to search – all subfolders are included",
        "de": "Zu durchsuchender Ordner – alle Unterordner werden einbezogen",
    },
    "folder.browse": {"en": "Browse…", "de": "Durchsuchen…"},
    "opt.top_k": {"en": "Candidates:", "de": "Kandidaten:"},
    "opt.mode": {"en": "Comparison:", "de": "Vergleich:"},
    "mode.hybrid": {"en": "Hybrid (recommended)", "de": "Hybrid (empfohlen)"},
    "mode.global": {"en": "Global – robust to position", "de": "Global – robust gegen Lage"},
    "mode.spatial": {"en": "Spatial – fine detail", "de": "Räumlich – feine Details"},
    "mode.tooltip": {
        "en": "Hybrid combines both. Global ignores where things are in the image;\n"
        "Spatial compares the image region by region and catches fine differences.",
        "de": "Hybrid kombiniert beides. Global ignoriert, wo sich etwas im Bild befindet;\n"
        "Räumlich vergleicht Bereich für Bereich und erkennt feine Unterschiede.",
    },
    "btn.search": {"en": "Search", "de": "Suchen"},
    "btn.cancel": {"en": "Cancel", "de": "Abbrechen"},
    # ------------------------------------------------------------------ status
    "status.loading_model": {
        "en": "Loading model… (the first start may download about 350 MB)",
        "de": "Lade Modell… (beim ersten Start werden evtl. ca. 350 MB geladen)",
    },
    "status.model_ready": {
        "en": "Ready – model runs on {device}",
        "de": "Bereit – Modell läuft auf {device}",
    },
    "status.model_failed": {
        "en": "The model could not be loaded: {error}",
        "de": "Das Modell konnte nicht geladen werden: {error}",
    },
    "status.scanning": {"en": "Scanning folder…", "de": "Durchsuche Ordner…"},
    "status.searching": {
        "en": "Comparing images… {done} / {total}",
        "de": "Vergleiche Bilder… {done} / {total}",
    },
    "status.cancelling": {"en": "Cancelling…", "de": "Breche ab…"},
    "status.cancelled": {"en": "Search cancelled.", "de": "Suche abgebrochen."},
    "status.done": {
        "en": "{scanned} images compared in {seconds} s",
        "de": "{scanned} Bilder in {seconds} s verglichen",
    },
    # ------------------------------------------------------------------ verdict
    "verdict.confident": {
        "en": "✔ Clear match: “{name}” stands out from all other images.",
        "de": "✔ Eindeutiger Treffer: „{name}“ hebt sich deutlich von allen anderen ab.",
    },
    "verdict.ambiguous": {
        "en": "⚠ Not unique: {n} candidates are similarly plausible (marked ✓) – "
        "please compare them.",
        "de": "⚠ Nicht eindeutig: {n} Kandidaten sind ähnlich plausibel (mit ✓ markiert) – "
        "bitte vergleichen.",
    },
    "verdict.no_match": {
        "en": "✖ No candidate clearly stands out – the image may not be in this folder. "
        "Check the candidates carefully.",
        "de": "✖ Kein Kandidat sticht deutlich heraus – das Bild ist evtl. nicht im Ordner. "
        "Kandidaten bitte sorgfältig prüfen.",
    },
    "verdict.empty": {
        "en": "No images found in the selected folder.",
        "de": "Im gewählten Ordner wurden keine Bilder gefunden.",
    },
    # ------------------------------------------------------------------ results table
    "col.rank": {"en": "#", "de": "#"},
    "col.preview": {"en": "Preview", "de": "Vorschau"},
    "col.score": {"en": "Similarity", "de": "Ähnlichkeit"},
    "col.votes": {"en": "Agreement", "de": "Übereinstimmung"},
    "col.plausible": {"en": "Plausible", "de": "Plausibel"},
    "col.path": {"en": "File", "de": "Datei"},
    "tip.score": {
        "en": "Mean cosine similarity over all query variants ± standard deviation "
        "(1.0 = identical)",
        "de": "Mittlere Kosinus-Ähnlichkeit über alle Anfrage-Varianten ± Standardabweichung "
        "(1,0 = identisch)",
    },
    "tip.votes": {
        "en": "Share of slightly altered query variants for which this image ranked first",
        "de": "Anteil leicht veränderter Anfrage-Varianten, bei denen dieses Bild auf Platz 1 lag",
    },
    "tip.plausible": {
        "en": "✓ = not significantly worse than the best match",
        "de": "✓ = nicht signifikant schlechter als der beste Treffer",
    },
    # ------------------------------------------------------------------ skipped files
    "skipped.button": {"en": "{n} file(s) skipped…", "de": "{n} Datei(en) übersprungen…"},
    "skipped.title": {"en": "Skipped files", "de": "Übersprungene Dateien"},
    "skipped.text": {
        "en": "These files could not be read and were ignored:",
        "de": "Diese Dateien konnten nicht gelesen werden und wurden ignoriert:",
    },
    # ------------------------------------------------------------------ dialogs / errors
    "dialog.open_image": {"en": "Select reference image", "de": "Referenzbild wählen"},
    "dialog.image_filter": {"en": "Images", "de": "Bilder"},
    "dialog.all_files": {"en": "All files", "de": "Alle Dateien"},
    "dialog.choose_folder": {"en": "Select search folder", "de": "Suchordner wählen"},
    "error.title": {"en": "ObjectTwin – Error", "de": "ObjectTwin – Fehler"},
    "error.load_image": {
        "en": "The image could not be loaded:\n\n{error}",
        "de": "Das Bild konnte nicht geladen werden:\n\n{error}",
    },
    "error.no_image": {
        "en": "Please select a reference image first.",
        "de": "Bitte zuerst ein Referenzbild wählen.",
    },
    "error.no_folder": {
        "en": "Please select an existing search folder.",
        "de": "Bitte einen existierenden Suchordner wählen.",
    },
    "error.model_not_ready": {
        "en": "The model is still loading – please wait a moment.",
        "de": "Das Modell wird noch geladen – bitte einen Moment warten.",
    },
    "error.search": {
        "en": "The search failed:\n\n{error}",
        "de": "Die Suche ist fehlgeschlagen:\n\n{error}",
    },
    "about.title": {"en": "About ObjectTwin", "de": "Über ObjectTwin"},
    "about.text": {
        "en": "<h3>ObjectTwin {version}</h3>"
        "<p>Finds the images in a folder tree that look most similar to a reference image, "
        "using the DINOv2 vision model by Meta AI.</p>"
        "<p>Model: {model}<br>Device: {device}</p>"
        '<p>Developed by <a href="{author_url}">{author}</a><br>'
        'Source code: <a href="{repo_url}">{repo_label}</a><br>{license}</p>',
        "de": "<h3>ObjectTwin {version}</h3>"
        "<p>Findet in einer Ordnerstruktur die Bilder, die einem Referenzbild am ähnlichsten "
        "sind – mit dem Bildmodell DINOv2 von Meta AI.</p>"
        "<p>Modell: {model}<br>Gerät: {device}</p>"
        '<p>Entwickelt von <a href="{author_url}">{author}</a><br>'
        'Quellcode: <a href="{repo_url}">{repo_label}</a><br>{license}</p>',
    },
    "about.not_loaded": {"en": "not loaded yet", "de": "noch nicht geladen"},
    "about.credit": {
        "en": 'Developed by <a href="{author_url}">{author}</a> · <a href="{repo_url}">GitHub</a>',
        "de": 'Entwickelt von <a href="{author_url}">{author}</a>'
        ' · <a href="{repo_url}">GitHub</a>',
    },
    "about.credit_tip": {
        "en": "Developer's LinkedIn profile and the source code on GitHub",
        "de": "LinkedIn-Profil des Entwicklers und Quellcode auf GitHub",
    },
}

_language = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _language
    if code not in LANGUAGES:
        raise ValueError(f"Unsupported language {code!r}")
    _language = code


def language() -> str:
    return _language


def tr(key: str, **kwargs: object) -> str:
    """Translate *key* into the current language and format it with *kwargs*."""
    entry = _STRINGS[key]
    text = entry.get(_language) or entry[DEFAULT_LANGUAGE]
    return text.format(**kwargs) if kwargs else text


def all_keys() -> dict[str, dict[str, str]]:
    """All translation entries (for tests)."""
    return _STRINGS
