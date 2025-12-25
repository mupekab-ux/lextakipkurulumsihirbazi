# -*- coding: utf-8 -*-
"""
Senkronizasyon HTTP İstemcisi

Sunucu ile iletişimi yönetir.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

from sync.config import SyncConfig, get_sync_config, save_sync_config

logger = logging.getLogger(__name__)

# SSL doğrulamasını devre dışı bırak (self-signed cert için)
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


@dataclass
class SyncResult:
    """Senkronizasyon sonucu."""
    success: bool
    message: str
    new_revision: int = 0
    changes_sent: int = 0
    changes_received: int = 0
    incoming_changes: List[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.incoming_changes is None:
            self.incoming_changes = []
        if self.errors is None:
            self.errors = []


@dataclass
class LoginResult:
    """Giriş sonucu."""
    success: bool
    message: str
    token: str = ""
    user_uuid: str = ""
    firm_id: str = ""
    firm_name: str = ""
    role: str = ""
    permissions: Dict[str, bool] = None


class SyncClient:
    """Sunucu ile senkronizasyon istemcisi."""

    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or get_sync_config()
        self.timeout = 30  # saniye

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        auth_required: bool = True
    ) -> Tuple[bool, Any]:
        """
        HTTP isteği yap.

        Returns:
            (success, response_data or error_message)
        """
        url = f"{self.config.api_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if auth_required and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        body = None
        if data:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')

        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, timeout=self.timeout, context=SSL_CONTEXT) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return True, response_data

        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('detail', str(e))
            except:
                error_msg = error_body or str(e)

            logger.error(f"HTTP hatası: {e.code} - {error_msg}")
            return False, f"HTTP {e.code}: {error_msg}"

        except URLError as e:
            logger.error(f"Bağlantı hatası: {e}")
            return False, f"Sunucuya bağlanılamadı: {e.reason}"

        except Exception as e:
            logger.exception("Beklenmeyen hata")
            return False, f"Hata: {str(e)}"

    def check_health(self) -> Tuple[bool, str]:
        """Sunucu sağlık durumunu kontrol et."""
        success, result = self._make_request("/api/health", auth_required=False)

        if success:
            return True, result.get('status', 'ok')
        return False, result

    def test_connection(self) -> Tuple[bool, str]:
        """Sunucu bağlantısını test et."""
        success, result = self._make_request("/public/token", auth_required=False)

        if success:
            return True, "Sunucu bağlantısı başarılı"
        return False, result

    def login(self, username: str, password: str) -> LoginResult:
        """
        Sunucuya giriş yap.

        Başarılı olursa token'ı config'e kaydeder.
        """
        data = {
            "username": username,
            "password": password,
            "device_id": self.config.device_id
        }

        success, result = self._make_request(
            "/api/login",
            method="POST",
            data=data,
            auth_required=False
        )

        if not success:
            return LoginResult(success=False, message=result)

        if not result.get('success'):
            return LoginResult(
                success=False,
                message=result.get('message', 'Giriş başarısız')
            )

        # Token'ı kaydet
        self.config.auth_token = result.get('token', '')
        self.config.user_uuid = result.get('user_uuid', '')
        self.config.firm_id = result.get('firm_id', '')
        self.config.firm_name = result.get('firm_name', '')
        self.config.username = username
        self.config.role = result.get('role', '')
        save_sync_config(self.config)

        return LoginResult(
            success=True,
            message="Giriş başarılı",
            token=result.get('token', ''),
            user_uuid=result.get('user_uuid', ''),
            firm_id=result.get('firm_id', ''),
            firm_name=result.get('firm_name', ''),
            role=result.get('role', ''),
            permissions=result.get('permissions', {})
        )

    def sync(self, changes: List[Dict[str, Any]] = None) -> SyncResult:
        """
        Senkronizasyon yap.

        Args:
            changes: Gönderilecek değişiklikler listesi

        Returns:
            SyncResult
        """
        if not self.config.is_configured:
            return SyncResult(
                success=False,
                message="Senkronizasyon yapılandırılmamış"
            )

        data = {
            "device_id": self.config.device_id,
            "last_sync_revision": self.config.last_sync_revision,
            "changes": changes or []
        }

        success, result = self._make_request(
            "/api/sync",
            method="POST",
            data=data
        )

        if not success:
            return SyncResult(success=False, message=result)

        if not result.get('success'):
            return SyncResult(
                success=False,
                message=result.get('message', 'Senkronizasyon başarısız'),
                errors=result.get('errors', [])
            )

        # Başarılı - revision'ı güncelle
        new_revision = result.get('new_revision', self.config.last_sync_revision)
        self.config.last_sync_revision = new_revision
        self.config.last_sync_time = datetime.now().isoformat()
        save_sync_config(self.config)

        incoming_changes = result.get('changes', [])

        return SyncResult(
            success=True,
            message=result.get('message', 'Senkronizasyon tamamlandı'),
            new_revision=new_revision,
            changes_sent=len(changes) if changes else 0,
            changes_received=len(incoming_changes),
            incoming_changes=incoming_changes,
            errors=result.get('errors', [])
        )

    def get_sync_status(self) -> Tuple[bool, Dict[str, Any]]:
        """Sunucudaki sync durumunu al."""
        success, result = self._make_request("/api/sync/status")

        if success:
            return True, result
        return False, {"error": result}

    def logout(self) -> bool:
        """Çıkış yap - token'ı temizle."""
        self.config.auth_token = ""
        self.config.user_uuid = ""
        self.config.username = ""
        self.config.role = ""
        save_sync_config(self.config)
        return True


def perform_full_sync() -> SyncResult:
    """
    Tam senkronizasyon yap.

    1. Outbox'taki değişiklikleri al
    2. Sunucuya gönder
    3. Gelen değişiklikleri işle
    4. Outbox'ı temizle
    """
    from sync.outbox import get_pending_changes, mark_changes_synced
    from sync.merger import apply_incoming_changes

    client = SyncClient()

    if not client.config.is_configured:
        return SyncResult(
            success=False,
            message="Senkronizasyon yapılandırılmamış. Lütfen önce sunucu ayarlarını yapın."
        )

    # 1. Gönderilecek değişiklikleri al
    pending_changes = get_pending_changes()
    logger.info(f"Gönderilecek değişiklik sayısı: {len(pending_changes)}")

    # 2. Sync yap
    result = client.sync(pending_changes)

    if not result.success:
        return result

    # 3. Gelen değişiklikleri uygula
    applied_count = 0
    if result.incoming_changes:
        logger.info(f"Gelen değişiklik sayısı: {len(result.incoming_changes)}")
        try:
            stats = apply_incoming_changes(result.incoming_changes)
            applied_count = stats.get('inserted', 0) + stats.get('updated', 0)
            logger.info(f"Uygulanan değişiklikler: {stats}")

            # Mesajı güncelle
            result = SyncResult(
                success=True,
                message=f"Senkronizasyon tamamlandı. {applied_count} kayıt güncellendi.",
                new_revision=result.new_revision,
                changes_sent=result.changes_sent,
                changes_received=applied_count,
                incoming_changes=result.incoming_changes,
                errors=result.errors
            )
        except Exception as e:
            logger.exception("Gelen değişiklikler uygulanırken hata")
            return SyncResult(
                success=False,
                message=f"Değişiklikler uygulanırken hata: {str(e)}",
                new_revision=result.new_revision,
                changes_sent=result.changes_sent,
                changes_received=0
            )

    # 4. Gönderilen değişiklikleri işaretle
    if pending_changes:
        try:
            change_ids = [c.get('id') for c in pending_changes if c.get('id')]
            mark_changes_synced(change_ids)
        except Exception as e:
            logger.exception("Outbox temizlenirken hata")

    return result
