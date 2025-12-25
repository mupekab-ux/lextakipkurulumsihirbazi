# -*- coding: utf-8 -*-
"""
Sync Manager

Ana senkronizasyon yöneticisi.
Tüm sync bileşenlerini koordine eder.
"""

import json
import logging
import platform
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

from .models import (
    SyncStatus, SyncConfig, SyncResult, SyncConflict,
    DeviceInfo, SYNCED_TABLES, SYNC_COLUMNS
)
from .encryption_service import EncryptionService, RecoveryCodeManager
from .sync_client import SyncClient, FirmMismatchError, DeviceNotApprovedError
from .outbox_processor import OutboxProcessor
from .inbox_processor import InboxProcessor
from .conflict_handler import ConflictHandler
from .migration import SyncMigration, UUID_FK_RELATIONS

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Ana senkronizasyon yöneticisi.

    Kullanım:
        sync_manager = SyncManager(db_path)
        sync_manager.initialize(config)
        sync_manager.start_background_sync()
    """

    DEFAULT_SYNC_INTERVAL = 30  # saniye

    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLite veritabanı yolu
        """
        self.db_path = db_path
        self.config: Optional[SyncConfig] = None
        self.status = SyncStatus.NOT_CONFIGURED

        # Alt bileşenler
        self.client: Optional[SyncClient] = None
        self.encryption: Optional[EncryptionService] = None
        self.outbox: Optional[OutboxProcessor] = None
        self.inbox: Optional[InboxProcessor] = None
        self.conflict_handler: Optional[ConflictHandler] = None

        # Thread yönetimi
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sync_interval = self.DEFAULT_SYNC_INTERVAL
        self._lock = threading.Lock()

        # Callbacks
        self.on_status_change: Optional[Callable[[SyncStatus], None]] = None
        self.on_sync_complete: Optional[Callable[[SyncResult], None]] = None
        self.on_conflict: Optional[Callable[[SyncConflict], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Sync tablolarını oluştur
        self._ensure_sync_tables()

        # Mevcut yapılandırmayı yüklemeyi dene
        self.load_config_from_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================================
    # YAPILANDIRMA
    # ============================================================

    def initialize(self, config: SyncConfig) -> bool:
        """
        Senkronizasyonu başlat.

        Args:
            config: SyncConfig instance

        Returns:
            Başarılıysa True
        """
        if not config.is_valid():
            logger.error("Geçersiz sync yapılandırması")
            return False

        self.config = config

        # Alt bileşenleri oluştur
        self.encryption = EncryptionService(config.firm_key)
        self.client = SyncClient(config)
        self.outbox = OutboxProcessor(self.db_path, self.client, self.encryption)
        self.inbox = InboxProcessor(self.db_path, self.client, self.encryption)
        self.conflict_handler = ConflictHandler(self.db_path)

        # Tabloları hazırla
        self._ensure_sync_tables()

        self.status = SyncStatus.IDLE
        self._notify_status_change()

        logger.info("SyncManager başlatıldı")
        return True

    def load_config_from_db(self) -> bool:
        """
        Yapılandırmayı veritabanından yükle.

        Returns:
            Yapılandırma bulunduysa True
        """
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT device_id, firm_id, firm_key_encrypted,
                       server_url, access_token, refresh_token, is_sync_enabled
                FROM sync_metadata
                LIMIT 1
            """).fetchone()

            if not row:
                return False

            # Pending approval durumu (is_sync_enabled = 0)
            if not row['is_sync_enabled']:
                # Pending approval için minimal config oluştur
                temp_config = SyncConfig(
                    server_url=row['server_url'],
                    firm_id=row['firm_id'],
                    device_id=row['device_id'],
                    firm_key=b"",
                )
                self.client = SyncClient(temp_config)
                self.config = temp_config
                self.status = SyncStatus.PENDING_APPROVAL
                logger.info("Pending approval durumu yüklendi")
                return True

            # Normal durum - tam yapılandırma
            firm_key = row['firm_key_encrypted']

            config = SyncConfig(
                server_url=row['server_url'],
                firm_id=row['firm_id'],
                device_id=row['device_id'],
                firm_key=firm_key,
                access_token=row['access_token'],
                refresh_token=row['refresh_token'],
            )

            return self.initialize(config)

        except sqlite3.OperationalError:
            # Tablo yok
            return False
        finally:
            conn.close()

    def save_config_to_db(self):
        """Yapılandırmayı veritabanına kaydet"""
        if not self.config:
            return

        conn = self._get_connection()
        try:
            # Önce mevcut kaydı sil
            conn.execute("DELETE FROM sync_metadata")

            conn.execute("""
                INSERT INTO sync_metadata
                (device_id, firm_id, firm_key_encrypted, server_url,
                 access_token, refresh_token, is_sync_enabled)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                self.config.device_id,
                self.config.firm_id,
                self.config.firm_key,  # TODO: Cihaz anahtarıyla şifrele
                self.config.server_url,
                self.config.access_token,
                self.config.refresh_token,
            ))
            conn.commit()
        finally:
            conn.close()

    def clear_config(self):
        """Yapılandırmayı temizle"""
        conn = self._get_connection()
        try:
            # Kaydı tamamen sil
            conn.execute("DELETE FROM sync_metadata")
            conn.commit()
        finally:
            conn.close()

        self.config = None
        self.client = None
        self.encryption = None
        self.outbox = None
        self.inbox = None
        self.conflict_handler = None
        self.status = SyncStatus.NOT_CONFIGURED
        self._notify_status_change()

    # ============================================================
    # ARKA PLAN SENKRONİZASYON
    # ============================================================

    def start_background_sync(self):
        """Arka plan senkronizasyonunu başlat"""
        if self._sync_thread and self._sync_thread.is_alive():
            logger.warning("Arka plan sync zaten çalışıyor")
            return

        if self.status == SyncStatus.NOT_CONFIGURED:
            logger.warning("Sync yapılandırılmamış, arka plan sync başlatılamaz")
            return

        self._stop_event.clear()
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            name="SyncThread",
            daemon=True
        )
        self._sync_thread.start()
        logger.info("Arka plan sync başlatıldı")

    def stop_background_sync(self):
        """Arka plan senkronizasyonunu durdur"""
        self._stop_event.set()
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
            self._sync_thread = None
        logger.info("Arka plan sync durduruldu")

    def set_sync_interval(self, seconds: int):
        """Sync aralığını ayarla"""
        self._sync_interval = max(10, seconds)  # Minimum 10 saniye

    def _sync_loop(self):
        """Arka plan sync döngüsü"""
        while not self._stop_event.is_set():
            try:
                self._perform_sync()
            except Exception as e:
                logger.error(f"Sync döngüsü hatası: {e}")
                self.status = SyncStatus.ERROR
                self._notify_status_change()

                if self.on_error:
                    self.on_error(str(e))

            # Interruptible bekleme
            self._stop_event.wait(self._sync_interval)

    # ============================================================
    # SENKRONİZASYON İŞLEMLERİ
    # ============================================================

    def sync_now(self) -> SyncResult:
        """
        Hemen senkronize et.

        Returns:
            SyncResult instance
        """
        with self._lock:
            return self._perform_sync()

    def _perform_sync(self) -> SyncResult:
        """Senkronizasyon işlemi"""
        start_time = time.time()
        result = SyncResult(success=False)

        if self.status == SyncStatus.NOT_CONFIGURED:
            result.errors.append("Sync yapılandırılmamış")
            return result

        if self.status == SyncStatus.SYNCING:
            result.errors.append("Sync zaten devam ediyor")
            return result

        self.status = SyncStatus.SYNCING
        self._notify_status_change()

        try:
            # 1. Bağlantı kontrolü
            if not self.client.check_connection():
                self.status = SyncStatus.OFFLINE
                self._notify_status_change()
                result.errors.append("Sunucuya bağlanılamadı")
                return result

            # 2. Firma doğrulaması
            try:
                self.client.validate_firm_connection()
            except FirmMismatchError as e:
                self.status = SyncStatus.ERROR
                self._notify_status_change()
                result.errors.append(str(e))
                return result

            # 3. Token yenile (gerekirse)
            if self.config.access_token:
                try:
                    self.client.refresh_token()
                except Exception:
                    pass  # Login gerekebilir

            # 4. Push: Lokal değişiklikleri gönder
            push_result = self.outbox.process()
            result.pushed_count = push_result['count']

            for conflict in push_result.get('conflicts', []):
                resolved = self.conflict_handler.resolve(conflict)
                result.conflicts.append(conflict)
                if self.on_conflict:
                    self.on_conflict(conflict)

            # 5. Pull: Uzak değişiklikleri al
            pull_result = self.inbox.fetch_and_process()
            result.pulled_count = pull_result['count']
            result.last_revision = pull_result['last_revision']

            for conflict in pull_result.get('conflicts', []):
                resolved = self.conflict_handler.resolve(conflict)
                result.conflicts.append(conflict)
                if self.on_conflict:
                    self.on_conflict(conflict)

            # 6. Başarılı
            result.success = True
            self.status = SyncStatus.IDLE
            self._notify_status_change()

            # 7. Son sync zamanını güncelle
            self._update_last_sync()

            logger.info(
                f"Sync tamamlandı: {result.pushed_count} push, "
                f"{result.pulled_count} pull, {len(result.conflicts)} çakışma"
            )

        except Exception as e:
            logger.error(f"Sync hatası: {e}")
            result.errors.append(str(e))
            self.status = SyncStatus.ERROR
            self._notify_status_change()

        result.sync_duration_ms = (time.time() - start_time) * 1000

        if self.on_sync_complete:
            self.on_sync_complete(result)

        return result

    def _update_last_sync(self):
        """Son sync zamanını güncelle"""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE sync_metadata
                SET last_sync_at = ?
            """, (datetime.now().isoformat(),))
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # KÜNYE TABANLI TAM SENKRONİZASYON
    # ============================================================

    def full_sync(self) -> Dict[str, Any]:
        """
        Künye tabanlı tam senkronizasyon.

        1. Tüm lokal künyeleri topla (uuid + updated_at)
        2. Sunucuya gönder
        3. Sunucu eksik/güncel olanları gönderir
        4. Sunucu bizden istenen verileri alır
        5. BN değişikliklerini uygula

        Returns:
            {success, received, sent, bn_changes, errors}
        """
        result = {
            'success': False,
            'received': 0,
            'sent': 0,
            'bn_changes': [],
            'errors': []
        }

        if self.status == SyncStatus.NOT_CONFIGURED:
            result['errors'].append("Sync yapılandırılmamış")
            return result

        if not self.client:
            result['errors'].append("Client yapılandırılmamış")
            return result

        try:
            # 1. Tüm lokal künyeleri topla
            kunyeler = self._get_all_kunyeler()
            logger.debug(f"Toplam {len(kunyeler)} künye toplandı")

            # 2. Outbox'taki bekleyen değişiklikleri al
            pending_changes = self._get_pending_changes()
            logger.debug(f"{len(pending_changes)} bekleyen değişiklik")

            # 3. Sunucuya sync isteği gönder
            response = self._send_sync_request(kunyeler, pending_changes)

            if not response.get('success', False):
                result['errors'].append(response.get('message', 'Sync başarısız'))
                return result

            # 4. Sunucudan gelen verileri uygula
            to_client = response.get('to_client', [])
            for record in to_client:
                try:
                    self._apply_remote_record(record)
                    result['received'] += 1
                except Exception as e:
                    logger.error(f"Kayıt uygulama hatası: {e}")
                    result['errors'].append(str(e))

            # 5. Sunucunun istediği verileri gönder
            need_from_client = response.get('need_from_client', [])
            if need_from_client:
                sent_count = self._send_requested_records(need_from_client)
                result['sent'] = sent_count

            # 6. BN değişikliklerini uygula
            bn_changes = response.get('bn_changes', [])
            for bn_change in bn_changes:
                try:
                    self._apply_bn_change(bn_change)
                    result['bn_changes'].append(bn_change)
                except Exception as e:
                    logger.error(f"BN değişiklik hatası: {e}")

            # 7. Outbox'ı temizle
            self._mark_changes_synced(pending_changes)

            # 8. Son sync zamanını güncelle
            self._update_last_sync()

            result['success'] = True
            logger.info(
                f"Full sync tamamlandı: {result['received']} alındı, "
                f"{result['sent']} gönderildi, {len(bn_changes)} BN değişikliği"
            )

        except Exception as e:
            logger.error(f"Full sync hatası: {e}")
            result['errors'].append(str(e))

        return result

    def force_sync_all(self) -> Dict[str, Any]:
        """
        Tüm mevcut verileri zorla senkronize et.

        Bu metod:
        1. Mevcut verileri outbox'a ekler (seed_existing_data)
        2. Full sync çalıştırır

        Returns:
            {success, seeded, received, sent, errors}
        """
        result = {
            'success': False,
            'seeded': 0,
            'received': 0,
            'sent': 0,
            'errors': []
        }

        if self.status == SyncStatus.NOT_CONFIGURED:
            result['errors'].append("Sync yapılandırılmamış")
            return result

        try:
            # 1. Mevcut verileri outbox'a ekle
            migration = SyncMigration(self.db_path)
            seeded = migration.seed_existing_data()
            result['seeded'] = seeded
            logger.info(f"Force sync: {seeded} kayıt outbox'a eklendi")

            # 2. Full sync çalıştır
            sync_result = self.full_sync()
            result['received'] = sync_result.get('received', 0)
            result['sent'] = sync_result.get('sent', 0)
            result['errors'].extend(sync_result.get('errors', []))
            result['success'] = sync_result.get('success', False)

            if result['success']:
                logger.info(
                    f"Force sync tamamlandı: {seeded} seeded, "
                    f"{result['received']} alındı, {result['sent']} gönderildi"
                )

        except Exception as e:
            logger.error(f"Force sync hatası: {e}")
            result['errors'].append(str(e))

        return result

    def _get_all_kunyeler(self) -> List[Dict[str, str]]:
        """Tüm tabloların UUID ve updated_at bilgisini döndür"""
        kunyeler = []
        conn = self._get_connection()

        try:
            for table in SYNCED_TABLES:
                try:
                    # Tablo var mı kontrol et
                    exists = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    ).fetchone()

                    if not exists:
                        continue

                    # uuid kolonu var mı?
                    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
                    if 'uuid' not in columns:
                        continue

                    # updated_at kolonu var mı?
                    has_updated_at = 'updated_at' in columns

                    if has_updated_at:
                        rows = conn.execute(f"""
                            SELECT uuid, updated_at FROM {table}
                            WHERE uuid IS NOT NULL AND uuid != ''
                        """).fetchall()
                    else:
                        rows = conn.execute(f"""
                            SELECT uuid, NULL as updated_at FROM {table}
                            WHERE uuid IS NOT NULL AND uuid != ''
                        """).fetchall()

                    for row in rows:
                        kunyeler.append({
                            'uuid': row[0],
                            'table_name': table,
                            'updated_at': row[1] or datetime.now().isoformat()
                        })

                except sqlite3.OperationalError as e:
                    logger.debug(f"{table} tablosu okunamadı: {e}")
                    continue

        finally:
            conn.close()

        return kunyeler

    def _get_pending_changes(self) -> List[Dict[str, Any]]:
        """Outbox'taki bekleyen değişiklikleri al"""
        conn = self._get_connection()
        changes = []

        try:
            rows = conn.execute("""
                SELECT id, uuid, table_name, operation, data_json
                FROM sync_outbox
                WHERE synced = 0
                ORDER BY created_at
            """).fetchall()

            for row in rows:
                try:
                    data = json.loads(row[4]) if row[4] else {}
                except:
                    data = {}

                changes.append({
                    'id': row[0],
                    'uuid': row[1],
                    'table_name': row[2],
                    'operation': row[3],
                    'data': data
                })

        finally:
            conn.close()

        return changes

    def _send_sync_request(
        self,
        kunyeler: List[Dict],
        changes: List[Dict]
    ) -> Dict[str, Any]:
        """Sunucuya sync isteği gönder"""
        try:
            # Token kontrolü
            if not self.config.access_token:
                return {'success': False, 'message': 'Token yok, login gerekli'}

            # API çağrısı
            response = self.client._session.post(
                self.client._get_url('/api/sync'),
                json={
                    'kunyeler': kunyeler,
                    'changes': changes
                },
                timeout=120,
                verify=False
            )

            if response.status_code == 401:
                # Token yenilemeyi dene
                try:
                    self.client.refresh_token()
                    # Tekrar dene
                    response = self.client._session.post(
                        self.client._get_url('/api/sync'),
                        json={
                            'kunyeler': kunyeler,
                            'changes': changes
                        },
                        timeout=120,
                        verify=False
                    )
                except:
                    return {'success': False, 'message': 'Token yenilenemedi'}

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Sync request hatası: {e}")
            return {'success': False, 'message': str(e)}

    def _apply_remote_record(self, record: Dict[str, Any]):
        """Sunucudan gelen kaydı lokal veritabanına uygula"""
        record_uuid = record.get('uuid')
        table_name = record.get('table_name')
        operation = record.get('operation', 'INSERT')
        data = record.get('data', {})

        if not record_uuid or not table_name:
            return

        if table_name not in SYNCED_TABLES:
            logger.warning(f"Bilinmeyen tablo: {table_name}")
            return

        conn = self._get_connection()
        try:
            if operation == 'DELETE':
                # Soft delete
                conn.execute(
                    f"UPDATE {table_name} SET is_deleted = 1 WHERE uuid = ?",
                    (record_uuid,)
                )
            else:
                # INSERT veya UPDATE
                # Mevcut kaydı kontrol et
                existing = conn.execute(
                    f"SELECT uuid FROM {table_name} WHERE uuid = ?",
                    (record_uuid,)
                ).fetchone()

                # Kolon listesini al
                columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]

                # Sadece mevcut kolonları filtrele
                filtered_data = {k: v for k, v in data.items() if k in columns and k != 'id'}

                # ============================================================
                # UUID FK -> INTEGER FK ÇÖZÜMLEME
                # Sunucudan gelen UUID FK değerlerini lokal integer ID'lere çevir
                # ============================================================
                for fk_table, uuid_col, ref_table, int_col in UUID_FK_RELATIONS:
                    if table_name == fk_table and uuid_col in filtered_data:
                        ref_uuid = filtered_data.get(uuid_col)
                        if ref_uuid:
                            # Referans tablodaki lokal integer ID'yi bul
                            ref_row = conn.execute(
                                f"SELECT id FROM {ref_table} WHERE uuid = ?",
                                (ref_uuid,)
                            ).fetchone()

                            if ref_row:
                                # Lokal integer FK'yı ayarla
                                if int_col in columns:
                                    filtered_data[int_col] = ref_row[0]
                                logger.debug(
                                    f"{table_name}.{uuid_col}={ref_uuid} -> "
                                    f"{int_col}={ref_row[0]}"
                                )
                            else:
                                # Referans kayıt henüz yok, integer FK'yı NULL bırak
                                # (daha sonra sync edildiğinde düzelecek)
                                logger.warning(
                                    f"Referans kayıt bulunamadı: {ref_table}.uuid={ref_uuid}"
                                )
                                if int_col in columns:
                                    filtered_data[int_col] = None
                # ============================================================

                if existing:
                    # UPDATE
                    if filtered_data:
                        set_clause = ", ".join([f"{k} = ?" for k in filtered_data.keys()])
                        values = list(filtered_data.values()) + [record_uuid]
                        conn.execute(
                            f"UPDATE {table_name} SET {set_clause} WHERE uuid = ?",
                            values
                        )
                else:
                    # INSERT
                    filtered_data['uuid'] = record_uuid
                    columns_str = ", ".join(filtered_data.keys())
                    placeholders = ", ".join(["?" for _ in filtered_data])
                    conn.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})",
                        list(filtered_data.values())
                    )

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"Kayıt uygulama hatası ({table_name}): {e}")
            raise
        finally:
            conn.close()

    def _send_requested_records(self, uuids: List[str]) -> int:
        """Sunucunun istediği kayıtları gönder"""
        sent = 0
        conn = self._get_connection()

        try:
            for record_uuid in uuids:
                # Tüm tablolarda ara
                for table in SYNCED_TABLES:
                    try:
                        row = conn.execute(
                            f"SELECT * FROM {table} WHERE uuid = ?",
                            (record_uuid,)
                        ).fetchone()

                        if row:
                            # Kayıt bulundu, gönder
                            data = dict(row)
                            change = {
                                'uuid': record_uuid,
                                'table_name': table,
                                'operation': 'INSERT',
                                'data': data
                            }

                            # Push
                            self.client._session.post(
                                self.client._get_url('/api/sync/push'),
                                json={'changes': [change]},
                                timeout=30,
                                verify=False
                            )
                            sent += 1
                            break

                    except sqlite3.OperationalError:
                        continue

        finally:
            conn.close()

        return sent

    def _apply_bn_change(self, bn_change: Dict[str, Any]):
        """BN değişikliğini lokal veritabanına uygula"""
        record_uuid = bn_change.get('uuid')
        new_bn = bn_change.get('new_bn')
        old_bn = bn_change.get('old_bn')

        if not record_uuid or not new_bn:
            return

        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE dosyalar SET buro_takip_no = ? WHERE uuid = ?",
                (new_bn, record_uuid)
            )
            conn.commit()
            logger.info(f"BN değişikliği uygulandı: {old_bn} → {new_bn} (uuid={record_uuid})")
        finally:
            conn.close()

    def _mark_changes_synced(self, changes: List[Dict]):
        """Gönderilen değişiklikleri synced olarak işaretle"""
        if not changes:
            return

        conn = self._get_connection()
        try:
            ids = [c['id'] for c in changes if 'id' in c]
            if ids:
                placeholders = ",".join(["?" for _ in ids])
                conn.execute(
                    f"UPDATE sync_outbox SET synced = 1, synced_at = ? WHERE id IN ({placeholders})",
                    [datetime.now().isoformat()] + ids
                )
                conn.commit()
        finally:
            conn.close()

    # ============================================================
    # BÜRO YÖNETİMİ
    # ============================================================

    def setup_new_firm(self, server_url: str, firm_name: str,
                       admin_username: str, admin_password: str,
                       admin_email: str = "") -> Dict[str, Any]:
        """
        Yeni büro kur.

        Args:
            server_url: Sync server URL
            firm_name: Büro adı
            admin_username: Yönetici kullanıcı adı
            admin_password: Yönetici şifresi
            admin_email: E-posta (opsiyonel)

        Returns:
            {firm_id, recovery_code, join_code}
        """
        # Geçici client oluştur
        device_info = DeviceInfo.collect()
        temp_config = SyncConfig(
            server_url=server_url,
            firm_id="",  # Henüz yok
            device_id=device_info.device_id,
            firm_key=b"",  # Henüz yok
        )

        client = SyncClient(temp_config)

        # Büro oluştur
        response = client.init_firm(
            firm_name=firm_name,
            admin_username=admin_username,
            admin_password=admin_password,
            admin_email=admin_email,
        )

        # Yapılandırmayı kaydet
        firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']

        self.config = SyncConfig(
            server_url=server_url,
            firm_id=response['firm_id'],
            device_id=device_info.device_id,
            firm_key=firm_key,
        )

        self.initialize(self.config)

        # Otomatik login yap
        try:
            login_result = self.client.login(admin_username, admin_password)
            self.config.access_token = login_result.get('access_token')
            self.config.refresh_token = login_result.get('refresh_token')
            logger.info("Büro kurulumu sonrası otomatik login başarılı")
        except Exception as e:
            logger.warning(f"Otomatik login başarısız: {e}")

        self.save_config_to_db()

        # Migration çalıştır - trigger'ları ve sync kolonlarını oluştur
        try:
            migration = SyncMigration(self.db_path)
            success, msg = migration.run_all()
            if success:
                logger.info("Sync migration tamamlandı")
            else:
                logger.warning(f"Sync migration uyarı: {msg}")
        except Exception as e:
            logger.error(f"Sync migration hatası: {e}")

        # Kurtarma kodu üret
        recovery_manager = RecoveryCodeManager()
        recovery_code = recovery_manager.generate_recovery_code(firm_key)

        return {
            'firm_id': response['firm_id'],
            'recovery_code': recovery_code,
            'join_code': response.get('join_code', ''),
        }

    def join_firm(self, server_url: str, join_code: str) -> Dict[str, Any]:
        """
        Mevcut büroya katıl.

        Args:
            server_url: Sync server URL
            join_code: Katılım kodu

        Returns:
            {status: 'joined'|'pending_approval', firm_name?, message?}
        """
        # Mevcut veri kontrolü
        if self._has_synced_data():
            raise ValueError(
                "Bu cihazda başka büroya ait veri var. "
                "Önce 'Bürodan Ayrıl' işlemi yapın."
            )

        # Geçici client oluştur
        device_info = DeviceInfo.collect()
        temp_config = SyncConfig(
            server_url=server_url,
            firm_id="",
            device_id=device_info.device_id,
            firm_key=b"",
        )

        client = SyncClient(temp_config)

        # Katılım isteği
        response = client.join_firm(
            join_code=join_code,
            device_name=device_info.device_name,
            device_info=device_info.to_dict(),
        )

        if response.get('requires_approval'):
            # Onay bekliyor - sunucunun oluşturduğu device_id'yi kaydet
            self._save_pending_config(
                server_url=server_url,
                firm_id=response['firm_id'],
                device_id=response['device_id'],  # Sunucunun oluşturduğu device_id
            )

            # Config ve client'ı ayarla (status kontrolü için gerekli)
            self.config = SyncConfig(
                server_url=server_url,
                firm_id=response['firm_id'],
                device_id=response['device_id'],
                firm_key=b"",  # Henüz yok, onaydan sonra gelecek
            )
            self.client = SyncClient(self.config)

            self.status = SyncStatus.PENDING_APPROVAL
            self._notify_status_change()

            return {
                'status': 'pending_approval',
                'message': 'Cihazınız yönetici onayı bekliyor.',
            }

        # Hemen katıldı
        firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']

        self.config = SyncConfig(
            server_url=server_url,
            firm_id=response['firm_id'],
            device_id=response['device_id'],  # Sunucunun oluşturduğu device_id
            firm_key=firm_key,
        )

        self.initialize(self.config)
        self.save_config_to_db()

        # Migration çalıştır
        try:
            migration = SyncMigration(self.db_path)
            migration.run_all()
            logger.info("Sync migration tamamlandı (join)")
        except Exception as e:
            logger.error(f"Sync migration hatası: {e}")

        return {
            'status': 'joined',
            'firm_name': response.get('firm_name', ''),
        }

    def check_approval_status(self) -> Dict[str, Any]:
        """
        Cihaz onay durumunu kontrol et.

        Returns:
            {is_approved, firm_key?, needs_login?}
        """
        if not self.client:
            raise ValueError("Client yapılandırılmamış")

        response = self.client.check_approval_status()

        if response.get('is_approved'):
            # Onaylandı, firm_key'i al
            firm_key = response['firm_key'].encode() if isinstance(response['firm_key'], str) else response['firm_key']
            self.config.firm_key = firm_key

            # NOT: Token almak için login gerekiyor
            # UI'da login dialog gösterilecek
            response['needs_login'] = True

            logger.info("Cihaz onaylandı, login gerekiyor")

        return response

    def login_after_approval(self, username: str, password: str) -> Dict[str, Any]:
        """
        Onay sonrası login yap ve sync'i başlat.

        Args:
            username: Kullanıcı adı
            password: Şifre

        Returns:
            {success, message}
        """
        if not self.client:
            raise ValueError("Client yapılandırılmamış")

        if not self.config or not self.config.firm_key:
            raise ValueError("Önce onay durumu kontrol edilmeli")

        try:
            # Login yap
            login_result = self.client.login(username, password)

            # Token'ları config'e kaydet
            self.config.access_token = login_result.get('access_token')
            self.config.refresh_token = login_result.get('refresh_token')

            # Şimdi tam initialize et
            self.initialize(self.config)
            self.save_config_to_db()

            # Migration çalıştır
            try:
                migration = SyncMigration(self.db_path)
                migration.run_all()
                logger.info("Sync migration tamamlandı (login sonrası)")

                # Mevcut verileri outbox'a ekle (ilk senkronizasyon için)
                seeded_count = migration.seed_existing_data()
                if seeded_count > 0:
                    logger.info(f"{seeded_count} mevcut kayıt outbox'a eklendi")
            except Exception as e:
                logger.error(f"Sync migration hatası: {e}")

            self.status = SyncStatus.IDLE
            self._notify_status_change()

            logger.info("Login başarılı, sync hazır")
            return {'success': True, 'message': 'Giriş başarılı, senkronizasyon hazır.'}

        except Exception as e:
            logger.error(f"Login hatası: {e}")
            raise

    def leave_firm(self, keep_local_data: bool = False) -> Dict[str, Any]:
        """
        Bürodan ayrıl.

        Args:
            keep_local_data: True ise veriler silinmez

        Returns:
            {status, backup_path?}
        """
        backup_path = None

        # Sunucuya bildir
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass

        # Veriyi temizle
        if not keep_local_data:
            backup_path = self._backup_and_clear_data()

        # Yapılandırmayı temizle
        self.clear_config()
        self.stop_background_sync()

        return {
            'status': 'left',
            'backup_path': backup_path,
        }

    def reset_sync_state(self) -> Dict[str, Any]:
        """
        Sync durumunu sıfırla - sunucu verilerini silmeden lokal sync'i yeniden başlat.

        Bu işlem:
        1. Lokal sync tablolarını temizler (outbox, revision)
        2. Sunucuya sıfırlama isteği gönderir
        3. Mevcut lokal verileri outbox'a ekler
        4. Full sync çalıştırır

        Returns:
            {success, message, seeded, received, sent}
        """
        result = {
            'success': False,
            'message': '',
            'seeded': 0,
            'received': 0,
            'sent': 0,
        }

        if self.status == SyncStatus.NOT_CONFIGURED:
            result['message'] = "Sync yapılandırılmamış"
            return result

        if not self.client:
            result['message'] = "Client yapılandırılmamış"
            return result

        conn = self._get_connection()
        try:
            logger.info("Sync durumu sıfırlanıyor...")

            # Step 1: Lokal sync tablolarını temizle
            conn.execute("DELETE FROM sync_outbox")
            conn.execute("UPDATE sync_metadata SET last_sync_revision = 0")
            conn.commit()
            logger.info("Lokal sync tabloları temizlendi")

            # Step 2: Sunucuya sıfırlama isteği gönder
            try:
                response = self.client._session.post(
                    self.client._get_url('/api/sync/reset'),
                    timeout=30,
                    verify=False
                )
                if response.status_code == 200:
                    logger.info("Sunucu sync durumu sıfırlandı")
                else:
                    logger.warning(f"Sunucu sıfırlama yanıtı: {response.status_code}")
            except Exception as e:
                logger.warning(f"Sunucu sıfırlama hatası (devam edilecek): {e}")

            # Step 3: Trigger'ları yeniden oluştur (UUID FK desteği ile)
            try:
                from .migration import SyncMigration, UUIDFKMigration

                # UUID FK migration'ı çalıştır
                uuid_migration = UUIDFKMigration(self.db_path)
                uuid_result = uuid_migration.run_full_migration()
                logger.info(f"UUID FK migration: {uuid_result}")

                # Trigger'ları yeniden oluştur
                migration = SyncMigration(self.db_path)
                migration.drop_all_sync_triggers()
                migration.create_triggers()
                logger.info("Trigger'lar yeniden oluşturuldu")
            except Exception as e:
                logger.error(f"Migration hatası: {e}")

            # Step 4: Mevcut lokal verileri outbox'a ekle
            migration = SyncMigration(self.db_path)
            seeded = migration.seed_existing_data()
            result['seeded'] = seeded
            logger.info(f"{seeded} mevcut kayıt outbox'a eklendi")

            # Step 5: Full sync çalıştır
            sync_result = self.full_sync()
            result['received'] = sync_result.get('received', 0)
            result['sent'] = sync_result.get('sent', 0)

            if sync_result.get('success'):
                result['success'] = True
                result['message'] = (
                    f"Sync durumu sıfırlandı. "
                    f"{seeded} kayıt gönderildi, "
                    f"{result['received']} kayıt alındı."
                )
            else:
                result['message'] = f"Sync kısmen başarılı: {sync_result.get('errors', [])}"

            logger.info(f"Sync sıfırlama tamamlandı: {result}")

        except Exception as e:
            logger.error(f"Sync sıfırlama hatası: {e}")
            result['message'] = str(e)
            conn.rollback()
        finally:
            conn.close()

        return result

    # ============================================================
    # YARDIMCI METODLAR
    # ============================================================

    def _has_synced_data(self) -> bool:
        """Senkronize edilmiş veri var mı?"""
        conn = self._get_connection()
        try:
            result = conn.execute("""
                SELECT firm_id FROM sync_metadata
                WHERE firm_id IS NOT NULL AND firm_id != ''
                LIMIT 1
            """).fetchone()
            return result is not None
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    def _save_pending_config(self, server_url: str, firm_id: str, device_id: str):
        """Onay bekleyen yapılandırmayı kaydet"""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM sync_metadata")
            conn.execute("""
                INSERT INTO sync_metadata
                (device_id, firm_id, server_url, is_sync_enabled)
                VALUES (?, ?, ?, 0)
            """, (device_id, firm_id, server_url))
            conn.commit()
        finally:
            conn.close()

    def _backup_and_clear_data(self) -> str:
        """Veriyi yedekle ve temizle"""
        # TODO: Yedekleme implementasyonu
        backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

        # Sync tablolarını temizle
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM sync_outbox")
            conn.execute("DELETE FROM sync_inbox")

            # Senkronize verilerdeki firm bilgilerini temizle
            for table in SYNCED_TABLES:
                try:
                    conn.execute(f"UPDATE {table} SET firm_id = NULL, synced_at = NULL")
                except sqlite3.OperationalError:
                    pass

            conn.commit()
        finally:
            conn.close()

        return backup_path

    def _ensure_sync_tables(self):
        """Sync tablolarının var olduğundan emin ol"""
        conn = self._get_connection()
        try:
            # sync_metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR(36) NOT NULL,
                    firm_id VARCHAR(36),
                    firm_key_encrypted BLOB,
                    last_sync_revision INTEGER DEFAULT 0,
                    last_sync_at DATETIME,
                    server_url TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    is_sync_enabled INTEGER DEFAULT 0
                )
            """)

            # Eski tablolarda access_token ve refresh_token yoksa ekle
            try:
                conn.execute("ALTER TABLE sync_metadata ADD COLUMN access_token TEXT")
            except sqlite3.OperationalError:
                pass  # Kolon zaten var

            try:
                conn.execute("ALTER TABLE sync_metadata ADD COLUMN refresh_token TEXT")
            except sqlite3.OperationalError:
                pass  # Kolon zaten var

            # sync_outbox
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    last_retry_at DATETIME,
                    synced INTEGER DEFAULT 0,
                    synced_at DATETIME,
                    error_message TEXT
                )
            """)

            # sync_inbox
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) NOT NULL,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed INTEGER DEFAULT 0,
                    processed_at DATETIME
                )
            """)

            # sync_conflicts
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

            # İndeksler
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_pending "
                "ON sync_outbox(synced, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_inbox_pending "
                "ON sync_inbox(processed, revision)"
            )

            conn.commit()
        finally:
            conn.close()

    def _notify_status_change(self):
        """Durum değişikliğini bildir"""
        if self.on_status_change:
            self.on_status_change(self.status)

    # ============================================================
    # DURUM BİLGİSİ
    # ============================================================

    def get_status_info(self) -> Dict[str, Any]:
        """
        Detaylı durum bilgisi al.

        Returns:
            Durum dict
        """
        conn = self._get_connection()
        try:
            meta = conn.execute(
                "SELECT * FROM sync_metadata LIMIT 1"
            ).fetchone()

            pending_out = conn.execute(
                "SELECT COUNT(*) FROM sync_outbox WHERE synced = 0"
            ).fetchone()[0]

            pending_in = conn.execute(
                "SELECT COUNT(*) FROM sync_inbox WHERE processed = 0"
            ).fetchone()[0]

            return {
                'status': self.status.value,
                'is_configured': self.config is not None,
                'server_url': self.config.server_url if self.config else None,
                'firm_id': self.config.firm_id[:8] + '...' if self.config else None,
                'device_id': self.config.device_id if self.config else None,
                'last_sync_at': meta['last_sync_at'] if meta else None,
                'last_revision': meta['last_sync_revision'] if meta else 0,
                'pending_push': pending_out,
                'pending_pull': pending_in,
            }
        except sqlite3.OperationalError:
            return {
                'status': self.status.value,
                'is_configured': False,
            }
        finally:
            conn.close()

    def get_pending_changes_count(self) -> int:
        """Bekleyen değişiklik sayısını al"""
        if self.outbox:
            return self.outbox.get_pending_count()
        return 0
