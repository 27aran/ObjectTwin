"""Reusable widgets."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy


class ImagePreview(QLabel):
    """Shows an image scaled to fit (keeping the aspect ratio) or a placeholder text."""

    def __init__(self) -> None:
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._placeholder = ""
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(QSize(220, 180))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWordWrap(True)
        self.setStyleSheet("QLabel { background: palette(base); color: palette(mid); }")

    def set_image(self, image: QImage | None) -> None:
        self._pixmap = QPixmap.fromImage(image) if image is not None else None
        self._refresh()

    def set_placeholder(self, text: str) -> None:
        """Text shown while no image is set."""
        self._placeholder = text
        self._refresh()

    def has_image(self) -> bool:
        return self._pixmap is not None

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._pixmap is None:
            self.setPixmap(QPixmap())
            self.setText(self._placeholder)
            return
        self.setPixmap(
            self._pixmap.scaled(
                self.contentsRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
