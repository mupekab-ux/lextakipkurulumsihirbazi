# -*- coding: utf-8 -*-
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

try:  # pragma: no cover - runtime import guard
    from app.models import (
        get_attachments,
        add_attachment as add_attachment_record,
        delete_attachment,
    )
except ModuleNotFoundError:  # pragma: no cover
    from models import (
        get_attachments,
        add_attachment as add_attachment_record,
        delete_attachment,
    )


class AttachmentsDialog(QDialog):
    def __init__(self, parent=None, dosya_id: int | None = None):
        super().__init__(parent)
        self.dosya_id = dosya_id
        self.setWindowTitle("TakibiEsasi - Ekleri Yönet")

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Dosya Yolu", "Eklenme Tarihi"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Ekle")
        self.open_button = QPushButton("Dosyayı Göster")
        self.remove_button = QPushButton("Kaldır")
        self.close_button = QPushButton("Kapat")
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self.add_attachment)
        self.open_button.clicked.connect(self.open_attachment)
        self.remove_button.clicked.connect(self.remove_attachment)
        self.close_button.clicked.connect(self.close)

        if self.dosya_id is not None:
            self.refresh()
        self._restore_dialog_size()

    def _restore_dialog_size(self) -> None:
        """Kaydedilmiş pencere boyutunu yükle."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        size = settings.value("AttachmentsDialog/size")
        if size:
            self.resize(size)

    def closeEvent(self, event) -> None:
        """Pencere boyutunu kaydet ve kapat."""
        settings = QSettings("TakibiEsasi", "TakibiEsasi")
        settings.setValue("AttachmentsDialog/size", self.size())
        super().closeEvent(event)

    def refresh(self) -> None:
        """Veritabanından ekleri yükler."""
        attachments = get_attachments(self.dosya_id)
        self.table.setRowCount(0)
        for att in attachments:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_path = QTableWidgetItem(att["path"])
            item_path.setData(Qt.ItemDataRole.UserRole, att["id"])
            item_date = QTableWidgetItem(att["created_at"])
            self.table.setItem(row, 0, item_path)
            self.table.setItem(row, 1, item_date)

    def add_attachment(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Dosya Seç")
        if path and self.dosya_id is not None:
            try:
                add_attachment_record(self.dosya_id, path)
            except FileNotFoundError:
                QMessageBox.warning(
                    self,
                    "Dosya bulunamadı",
                    "Seçtiğiniz dosya bulunamadı. Lütfen dosya yolunu kontrol edin.",
                )
            except Exception as exc:  # pragma: no cover - kullanıcıya hata gösterimi
                QMessageBox.critical(
                    self,
                    "Hata",
                    f"Ek eklenirken bir hata oluştu:\n{exc}",
                )
            else:
                self.refresh()

    def open_attachment(self) -> None:
        item = self.table.currentItem()
        if not item:
            return
        row = item.row()
        path_item = self.table.item(row, 0)
        if path_item:
            path = path_item.text()
            file_path = Path(path)
            if not file_path.exists():
                QMessageBox.warning(
                    self,
                    "Dosya bulunamadı",
                    "Dosya bulunamadı. attachments klasörünü kontrol edin.",
                )
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))

    def remove_attachment(self) -> None:
        item = self.table.currentItem()
        if not item:
            return
        row = item.row()
        path_item = self.table.item(row, 0)
        if not path_item:
            return
        attachment_id = path_item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "Onay",
            "Seçili ek kaldırılacak. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_attachment(attachment_id)
            self.refresh()

