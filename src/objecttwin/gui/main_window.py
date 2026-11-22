"""Main application window."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from objecttwin import __version__
from objecttwin.appdirs import log_dir
from objecttwin.descriptor import DEFAULT_DESCRIPTOR, Descriptor
from objecttwin.gui import i18n
from objecttwin.gui.i18n import tr
from objecttwin.gui.widgets import ImagePreview
from objecttwin.gui.workers import ModelLoader, SearchWorker, load_thumbnail, pil_to_qimage
from objecttwin.imageio import SUPPORTED_EXTENSIONS, ImageLoadError, is_supported, load_image
from objecttwin.search import DEFAULT_TOP_K, SearchResult, SupportsEmbedding
from objecttwin.uncertainty import Verdict

log = logging.getLogger(__name__)

QUERY_PREVIEW_SIZE = 1024
ROW_ICON_SIZE = 96

COL_RANK, COL_PREVIEW, COL_SCORE, COL_VOTES, COL_PLAUSIBLE, COL_PATH = range(6)
_COLUMNS = [
    ("col.rank", None),
    ("col.preview", None),
    ("col.score", "tip.score"),
    ("col.votes", "tip.votes"),
    ("col.plausible", "tip.plausible"),
    ("col.path", None),
]
_MODES = [
    (Descriptor.HYBRID, "mode.hybrid"),
    (Descriptor.GLOBAL, "mode.global"),
    (Descriptor.SPATIAL, "mode.spatial"),
]
# (background, text, accent) per verdict
_VERDICT_STYLE = {
    Verdict.CONFIDENT: ("#e6f4ea", "#1e5c31", "#2e9b4f"),
    Verdict.AMBIGUOUS: ("#fff4e0", "#7a4a00", "#f0a020"),
    Verdict.NO_MATCH: ("#fde8e8", "#8b1a1a", "#e04545"),
    Verdict.EMPTY: ("#eeeeee", "#444444", "#999999"),
}
_PLAUSIBLE_TINT = QColor(46, 160, 67, 40)


def _fmt(value: float, digits: int = 3) -> str:
    """Locale-aware number formatting (decimal comma in German)."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if i18n.language() == "de" else text


class MainWindow(QMainWindow):
    """Select a reference image and a folder, search, inspect ranked candidates."""

    def __init__(
        self,
        embedder_factory: Callable[[], SupportsEmbedding],
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or QSettings()
        self._embedder: SupportsEmbedding | None = None
        self._model_error: str | None = None
        self._query_path: Path | None = None
        self._query_info: tuple[str, int, int] | None = None
        self._result: SearchResult | None = None
        self._search_root: Path | None = None
        self._thumbnails: dict[str, QImage] = {}
        self._worker: SearchWorker | None = None
        self._worker_thread: threading.Thread | None = None
        self._status: tuple[str, dict[str, object]] = ("status.loading_model", {})

        i18n.set_language(str(self._settings.value("language", i18n.DEFAULT_LANGUAGE)))
        self.setAcceptDrops(True)
        self.resize(1200, 860)
        self._build_ui()
        self._build_menu()
        self._restore_settings()
        self._retranslate()
        self._set_busy(False)

        self._loader = ModelLoader(embedder_factory)
        self._loader.loaded.connect(self._on_model_loaded)
        self._loader.failed.connect(self._on_model_failed)
        self._loader.start()

    # ================================================================ UI construction

    def _build_ui(self) -> None:
        # --- reference image
        self.ref_preview = ImagePreview()
        self.ref_info = QLabel()
        self.ref_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ref_browse = QPushButton()
        self.ref_browse.clicked.connect(self._choose_image)
        self.ref_group = QGroupBox()
        ref_layout = QVBoxLayout(self.ref_group)
        ref_layout.addWidget(self.ref_preview, 1)
        ref_row = QHBoxLayout()
        ref_row.addWidget(self.ref_info, 1)
        ref_row.addWidget(self.ref_browse)
        ref_layout.addLayout(ref_row)

        # --- selected candidate
        self.cand_preview = ImagePreview()
        self.cand_info = QLabel()
        self.cand_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cand_open = QPushButton()
        self.cand_open.clicked.connect(self._open_selected)
        self.cand_show = QPushButton()
        self.cand_show.clicked.connect(self._show_selected_in_folder)
        self.cand_group = QGroupBox()
        cand_layout = QVBoxLayout(self.cand_group)
        cand_layout.addWidget(self.cand_preview, 1)
        cand_row = QHBoxLayout()
        cand_row.addWidget(self.cand_info, 1)
        cand_row.addWidget(self.cand_open)
        cand_row.addWidget(self.cand_show)
        cand_layout.addLayout(cand_row)

        previews = QWidget()
        previews_layout = QHBoxLayout(previews)
        previews_layout.setContentsMargins(0, 0, 0, 0)
        previews_layout.addWidget(self.ref_group, 1)
        previews_layout.addWidget(self.cand_group, 1)

        # --- search controls
        self.folder_label = QLabel()
        self.folder_edit = QLineEdit()
        self.folder_edit.setAcceptDrops(False)  # drops are handled by the window
        self.folder_edit.returnPressed.connect(self._start_search)
        self.folder_browse = QPushButton()
        self.folder_browse.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.folder_browse)

        self.top_k_label = QLabel()
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 200)
        self.top_k_spin.setValue(DEFAULT_TOP_K)
        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        for descriptor, _ in _MODES:
            self.mode_combo.addItem("", descriptor.value)
        self.search_button = QPushButton()
        self.search_button.setDefault(True)
        self.search_button.setMinimumWidth(120)
        bold = QFont(self.search_button.font())
        bold.setBold(True)
        self.search_button.setFont(bold)
        self.search_button.clicked.connect(self._start_search)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._cancel_search)
        options_row = QHBoxLayout()
        options_row.addWidget(self.top_k_label)
        options_row.addWidget(self.top_k_spin)
        options_row.addSpacing(16)
        options_row.addWidget(self.mode_label)
        options_row.addWidget(self.mode_combo)
        options_row.addStretch(1)
        options_row.addWidget(self.search_button)
        options_row.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.verdict_label = QLabel()
        self.verdict_label.setWordWrap(True)
        self.verdict_label.setVisible(False)

        # --- results
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setIconSize(QSize(ROW_ICON_SIZE, ROW_ICON_SIZE))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_ICON_SIZE + 8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        header = self.table.horizontalHeader()
        for col in (COL_RANK, COL_SCORE, COL_VOTES, COL_PLAUSIBLE):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PREVIEW, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_PREVIEW, ROW_ICON_SIZE + 12)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected())

        self.skipped_button = QPushButton()
        self.skipped_button.setFlat(True)
        self.skipped_button.setVisible(False)
        self.skipped_button.clicked.connect(self._show_skipped)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addLayout(folder_row)
        bottom_layout.addLayout(options_row)
        bottom_layout.addWidget(self.progress)
        bottom_layout.addWidget(self.verdict_label)
        bottom_layout.addWidget(self.table, 1)
        skipped_row = QHBoxLayout()
        skipped_row.addStretch(1)
        skipped_row.addWidget(self.skipped_button)
        bottom_layout.addLayout(skipped_row)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(previews)
        self.splitter.addWidget(bottom)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.splitter)
        self.setCentralWidget(central)

        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label, 1)

    def _build_menu(self) -> None:
        bar = self.menuBar()
        self.file_menu = bar.addMenu("")
        self.act_open = QAction(self, triggered=self._choose_image, shortcut="Ctrl+O")
        self.act_folder = QAction(self, triggered=self._choose_folder, shortcut="Ctrl+D")
        self.act_exit = QAction(self, triggered=self.close, shortcut="Ctrl+Q")
        self.file_menu.addAction(self.act_open)
        self.file_menu.addAction(self.act_folder)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.act_exit)

        self.settings_menu = bar.addMenu("")
        self.language_menu = self.settings_menu.addMenu("")
        self.language_group = QActionGroup(self)
        self.language_actions: dict[str, QAction] = {}
        for code, name in i18n.LANGUAGES.items():
            action = QAction(name, self, checkable=True)
            action.setData(code)
            action.setChecked(code == i18n.language())
            action.triggered.connect(lambda _checked, c=code: self.set_language(c))
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        self.help_menu = bar.addMenu("")
        self.act_log = QAction(self, triggered=self._open_log_folder)
        self.act_about = QAction(self, triggered=self._show_about)
        self.help_menu.addAction(self.act_log)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.act_about)

    # ================================================================ translation

    def set_language(self, code: str) -> None:
        i18n.set_language(code)
        self._settings.setValue("language", code)
        self.language_actions[code].setChecked(True)
        self._retranslate()

    def _retranslate(self) -> None:
        self.setWindowTitle(f"ObjectTwin {__version__}")
        self.file_menu.setTitle(tr("menu.file"))
        self.act_open.setText(tr("action.open_image"))
        self.act_folder.setText(tr("action.choose_folder"))
        self.act_exit.setText(tr("action.exit"))
        self.settings_menu.setTitle(tr("menu.settings"))
        self.language_menu.setTitle(tr("menu.language"))
        self.help_menu.setTitle(tr("menu.help"))
        self.act_log.setText(tr("action.open_log"))
        self.act_about.setText(tr("action.about"))

        self.ref_group.setTitle(tr("ref.title"))
        self.ref_preview.set_placeholder(tr("ref.none"))
        self.ref_browse.setText(tr("ref.browse"))
        self.cand_group.setTitle(tr("cand.title"))
        self.cand_preview.set_placeholder(tr("cand.none"))
        self.cand_open.setText(tr("cand.open"))
        self.cand_show.setText(tr("cand.show_in_folder"))
        self._update_query_info()

        self.folder_label.setText(tr("folder.label"))
        self.folder_edit.setPlaceholderText(tr("folder.placeholder"))
        self.folder_browse.setText(tr("folder.browse"))
        self.top_k_label.setText(tr("opt.top_k"))
        self.mode_label.setText(tr("opt.mode"))
        self.mode_combo.setToolTip(tr("mode.tooltip"))
        for index, (_, key) in enumerate(_MODES):
            self.mode_combo.setItemText(index, tr(key))
        self.search_button.setText(tr("btn.search"))
        self.cancel_button.setText(tr("btn.cancel"))

        for col, (key, tip) in enumerate(_COLUMNS):
            item = QTableWidgetItem(tr(key))
            if tip:
                item.setToolTip(tr(tip))
            self.table.setHorizontalHeaderItem(col, item)

        self._render_status()
        self._render_result()

    # ================================================================ settings

    def _restore_settings(self) -> None:
        s = self._settings
        geometry = s.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        splitter = s.value("splitter")
        if isinstance(splitter, QByteArray):
            self.splitter.restoreState(splitter)
        self.top_k_spin.setValue(int(s.value("top_k", DEFAULT_TOP_K)))
        index = self.mode_combo.findData(str(s.value("descriptor", DEFAULT_DESCRIPTOR.value)))
        self.mode_combo.setCurrentIndex(max(0, index))
        self.folder_edit.setText(str(s.value("folder", "")))
        query = str(s.value("query", ""))
        if query and Path(query).is_file():
            self.set_query_image(Path(query), show_errors=False)

    def _save_settings(self) -> None:
        s = self._settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter", self.splitter.saveState())
        s.setValue("top_k", self.top_k_spin.value())
        s.setValue("descriptor", self.mode_combo.currentData())
        s.setValue("folder", self.folder_edit.text())
        s.setValue("query", str(self._query_path) if self._query_path else "")
        s.sync()

    # ================================================================ reference image

    def _choose_image(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        start = str(self._query_path.parent) if self._query_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog.open_image"),
            start,
            f"{tr('dialog.image_filter')} ({patterns});;{tr('dialog.all_files')} (*)",
        )
        if path:
            self.set_query_image(Path(path))

    def set_query_image(self, path: Path, show_errors: bool = True) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            image = load_image(path)
            width, height = image.size
            image.thumbnail((QUERY_PREVIEW_SIZE, QUERY_PREVIEW_SIZE))
            self.ref_preview.set_image(pil_to_qimage(image))
        except ImageLoadError as exc:
            log.warning("Cannot load query image: %s", exc)
            if show_errors:
                QMessageBox.warning(self, tr("error.title"), tr("error.load_image", error=exc))
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self._query_path = path
        self._query_info = (path.name, width, height)
        self._update_query_info()
        self._clear_results()
        return True

    def _update_query_info(self) -> None:
        if self._query_info is None:
            self.ref_info.setText("")
            return
        name, w, h = self._query_info
        self.ref_info.setText(tr("ref.info", name=name, w=w, h=h))
        self.ref_info.setToolTip(str(self._query_path))

    # ================================================================ folder

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, tr("dialog.choose_folder"), self.folder_edit.text()
        )
        if folder:
            self.folder_edit.setText(str(Path(folder)))

    # ================================================================ drag & drop

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dropped_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._dropped_path(event)
        if path is None:
            return
        event.acceptProposedAction()
        if path.is_dir():
            self.folder_edit.setText(str(path))
        else:
            self.set_query_image(path)

    @staticmethod
    def _dropped_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        return path if path.is_dir() or is_supported(path) else None

    # ================================================================ model

    def _on_model_loaded(self, embedder: SupportsEmbedding) -> None:
        self._embedder = embedder
        self._set_status("status.model_ready", device=self._device_name())
        self._set_busy(False)

    def _on_model_failed(self, error: str) -> None:
        self._model_error = error
        self._set_status("status.model_failed", error=error)
        self._set_busy(False)

    def _device_name(self) -> str:
        return str(getattr(self._embedder, "device_name", "CPU"))

    # ================================================================ search

    def _start_search(self) -> None:
        if self._worker is not None:
            return
        if self._query_path is None:
            QMessageBox.information(self, "ObjectTwin", tr("error.no_image"))
            return
        folder = Path(self.folder_edit.text().strip().strip('"'))
        if not self.folder_edit.text().strip() or not folder.is_dir():
            QMessageBox.information(self, "ObjectTwin", tr("error.no_folder"))
            return
        if self._embedder is None:
            message = (
                tr("status.model_failed", error=self._model_error)
                if self._model_error
                else tr("error.model_not_ready")
            )
            QMessageBox.information(self, "ObjectTwin", message)
            return

        if hasattr(self._embedder, "descriptor"):
            self._embedder.descriptor = self.mode_combo.currentData()
        self._clear_results()
        self._search_root = folder
        self.progress.setRange(0, 0)  # busy indicator until the file count is known
        self._set_status("status.scanning")

        self._worker = SearchWorker(
            self._embedder, self._query_path, folder, self.top_k_spin.value()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.cancelled.connect(self._on_search_cancelled)
        self._worker.failed.connect(self._on_search_failed)
        self._set_busy(True)
        self._worker_thread = self._worker.start()

    def _cancel_search(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self._set_status("status.cancelling")

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        if self.cancel_button.isEnabled():
            self._set_status("status.searching", done=done, total=total)

    def _on_search_finished(self, result: SearchResult, thumbnails: dict[str, QImage]) -> None:
        self._search_done()
        self._result = result
        self._thumbnails = thumbnails
        self._set_status("status.done", scanned=result.scanned, seconds=result.elapsed_s)
        self._render_result()
        if self.table.rowCount():
            self.table.selectRow(0)

    def _on_search_cancelled(self) -> None:
        self._search_done()
        self._set_status("status.cancelled")

    def _on_search_failed(self, error: str) -> None:
        self._search_done()
        self._set_status("status.model_ready", device=self._device_name())
        QMessageBox.critical(self, tr("error.title"), tr("error.search", error=error))

    def _search_done(self) -> None:
        self._worker = None
        self._worker_thread = None
        self._set_busy(False)

    def is_searching(self) -> bool:
        return self._worker is not None

    # ================================================================ results

    def _clear_results(self) -> None:
        self._result = None
        self._thumbnails = {}
        self._render_result()

    def _render_result(self) -> None:
        """(Re)build the verdict banner and the table from ``self._result``."""
        selected = self.table.currentRow()
        self.table.setRowCount(0)
        result = self._result
        if result is None:
            self.verdict_label.setVisible(False)
            self.skipped_button.setVisible(False)
            self._show_candidate(None)
            return

        self._render_verdict(result)
        self.skipped_button.setText(tr("skipped.button", n=len(result.skipped)))
        self.skipped_button.setVisible(bool(result.skipped))

        self.table.setRowCount(len(result.matches))
        for row, match in enumerate(result.matches):
            thumb = self._thumbnails.get(str(match.path))
            preview = QTableWidgetItem()
            if thumb is not None:
                preview.setIcon(QIcon(QPixmap.fromImage(thumb)))
            items = {
                COL_RANK: QTableWidgetItem(str(row + 1)),
                COL_PREVIEW: preview,
                COL_SCORE: QTableWidgetItem(f"{_fmt(match.score)} ± {_fmt(match.score_std)}"),
                COL_VOTES: QTableWidgetItem(f"{match.votes:.0%}".replace("%", " %")),
                COL_PLAUSIBLE: QTableWidgetItem("✓" if match.plausible else ""),
                COL_PATH: QTableWidgetItem(self._display_path(match.path)),
            }
            items[COL_PATH].setToolTip(str(match.path))
            for col, item in items.items():
                align = Qt.AlignmentFlag.AlignVCenter | (
                    Qt.AlignmentFlag.AlignLeft if col == COL_PATH else Qt.AlignmentFlag.AlignCenter
                )
                item.setTextAlignment(align)
                if match.plausible:
                    item.setBackground(_PLAUSIBLE_TINT)
                self.table.setItem(row, col, item)
        if 0 <= selected < self.table.rowCount():
            self.table.selectRow(selected)

    def _display_path(self, path: Path) -> str:
        """Path relative to the searched folder (full path is in the tooltip)."""
        if self._search_root is not None:
            try:
                return str(path.relative_to(self._search_root))
            except ValueError:
                pass
        return str(path)

    def _render_verdict(self, result: SearchResult) -> None:
        a = result.assessment
        if a.verdict == Verdict.CONFIDENT and result.matches:
            text = tr("verdict.confident", name=result.matches[0].path.name)
        elif a.verdict == Verdict.AMBIGUOUS:
            text = tr("verdict.ambiguous", n=a.n_plausible)
        else:
            text = tr(f"verdict.{a.verdict.value}")
        background, color, accent = _VERDICT_STYLE[a.verdict]
        self.verdict_label.setStyleSheet(
            f"QLabel {{ background: {background}; color: {color}; padding: 8px 10px;"
            f" border-left: 5px solid {accent}; border-radius: 3px; font-weight: 600; }}"
        )
        self.verdict_label.setText(text)
        self.verdict_label.setVisible(True)

    def _selected_path(self) -> Path | None:
        row = self.table.currentRow()
        if self._result is None or not 0 <= row < len(self._result.matches):
            return None
        return self._result.matches[row].path

    def _on_selection_changed(self) -> None:
        self._show_candidate(self._selected_path())

    def _show_candidate(self, path: Path | None) -> None:
        has = path is not None
        self.cand_open.setEnabled(has)
        self.cand_show.setEnabled(has)
        if path is None:
            self.cand_preview.set_image(None)
            self.cand_info.setText("")
            return
        thumb = self._thumbnails.get(str(path))
        if thumb is None:
            try:
                thumb = load_thumbnail(path)
            except ImageLoadError:
                thumb = None
        self.cand_preview.set_image(thumb)
        self.cand_info.setText(path.name)
        self.cand_info.setToolTip(str(path))

    def _open_selected(self) -> None:
        path = self._selected_path()
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_selected_in_folder(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _show_skipped(self) -> None:
        if self._result is None:
            return
        lines = [f"{p}: {err}" for p, err in self._result.skipped[:200]]
        box = QMessageBox(self)
        box.setWindowTitle(tr("skipped.title"))
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(tr("skipped.text"))
        box.setDetailedText("\n".join(lines))
        box.exec()

    # ================================================================ misc

    def _set_status(self, key: str, **kwargs: object) -> None:
        self._status = (key, kwargs)
        self._render_status()

    def _render_status(self) -> None:
        key, kwargs = self._status
        if isinstance(kwargs.get("seconds"), float):  # format at render time (locale)
            kwargs = {**kwargs, "seconds": _fmt(kwargs["seconds"], 1)}
        text = tr(key, **kwargs)
        if key == "status.done" and self._result and self._result.skipped:
            text += f" – {tr('skipped.button', n=len(self._result.skipped)).rstrip('…')}"
        self.status_label.setText(text)

    def _set_busy(self, busy: bool) -> None:
        ready = self._embedder is not None
        self.search_button.setEnabled(not busy and ready)
        self.cancel_button.setEnabled(busy)
        self.cancel_button.setVisible(busy)
        self.progress.setVisible(busy)
        for widget in (
            self.ref_browse,
            self.folder_edit,
            self.folder_browse,
            self.top_k_spin,
            self.mode_combo,
        ):
            widget.setEnabled(not busy)
        self.act_open.setEnabled(not busy)
        self.act_folder.setEnabled(not busy)
        self.setAcceptDrops(not busy)

    def _open_log_folder(self) -> None:
        folder = log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _show_about(self) -> None:
        if self._embedder is not None:
            model = str(getattr(self._embedder, "model_name", "DINOv2"))
            device = self._device_name()
        else:
            model = device = tr("about.not_loaded")
        QMessageBox.about(
            self,
            tr("about.title"),
            tr("about.text", version=__version__, model=model, device=device),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._worker.cancel()
            if self._worker_thread is not None:
                self._worker_thread.join(timeout=10)
        self._save_settings()
        super().closeEvent(event)
