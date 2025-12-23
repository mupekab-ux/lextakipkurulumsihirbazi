# -*- coding: utf-8 -*-
"""
Conflict Handler

Senkronizasyon çakışmalarını yönetir.
Varsayılan strateji: Last-Write-Wins
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from .models import SyncConflict

logger = logging.getLogger(__name__)


class ConflictHandler:
    """
    Çakışma yöneticisi.

    Stratejiler:
    - last_write_wins: En son güncellenen kazanır (varsayılan)
    - server_wins: Sunucu her zaman kazanır
    - client_wins: İstemci her zaman kazanır
    - manual: Kullanıcıya sor
    """

    def __init__(self, db_path: str, strategy: str = 'last_write_wins'):
        """
        Args:
            db_path: SQLite veritabanı yolu
            strategy: Çakışma çözüm stratejisi
        """
        self.db_path = db_path
        self.strategy = strategy

        # UI callback'i (manual mod için)
        self.on_conflict_ui: Optional[Callable[[SyncConflict], str]] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def resolve(self, conflict: SyncConflict) -> Dict[str, Any]:
        """
        Çakışmayı çöz.

        Args:
            conflict: SyncConflict instance

        Returns:
            Kazanan veri
        """
        if self.strategy == 'last_write_wins':
            return self._resolve_last_write_wins(conflict)
        elif self.strategy == 'server_wins':
            return self._resolve_server_wins(conflict)
        elif self.strategy == 'client_wins':
            return self._resolve_client_wins(conflict)
        elif self.strategy == 'manual':
            return self._resolve_manual(conflict)
        else:
            # Bilinmeyen strateji, last_write_wins kullan
            return self._resolve_last_write_wins(conflict)

    def _resolve_last_write_wins(self, conflict: SyncConflict) -> Dict[str, Any]:
        """
        Last-Write-Wins stratejisi.

        Daha yeni updated_at değerine sahip olan kazanır.
        """
        local_time = conflict.local_updated_at
        remote_time = conflict.remote_updated_at

        if local_time and remote_time:
            if local_time > remote_time:
                conflict.resolution = 'local'
                conflict.winning_data = conflict.local_data
                logger.info(f"Çakışma çözüldü (local kazandı): {conflict.record_uuid}")
            else:
                conflict.resolution = 'remote'
                conflict.winning_data = conflict.remote_data
                logger.info(f"Çakışma çözüldü (remote kazandı): {conflict.record_uuid}")
        else:
            # Timestamp yoksa remote kazanır (sunucu otoritesi)
            conflict.resolution = 'remote'
            conflict.winning_data = conflict.remote_data
            logger.info(f"Çakışma çözüldü (timestamp yok, remote): {conflict.record_uuid}")

        self._log_conflict(conflict)
        return conflict.winning_data

    def _resolve_server_wins(self, conflict: SyncConflict) -> Dict[str, Any]:
        """Sunucu her zaman kazanır"""
        conflict.resolution = 'remote'
        conflict.winning_data = conflict.remote_data
        self._log_conflict(conflict)
        return conflict.winning_data

    def _resolve_client_wins(self, conflict: SyncConflict) -> Dict[str, Any]:
        """İstemci her zaman kazanır"""
        conflict.resolution = 'local'
        conflict.winning_data = conflict.local_data
        self._log_conflict(conflict)
        return conflict.winning_data

    def _resolve_manual(self, conflict: SyncConflict) -> Dict[str, Any]:
        """
        Kullanıcıya sor.

        UI callback tanımlıysa kullanılır, yoksa last_write_wins.
        """
        if self.on_conflict_ui:
            # UI'dan kullanıcı seçimini al
            choice = self.on_conflict_ui(conflict)

            if choice == 'local':
                conflict.resolution = 'local'
                conflict.winning_data = conflict.local_data
            elif choice == 'remote':
                conflict.resolution = 'remote'
                conflict.winning_data = conflict.remote_data
            else:
                # Merge veya bilinmeyen, last_write_wins
                return self._resolve_last_write_wins(conflict)

            self._log_conflict(conflict)
            return conflict.winning_data
        else:
            # UI yok, otomatik çöz
            return self._resolve_last_write_wins(conflict)

    def _log_conflict(self, conflict: SyncConflict):
        """Çakışmayı loga kaydet"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO sync_conflicts
                (record_uuid, table_name, local_data, remote_data,
                 winning_data, resolution, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conflict.record_uuid,
                conflict.table_name,
                json.dumps(conflict.local_data, default=str),
                json.dumps(conflict.remote_data, default=str),
                json.dumps(conflict.winning_data, default=str),
                conflict.resolution,
                datetime.now().isoformat(),
            ))
            conn.commit()
        except sqlite3.OperationalError:
            # Tablo yoksa oluştur
            self._ensure_conflicts_table(conn)
            conn.execute("""
                INSERT INTO sync_conflicts
                (record_uuid, table_name, local_data, remote_data,
                 winning_data, resolution, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conflict.record_uuid,
                conflict.table_name,
                json.dumps(conflict.local_data, default=str),
                json.dumps(conflict.remote_data, default=str),
                json.dumps(conflict.winning_data, default=str),
                conflict.resolution,
                datetime.now().isoformat(),
            ))
            conn.commit()
        finally:
            conn.close()

    def _ensure_conflicts_table(self, conn: sqlite3.Connection):
        """sync_conflicts tablosunu oluştur"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uuid VARCHAR(36) NOT NULL,
                table_name VARCHAR(100) NOT NULL,
                local_data TEXT,
                remote_data TEXT,
                winning_data TEXT,
                resolution VARCHAR(50),
                resolved_by VARCHAR(36),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

    def get_conflicts(self, resolved: bool = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Çakışma kayıtlarını al.

        Args:
            resolved: True=çözülmüş, False=çözülmemiş, None=hepsi
            limit: Maksimum kayıt sayısı

        Returns:
            Çakışma listesi
        """
        conn = self._get_connection()
        try:
            if resolved is None:
                rows = conn.execute("""
                    SELECT * FROM sync_conflicts
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            elif resolved:
                rows = conn.execute("""
                    SELECT * FROM sync_conflicts
                    WHERE resolution IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM sync_conflicts
                    WHERE resolution IS NULL
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()

            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def apply_resolution(self, conflict_id: int, resolution: str,
                        winning_data: Dict[str, Any]):
        """
        Çözümü uygula (manuel mod için).

        Args:
            conflict_id: Çakışma ID'si
            resolution: 'local' veya 'remote'
            winning_data: Kazanan veri
        """
        conn = self._get_connection()
        try:
            # Çakışma kaydını güncelle
            conn.execute("""
                UPDATE sync_conflicts
                SET resolution = ?, winning_data = ?
                WHERE id = ?
            """, (resolution, json.dumps(winning_data, default=str), conflict_id))

            # Ana tabloya uygula
            conflict = conn.execute(
                "SELECT table_name, record_uuid FROM sync_conflicts WHERE id = ?",
                (conflict_id,)
            ).fetchone()

            if conflict:
                table_name = conflict['table_name']
                uuid = conflict['record_uuid']

                # Tabloyu güncelle
                set_clauses = []
                values = []

                for key, value in winning_data.items():
                    if key not in ('id', 'uuid'):
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                set_clauses.append("synced_at = ?")
                values.append(datetime.now().isoformat())
                values.append(uuid)

                conn.execute(
                    f"UPDATE {table_name} SET {','.join(set_clauses)} WHERE uuid = ?",
                    values
                )

            conn.commit()
        finally:
            conn.close()

    def clear_old_conflicts(self, older_than_days: int = 30):
        """Eski çakışma kayıtlarını temizle"""
        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM sync_conflicts
                WHERE created_at < datetime('now', ? || ' days')
            """, (f'-{older_than_days}',))
            conn.commit()
        finally:
            conn.close()
