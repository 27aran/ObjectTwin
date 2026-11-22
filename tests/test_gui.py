"""GUI tests (headless via QT_QPA_PLATFORM=offscreen, see conftest)."""

import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from objecttwin.gui import i18n
from objecttwin.gui.main_window import COL_PLAUSIBLE, COL_RANK, MainWindow

from .conftest import FakeEmbedder, save_solid

RED, ORANGE, BLUE = (250, 10, 10), (240, 120, 20), (10, 10, 250)


class SlowEmbedder(FakeEmbedder):
    def embed_batch(self, pixels: np.ndarray) -> np.ndarray:
        time.sleep(0.05)
        return super().embed_batch(pixels)


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def data(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "data"
    save_solid(root / "a" / "red_copy.tif", RED)
    save_solid(root / "b" / "orange.png", ORANGE)
    save_solid(root / "blue.tiff", BLUE)
    return save_solid(tmp_path / "query.tif", RED), root


@pytest.fixture
def make_window(qtbot, settings):
    def factory(embedder_cls=FakeEmbedder) -> MainWindow:
        window = MainWindow(embedder_cls, settings)
        qtbot.addWidget(window)
        qtbot.waitUntil(lambda: window.search_button.isEnabled(), timeout=5000)
        return window

    yield factory
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def _search(qtbot, window: MainWindow, query: Path, folder: Path) -> None:
    assert window.set_query_image(query)
    window.folder_edit.setText(str(folder))
    window.search_button.click()
    qtbot.waitUntil(lambda: not window.is_searching(), timeout=10000)


def test_full_search_flow(qtbot, make_window, data) -> None:
    query, root = data
    window = make_window()
    _search(qtbot, window, query, root)

    assert window.table.rowCount() == 3
    assert window.table.item(0, 5).text() == str(Path("a") / "red_copy.tif")  # relative
    assert window.table.item(0, 5).toolTip() == str(root / "a" / "red_copy.tif")
    assert window.table.item(0, COL_RANK).text() == "1"
    assert window.table.item(0, COL_PLAUSIBLE).text() == "✓"
    assert not window.verdict_label.isHidden()
    assert window.cand_preview.has_image()  # first row auto-selected
    assert window.ref_preview.has_image()
    assert "3 images compared" in window.status_label.text()


def test_language_switch_updates_ui(qtbot, make_window, data) -> None:
    query, root = data
    window = make_window()
    _search(qtbot, window, query, root)

    window.set_language("de")
    assert window.search_button.text() == "Suchen"
    assert window.table.horizontalHeaderItem(5).text() == "Datei"
    assert "Bilder in " in window.status_label.text()
    assert "," in window.status_label.text().split("in ")[1]  # seconds with decimal comma
    assert "," in window.table.item(0, 2).text()  # decimal comma

    window.set_language("en")
    assert window.search_button.text() == "Search"


def test_settings_are_persisted(qtbot, make_window, data, settings) -> None:
    query, root = data
    window = make_window()
    window.set_query_image(query)
    window.folder_edit.setText(str(root))
    window.top_k_spin.setValue(7)
    window.set_language("de")
    window.close()

    restored = make_window()
    assert restored.folder_edit.text() == str(root)
    assert restored.top_k_spin.value() == 7
    assert restored.ref_preview.has_image()
    assert i18n.language() == "de"


def test_cancel(qtbot, make_window, data, tmp_path: Path) -> None:
    query, _ = data
    many = tmp_path / "many"
    for i in range(80):
        save_solid(many / f"img{i:02d}.png", (i * 3, 0, 0))
    window = make_window(SlowEmbedder)
    window.set_query_image(query)
    window.folder_edit.setText(str(many))
    window.search_button.click()
    assert window.is_searching()
    window.cancel_button.click()
    qtbot.waitUntil(lambda: not window.is_searching(), timeout=10000)
    assert window.table.rowCount() == 0
    assert window.status_label.text() == "Search cancelled."


def test_missing_folder_shows_message(qtbot, make_window, data, monkeypatch) -> None:
    query, _ = data
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: shown.append(args[2]))
    window = make_window()
    window.set_query_image(query)
    window.folder_edit.setText(str(query.parent / "does_not_exist"))
    window.search_button.click()
    assert shown and "folder" in shown[0]
    assert not window.is_searching()


def test_bad_query_image_is_rejected(qtbot, make_window, tmp_path: Path, monkeypatch) -> None:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[2]))
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"not an image")
    window = make_window()
    assert not window.set_query_image(bad)
    assert shown
    assert not window.ref_preview.has_image()


def test_developer_credit(qtbot, make_window) -> None:
    from objecttwin.about import AUTHOR, AUTHOR_URL, REPO_URL

    window = make_window()
    assert AUTHOR in window.credit_label.text()
    assert AUTHOR_URL in window.credit_label.text()
    assert REPO_URL in window.credit_label.text()
    assert window.act_source in window.help_menu.actions()
    assert window.credit_label.openExternalLinks()
    assert window.act_developer in window.help_menu.actions()
    window.set_language("de")
    assert window.credit_label.text().startswith("Entwickelt von")
    assert window.act_developer.text() == "Entwickler auf &LinkedIn"


def test_model_failure_is_reported(qtbot, settings) -> None:
    def broken():
        raise RuntimeError("no weights")

    window = MainWindow(broken, settings)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: "no weights" in window.status_label.text(), timeout=5000)
    assert not window.search_button.isEnabled()
