from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

try:  # pragma: no cover - runtime import guard
    from app.models import get_attachments
except ModuleNotFoundError:  # pragma: no cover
    from models import get_attachments

try:  # pragma: no cover - runtime import guard
    from app.utils import get_attachments_dir
except ModuleNotFoundError:  # pragma: no cover
    from utils import get_attachments_dir

try:  # pragma: no cover - runtime import guard
    from app.attachments import file_exists, file_info, guess_mime
except ModuleNotFoundError:  # pragma: no cover
    from attachments import file_exists, file_info, guess_mime

try:  # pragma: no cover - runtime import guard
    from app.db import get_pending_changes
except ModuleNotFoundError:  # pragma: no cover
    from db import get_pending_changes


def _format_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 ** 2:
        return f"{value / 1024:.1f} KB"
    if value < 1024 ** 3:
        return f"{value / (1024 ** 2):.1f} MB"
    return f"{value / (1024 ** 3):.1f} GB"


class AttachmentScanWorker(QObject):
    batchReady = pyqtSignal(list)
    errorOccurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, dosya_id: int, *, chunk_size: int = 25) -> None:
        super().__init__()
        self._dosya_id = dosya_id
        self._chunk_size = max(1, int(chunk_size))
        self._cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        try:
            records = get_attachments(self._dosya_id)
        except Exception as exc:  # pragma: no cover - IO güvenliği
            self.errorOccurred.emit(str(exc))
            self.finished.emit()
            return

        batch: List[Dict[str, Any]] = []
        for record in records:
            if self._cancelled:
                break
            processed = self._process_record(record)
            batch.append(processed)
            if len(batch) >= self._chunk_size:
                self.batchReady.emit(batch)
                batch = []
        if batch and not self._cancelled:
            self.batchReady.emit(batch)
        self.finished.emit()

    @pyqtSlot()
    def cancel(self) -> None:
        self._cancelled = True

    def _process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        stored_path = record.get("stored_path") or ""
        absolute_raw = record.get("absolute_path") or ""
        path: Optional[Path] = None
        if absolute_raw:
            path = Path(absolute_raw)
        elif stored_path:
            path = get_attachments_dir() / stored_path

        exists = False
        size_bytes = int(record.get("size_bytes") or 0)
        mime = record.get("mime") or ""
        if path is not None:
            absolute_str = str(path)
            exists = file_exists(absolute_str)
            if exists:
                size_info, _ = file_info(absolute_str)
                if size_info is not None:
                    size_bytes = int(size_info)
                if not mime:
                    mime = guess_mime(absolute_str)
        name = record.get("original_name") or Path(stored_path).name or "(adsız)"
        added_value = record.get("added_at") or ""
        added_display = ""
        if added_value:
            try:
                added_display = datetime.fromisoformat(str(added_value)).strftime(
                    "%d.%m.%Y %H:%M"
                )
            except ValueError:
                added_display = str(added_value)

        return {
            "id": record.get("id"),
            "name": name,
            "mime": mime,
            "size_bytes": size_bytes,
            "size_display": _format_size(int(size_bytes)),
            "added_display": added_display,
            "exists": exists,
            "absolute_path": str(path) if path is not None else absolute_raw,
            "stored_path": stored_path,
        }


class ChangeDetectorWorker(QObject):
    """Veritabanı değişikliklerini arka planda tespit eden worker.

    SQLite trigger'ları tarafından doldurulan change_log tablosunu
    kontrol eder. Timestamp karşılaştırması yapmaz, sadece log'a bakar.
    """

    changesDetected = pyqtSignal(dict)
    errorOccurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        """Change log'u kontrol et ve değişiklikleri bildir."""
        try:
            if self._cancelled:
                self.finished.emit()
                return

            # Tek bir fonksiyon çağrısı ile tüm değişiklikleri al ve log'u temizle
            changes = get_pending_changes()

            if changes["dosyalar"] or changes["gorevler"] or changes["finans"]:
                self.changesDetected.emit(changes)

        except Exception as exc:  # pragma: no cover
            self.errorOccurred.emit(str(exc))

        self.finished.emit()

    @pyqtSlot()
    def cancel(self) -> None:
        """Worker'ı iptal et."""
        self._cancelled = True
