# -*- coding: utf-8 -*-
"""A lightweight flow layout helper for wrapping widgets."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtWidgets import QLayout, QSizePolicy, QWidget, QLayoutItem


class FlowLayout(QLayout):
    """A simple flow layout inspired by the Qt documentation example."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = -1) -> None:
        super().__init__(parent)
        self._item_list: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def __del__(self) -> None:
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item) -> None:  # type: ignore[override]
        self._item_list.append(item)

    def count(self) -> int:  # type: ignore[override]
        return len(self._item_list)

    def itemAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):  # type: ignore[override]
        from PyQt6.QtCore import Qt

        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect: QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # type: ignore[override]
        size = QSize()
        left, top, right, bottom = self.getContentsMargins()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        from PyQt6.QtCore import Qt

        x = rect.x()
        y = rect.y()
        line_height = 0

        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        max_width = effective_rect.width()

        for item in self._item_list:
            widget = item.widget()
            if widget is not None and not widget.isVisible():
                continue
            space_x = self.spacing() + widget.style().layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Horizontal,
            )
            space_y = self.spacing() + widget.style().layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Vertical,
            )
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + bottom
