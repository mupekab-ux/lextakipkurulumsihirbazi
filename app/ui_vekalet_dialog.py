# -*- coding: utf-8 -*-
"""Vekaletnameler yönetim dialogu."""

from __future__ import annotations

import os
import shutil
import time
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QFileDialog,
)

try:  # pragma: no cover - runtime import guard
    from app.utils import get_vekalet_dir, human_size
except ModuleNotFoundError:  # pragma: no cover
    from utils import get_vekalet_dir, human_size


class VekaletDialog(QDialog):
    """Vekaletnameler klasörünü yöneten basit dialog."""

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vekaletnameler")
        self.resize(800, 500)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Ad", "Boyut", "Son Değişiklik"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setMinimumHeight(200)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Ekle…")
        self.btn_open = QPushButton("Aç")
        self.btn_open_folder = QPushButton("Klasörü Aç")
        self.btn_delete = QPushButton("Sil")
        self.btn_refresh = QPushButton("Yenile")
        self.btn_close = QPushButton("Kapat")
        for button in (
            self.btn_add,
            self.btn_open,
            self.btn_open_folder,
            self.btn_delete,
            self.btn_refresh,
            self.btn_close,
        ):
            buttons.addWidget(button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.btn_add.clicked.connect(self.add_file)
        self.btn_open.clicked.connect(self.open_file)
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.btn_delete.clicked.connect(self.delete_file)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_close.clicked.connect(self.accept)

        self.refresh()

    def dir_path(self) -> str:
        return get_vekalet_dir()

    def refresh(self) -> None:
        directory = self.dir_path()
        os.makedirs(directory, exist_ok=True)
        entries: list[tuple[str, int, float]] = []
        try:
            names = sorted(os.listdir(directory), key=str.lower)
        except OSError:
            names = []
        for name in names:
            full_path = os.path.join(directory, name)
            if not os.path.isfile(full_path):
                continue
            try:
                stat_info = os.stat(full_path)
            except OSError:
                continue
            entries.append((name, stat_info.st_size, stat_info.st_mtime))

        self.table.setRowCount(0)
        for filename, size, mtime in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(filename))
            self.table.setItem(row, 1, QTableWidgetItem(human_size(size)))
            formatted = time.strftime("%d.%m.%Y %H:%M", time.localtime(mtime))
            self.table.setItem(row, 2, QTableWidgetItem(formatted))
        self.table.resizeColumnsToContents()

    def current_selection(self) -> Optional[str]:
        model = self.table.selectionModel()
        if model is None:
            return None
        indexes = model.selectedRows()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return None
        return os.path.join(self.dir_path(), item.text())

    def add_file(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Belge Seç", "", "Tüm Dosyalar (*.*)")
        if not source:
            return
        directory = self.dir_path()
        base_name = os.path.basename(source)
        destination = os.path.join(directory, base_name)
        if os.path.exists(destination):
            overwrite = QMessageBox.question(
                self,
                "Dosya mevcut",
                f"“{base_name}” zaten var.\nÜzerine yazılsın mı?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if overwrite == QMessageBox.StandardButton.No:
                name, ext = os.path.splitext(base_name)
                counter = 2
                new_destination = destination
                while os.path.exists(new_destination):
                    new_destination = os.path.join(directory, f"{name} ({counter}){ext}")
                    counter += 1
                destination = new_destination
        try:
            shutil.copy2(source, destination)
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Dosya kopyalanamadı:\n{exc}")
            return
        self.refresh()

    def open_file(self) -> None:
        path = self.current_selection()
        if not path:
            QMessageBox.information(self, "Bilgi", "Lütfen bir dosya seçin.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.dir_path()))

    def delete_file(self) -> None:
        path = self.current_selection()
        if not path:
            QMessageBox.information(self, "Bilgi", "Lütfen silmek için bir dosya seçin.")
            return
        reply = QMessageBox.question(
            self,
            "Silme Onayı",
            f"Seçili dosya silinsin mi?\n\n{os.path.basename(path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(path)
        except Exception as exc:  # pragma: no cover - GUI safety
            QMessageBox.critical(self, "Hata", f"Silinemedi:\n{exc}")
            return
        self.refresh()

