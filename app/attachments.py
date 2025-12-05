# -*- coding: utf-8 -*-
"""Dosya ekleri için yardımcı fonksiyonlar."""

from __future__ import annotations

import logging
import mimetypes
import os
import shutil
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QIcon

try:  # pragma: no cover - runtime import guard
    from app.db import (
        get_connection,
        get_case_files_root,
        get_case_folder_path,
        ensure_case_folder,
        sanitize_folder_name,
    )
except ModuleNotFoundError:  # pragma: no cover
    from db import (
        get_connection,
        get_case_files_root,
        get_case_folder_path,
        ensure_case_folder,
        sanitize_folder_name,
    )

try:  # pragma: no cover - runtime import guard
    from app.utils import get_attachments_dir
except ModuleNotFoundError:  # pragma: no cover
    from utils import get_attachments_dir

logger = logging.getLogger(__name__)

ICON_CACHE: Dict[str, QIcon] = {}


@lru_cache(maxsize=4096)
def file_exists(path: str) -> bool:
    return os.path.exists(path)


@lru_cache(maxsize=2048)
def file_info(path: str) -> tuple[Optional[int], Optional[float]]:
    try:
        stat_info = os.stat(path)
    except FileNotFoundError:
        return None, None
    return int(stat_info.st_size), float(stat_info.st_mtime)


@lru_cache(maxsize=512)
def guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def icon_for_ext(ext: str) -> QIcon:
    key = (ext or "").lower()
    icon = ICON_CACHE.get(key)
    if icon is not None:
        return icon
    candidate = QIcon()
    if key:
        candidate = QIcon.fromTheme(key.strip("."))
    if candidate.isNull():
        candidate = QIcon(":/icons/file_generic.svg")
    ICON_CACHE[key] = candidate
    return candidate


class AttachmentError(Exception):
    """Ek işlemlerinde oluşan beklenmedik hatalar."""


def _attachments_root() -> Path:
    """Yeni klasör yapısı: Documents/TakibiEsasi Dosyaları/"""
    root = Path(get_case_files_root())
    root.mkdir(parents=True, exist_ok=True)
    return root


def _legacy_attachments_root() -> Path:
    """Eski klasör yapısı (geriye dönük uyumluluk için)."""
    root = get_attachments_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _case_directory(dosya_id: int) -> Path:
    """
    Dava için klasör yolunu döndürür.

    Yeni format: [BN001] [Esas No] [Müvekkil]
    """
    folder_path = ensure_case_folder(dosya_id)
    if folder_path:
        return Path(folder_path)

    # Fallback: eski sisteme dön
    root = _legacy_attachments_root()
    case_dir = root / str(dosya_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def _normalize_name(name: str) -> str:
    """Dosya adını güvenli hale getirir."""
    # Uzantıyı ayır
    base, ext = os.path.splitext(name)

    # Türkçe karakterleri ve geçersiz karakterleri temizle
    sanitized = sanitize_folder_name(base)

    # Boşsa varsayılan isim ver
    if not sanitized:
        sanitized = "ek"

    return sanitized + ext


def _unique_destination(case_dir: Path, original_name: str) -> Path:
    base_name = _normalize_name(original_name)
    candidate = case_dir / base_name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        candidate = case_dir / new_name
        if not candidate.exists():
            return candidate
        counter += 1


def _copy_with_metadata(source: Path, destination: Path) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    size = destination.stat().st_size
    mime = guess_mime(str(destination))
    _invalidate_fs_caches()
    return size, mime


def add_attachments(dosya_id: int, paths: Iterable[str]) -> List[int]:
    """Girilen kaynak dosyaları kopyalayıp veritabanına ekler."""

    inserted_ids: List[int] = []
    case_dir = _case_directory(dosya_id)
    conn = get_connection()
    try:
        cur = conn.cursor()
        for raw_path in paths:
            if not raw_path:
                continue
            source = Path(raw_path)
            if not file_exists(str(source)):
                logger.warning("Attachment source missing: %s", raw_path)
                raise AttachmentError(f"Kaynak dosya bulunamadı: {raw_path}")
            destination = _unique_destination(case_dir, source.name)
            try:
                size, mime = _copy_with_metadata(source, destination)
            except Exception as exc:  # pragma: no cover - dosya kopyalama güvenliği
                logger.exception("Attachment copy failed for %s", raw_path)
                raise AttachmentError(str(exc)) from exc

            # Sadece dosya adını kaydet (klasör adı değişebilir)
            stored_filename = destination.name

            cur.execute(
                """
                INSERT INTO attachments (dosya_id, original_name, stored_path, mime, size_bytes, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dosya_id,
                    source.name,
                    stored_filename,
                    mime,
                    size,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            inserted_ids.append(int(cur.lastrowid))
        conn.commit()
    finally:
        conn.close()
    return inserted_ids


def list_attachments(dosya_id: int) -> List[dict]:
    """Verilen dosyaya ait ek kayıtlarını döndürür."""

    # Yeni ve eski klasör kökleri
    new_root = _attachments_root()
    legacy_root = _legacy_attachments_root()

    # Dava klasörü (yeni yapı)
    case_dir = _case_directory(dosya_id)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, original_name, stored_path, mime, size_bytes, added_at
            FROM attachments
            WHERE dosya_id = ?
            ORDER BY added_at DESC, id DESC
            """,
            (dosya_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    results: List[dict] = []
    for row in rows:
        stored = row[2] or ""
        exists = False
        absolute = None

        # 1. Önce yeni konumu dene (dava klasörü içinde sadece dosya adı)
        if stored:
            # stored_path sadece dosya adı olabilir veya eski format olabilir
            filename = os.path.basename(stored)
            new_path = case_dir / filename
            if file_exists(str(new_path)):
                absolute = new_path
                exists = True

        # 2. Yeni root altında tam yol olarak dene
        if not exists and stored:
            full_new = new_root / stored
            if file_exists(str(full_new)):
                absolute = full_new
                exists = True

        # 3. Eski konumu dene (geriye dönük uyumluluk)
        if not exists and stored:
            legacy_path = legacy_root / stored
            if file_exists(str(legacy_path)):
                absolute = legacy_path
                exists = True

        # Hiçbiri bulunamadıysa yeni yolu varsayılan olarak kullan
        if absolute is None:
            absolute = case_dir / os.path.basename(stored) if stored else case_dir / "unknown"

        size_bytes = int(row[4] or 0)
        if exists:
            cached_size, _ = file_info(str(absolute))
            if cached_size is not None:
                size_bytes = int(cached_size)

        mime_value = row[3] or ""
        if not mime_value and stored:
            mime_value = guess_mime(str(absolute))

        results.append(
            {
                "id": int(row[0]),
                "original_name": row[1] or os.path.basename(stored),
                "stored_path": stored,
                "absolute_path": str(absolute),
                "exists": exists,
                "mime": mime_value,
                "size_bytes": size_bytes,
                "added_at": row[5],
            }
        )
    return results


def delete_attachment(attachment_id: int, *, remove_file: bool = False) -> None:
    """Ek kaydını siler; istenirse fiziksel dosyayı da kaldırır."""

    new_root = _attachments_root()
    legacy_root = _legacy_attachments_root()
    conn = get_connection()
    stored_path: Optional[str] = None
    dosya_id: Optional[int] = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dosya_id, stored_path FROM attachments WHERE id = ?",
            (attachment_id,)
        )
        row = cur.fetchone()
        if row:
            dosya_id = row[0]
            stored_path = row[1]
        cur.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()
    finally:
        conn.close()

    if remove_file and stored_path:
        file_deleted = False

        # 1. Dava klasöründe ara (yeni yapı)
        if dosya_id:
            case_dir = _case_directory(dosya_id)
            filename = os.path.basename(stored_path)
            case_file = case_dir / filename
            if file_exists(str(case_file)):
                try:
                    case_file.unlink()
                    file_deleted = True
                    _invalidate_fs_caches()
                except Exception as exc:
                    logger.exception("Attachment file removal failed for %s", case_file)
                    raise AttachmentError(str(exc)) from exc

        # 2. Yeni root altında ara
        if not file_deleted:
            new_path = new_root / stored_path
            if file_exists(str(new_path)):
                try:
                    new_path.unlink()
                    file_deleted = True
                    _invalidate_fs_caches()
                except Exception as exc:
                    logger.exception("Attachment file removal failed for %s", new_path)
                    raise AttachmentError(str(exc)) from exc

        # 3. Eski root altında ara
        if not file_deleted:
            legacy_path = legacy_root / stored_path
            if file_exists(str(legacy_path)):
                try:
                    legacy_path.unlink()
                    _invalidate_fs_caches()
                except Exception as exc:
                    logger.exception("Attachment file removal failed for %s", legacy_path)
                    raise AttachmentError(str(exc)) from exc


def update_attachment_source(attachment_id: int, new_source_path: str) -> None:
    """Var olan ek için yeni kaynaktan dosya kopyalar ve meta veriyi günceller."""

    source = Path(new_source_path)
    if not file_exists(str(source)):
        raise AttachmentError("Seçilen dosya bulunamadı.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dosya_id FROM attachments WHERE id = ?",
            (attachment_id,),
        )
        row = cur.fetchone()
        if not row:
            raise AttachmentError("Güncellenecek ek kaydı bulunamadı.")
        dosya_id = int(row[0])
        destination_dir = _case_directory(dosya_id)
        destination = _unique_destination(destination_dir, source.name)
        size, mime = _copy_with_metadata(source, destination)

        # Sadece dosya adını kaydet
        stored_filename = destination.name

        cur.execute(
            """
            UPDATE attachments
            SET original_name = ?, stored_path = ?, mime = ?, size_bytes = ?, added_at = ?
            WHERE id = ?
            """,
            (
                source.name,
                stored_filename,
                mime,
                size,
                datetime.utcnow().isoformat(timespec="seconds"),
                attachment_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    _invalidate_fs_caches()


def export_attachment(attachment_id: int, target_directory: str) -> Path:
    """Ek dosyasını hedef klasöre kopyalar ve yeni yolu döndürür."""

    new_root = _attachments_root()
    legacy_root = _legacy_attachments_root()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT dosya_id, original_name, stored_path FROM attachments WHERE id = ?",
            (attachment_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise AttachmentError("Ek kaydı bulunamadı.")

    dosya_id, original_name, stored_path = row
    source = None

    # 1. Dava klasöründe ara (yeni yapı)
    if dosya_id and stored_path:
        case_dir = _case_directory(dosya_id)
        filename = os.path.basename(stored_path)
        case_file = case_dir / filename
        if case_file.exists():
            source = case_file

    # 2. Yeni root altında ara
    if source is None and stored_path:
        new_path = new_root / stored_path
        if new_path.exists():
            source = new_path

    # 3. Eski root altında ara
    if source is None and stored_path:
        legacy_path = legacy_root / stored_path
        if legacy_path.exists():
            source = legacy_path

    if source is None or not source.exists():
        raise AttachmentError("Kaydedilmiş dosya bulunamadı.")

    destination_dir = Path(target_directory)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (original_name or source.name)
    destination = _unique_destination(destination_dir, destination.name)
    shutil.copy2(source, destination)
    return destination


def open_attachment(path: str) -> bool:
    """Varsayılan uygulama ile dosyayı açar."""

    file_path = Path(path)
    if not file_path.exists():
        raise AttachmentError("Dosya bulunamadı.")
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))
def _invalidate_fs_caches() -> None:
    file_exists.cache_clear()
    file_info.cache_clear()
    guess_mime.cache_clear()


