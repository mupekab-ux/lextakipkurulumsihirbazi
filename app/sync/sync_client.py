# -*- coding: utf-8 -*-
"""
Sync HTTP Client

Raspberry Pi üzerindeki sync server ile iletişim kurar.
JWT authentication ve retry mekanizması içerir.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# HTTP client
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("Requests kütüphanesi yüklü değil. pip install requests")


class FirmMismatchError(Exception):
    """Yanlış büroya bağlanma hatası"""
    pass


class DeviceNotApprovedError(Exception):
    """Cihaz onaylanmamış hatası"""
    pass


class AuthenticationError(Exception):
    """Kimlik doğrulama hatası"""
    pass


class SyncClient:
    """
    Sync Server HTTP Client.

    Özellikler:
    - JWT token yönetimi (access + refresh)
    - Otomatik retry (network hataları için)
    - Firm ID doğrulama
    - SSL sertifika desteği (self-signed)
    """

    def __init__(self, config: 'SyncConfig'):
        """
        Args:
            config: SyncConfig instance
        """
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("Requests kütüphanesi gerekli. pip install requests")

        self.config = config
        self._session = self._create_session()
        self._token_expires_at: Optional[datetime] = None

    def _create_session(self) -> 'requests.Session':
        """Retry mekanizmalı session oluştur"""
        session = requests.Session()

        # Retry stratejisi
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Default headers
        session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Device-ID': self.config.device_id,
            'X-Firm-ID': self.config.firm_id,
        })

        return session

    def _get_url(self, endpoint: str) -> str:
        """Tam URL oluştur"""
        return urljoin(self.config.server_url, endpoint)

    def _ensure_authenticated(self):
        """Token'ın geçerli olduğundan emin ol"""
        if not self.config.access_token:
            raise AuthenticationError("Access token yok, önce login olun")

        # Token süresi dolmuşsa yenile
        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            self.refresh_token()

        self._session.headers['Authorization'] = f'Bearer {self.config.access_token}'

    def check_connection(self) -> bool:
        """
        Sunucu bağlantısını kontrol et.

        Returns:
            Bağlantı başarılıysa True
        """
        try:
            response = self._session.get(
                self._get_url('/api/health'),
                timeout=5,
                verify=False  # Self-signed cert için
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Bağlantı kontrolü başarısız: {e}")
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """
        Sunucu bilgilerini al.

        Returns:
            Server info dict (firm_id, version, etc.)
        """
        try:
            response = self._session.get(
                self._get_url('/api/sync/info'),
                timeout=10,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Sunucu bilgisi alınamadı: {e}")
            raise

    def validate_firm_connection(self) -> bool:
        """
        Firma bağlantısını doğrula.

        Yanlış ağa bağlanmayı önler.

        Returns:
            Doğrulama başarılıysa True

        Raises:
            FirmMismatchError: Firma ID eşleşmezse
        """
        server_info = self.get_server_info()
        server_firm_id = server_info.get('firm_id')

        if server_firm_id != self.config.firm_id:
            raise FirmMismatchError(
                f"Bu sunucu farklı bir büroya ait!\n\n"
                f"Sizin büro ID: {self.config.firm_id[:8]}...\n"
                f"Sunucu büro ID: {server_firm_id[:8] if server_firm_id else 'Bilinmiyor'}...\n\n"
                f"Lütfen doğru ağa bağlandığınızdan emin olun."
            )

        return True

    # ============================================================
    # AUTH ENDPOINTS
    # ============================================================

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Kullanıcı girişi.

        Args:
            username: Kullanıcı adı
            password: Şifre

        Returns:
            {access_token, refresh_token, user_info}
        """
        response = self._session.post(
            self._get_url('/api/auth/login'),
            json={
                'username': username,
                'password': password,
                'device_id': self.config.device_id,
            },
            timeout=15,
            verify=False
        )

        if response.status_code == 401:
            raise AuthenticationError("Kullanıcı adı veya şifre hatalı")
        elif response.status_code == 403:
            data = response.json()
            if data.get('reason') == 'device_not_approved':
                raise DeviceNotApprovedError("Bu cihaz henüz onaylanmamış")
            raise AuthenticationError(data.get('detail', 'Erişim reddedildi'))

        response.raise_for_status()
        data = response.json()

        # Token'ları kaydet
        self.config.access_token = data['access_token']
        self.config.refresh_token = data.get('refresh_token')

        # Token süresini hesapla (varsayılan 1 saat)
        expires_in = data.get('expires_in', 3600)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

        return data

    def refresh_token(self) -> bool:
        """
        Access token'ı yenile.

        Returns:
            Başarılıysa True
        """
        if not self.config.refresh_token:
            raise AuthenticationError("Refresh token yok")

        try:
            response = self._session.post(
                self._get_url('/api/auth/refresh'),
                json={'refresh_token': self.config.refresh_token},
                timeout=10,
                verify=False
            )

            if response.status_code == 401:
                # Refresh token da geçersiz, yeniden login gerekli
                raise AuthenticationError("Oturum süresi doldu, tekrar giriş yapın")

            response.raise_for_status()
            data = response.json()

            self.config.access_token = data['access_token']
            expires_in = data.get('expires_in', 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            return True

        except Exception as e:
            logger.error(f"Token yenileme hatası: {e}")
            raise

    def logout(self):
        """Çıkış yap"""
        try:
            self._ensure_authenticated()
            self._session.post(
                self._get_url('/api/auth/logout'),
                timeout=5,
                verify=False
            )
        except Exception:
            pass  # Logout hataları önemsiz
        finally:
            self.config.access_token = None
            self.config.refresh_token = None
            self._token_expires_at = None

    # ============================================================
    # SETUP ENDPOINTS
    # ============================================================

    def init_firm(self, firm_name: str, admin_username: str,
                  admin_password: str, admin_email: str = "") -> Dict[str, Any]:
        """
        Yeni büro oluştur.

        Args:
            firm_name: Büro adı
            admin_username: Yönetici kullanıcı adı
            admin_password: Yönetici şifresi
            admin_email: E-posta (opsiyonel)

        Returns:
            {firm_id, recovery_code, join_code, firm_key}
        """
        response = self._session.post(
            self._get_url('/api/setup/init'),
            json={
                'firm_name': firm_name,
                'admin_username': admin_username,
                'admin_password': admin_password,
                'admin_email': admin_email,
                'device_name': self.config.device_id,
            },
            timeout=30,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def join_firm(self, join_code: str, device_name: str,
                  device_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Mevcut büroya katıl.

        Args:
            join_code: Katılım kodu (BURO-XXXX-XXXX-XXXX)
            device_name: Cihaz adı
            device_info: Cihaz bilgileri

        Returns:
            {firm_id, device_id, requires_approval, firm_key?}
        """
        response = self._session.post(
            self._get_url('/api/setup/join'),
            json={
                'join_code': join_code,
                'device_name': device_name,
                'device_info': device_info or {},
            },
            timeout=15,
            verify=False
        )

        if response.status_code == 404:
            raise ValueError("Geçersiz veya süresi dolmuş katılım kodu")
        elif response.status_code == 403:
            raise ValueError("Bu katılım kodu kullanım limitine ulaşmış")

        response.raise_for_status()
        return response.json()

    def check_approval_status(self) -> Dict[str, Any]:
        """
        Cihaz onay durumunu kontrol et.

        Returns:
            {is_approved, firm_key?}
        """
        response = self._session.get(
            self._get_url(f'/api/setup/device/{self.config.device_id}/status'),
            timeout=10,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    # ============================================================
    # SYNC ENDPOINTS
    # ============================================================

    def push_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Değişiklikleri sunucuya gönder.

        Args:
            changes: Değişiklik listesi [{uuid, table, operation, data_encrypted}]

        Returns:
            {success, synced_count, conflicts: []}
        """
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url('/api/sync/push'),
            json={'changes': changes},
            timeout=60,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def pull_changes(self, since_revision: int = 0) -> Dict[str, Any]:
        """
        Sunucudan değişiklikleri çek.

        Args:
            since_revision: Bu revizyondan sonraki değişiklikleri al

        Returns:
            {changes: [...], latest_revision}
        """
        self._ensure_authenticated()

        response = self._session.get(
            self._get_url(f'/api/sync/pull?since_revision={since_revision}'),
            timeout=60,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def resolve_conflict(self, record_uuid: str, resolution: str,
                        winning_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Çakışmayı çöz.

        Args:
            record_uuid: Kayıt UUID'si
            resolution: Çözüm tipi ('local', 'remote', 'merged')
            winning_data: Kazanan veri

        Returns:
            {success}
        """
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url('/api/sync/resolve-conflict'),
            json={
                'record_uuid': record_uuid,
                'resolution': resolution,
                'winning_data': winning_data,
            },
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Senkronizasyon durumunu al.

        Returns:
            {is_connected, last_sync, pending_changes}
        """
        self._ensure_authenticated()

        response = self._session.get(
            self._get_url('/api/sync/status'),
            timeout=10,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    # ============================================================
    # ADMIN ENDPOINTS
    # ============================================================

    def get_devices(self) -> List[Dict[str, Any]]:
        """Cihaz listesini al"""
        self._ensure_authenticated()

        response = self._session.get(
            self._get_url('/api/admin/devices'),
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json().get('devices', [])

    def approve_device(self, device_id: str) -> Dict[str, Any]:
        """Cihazı onayla"""
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url(f'/api/admin/devices/{device_id}/approve'),
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def deactivate_device(self, device_id: str) -> Dict[str, Any]:
        """Cihazı deaktif et"""
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url(f'/api/admin/devices/{device_id}/deactivate'),
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def generate_join_code(self, max_uses: int = 10,
                          expires_hours: int = 24) -> Dict[str, Any]:
        """
        Yeni katılım kodu oluştur.

        Args:
            max_uses: Maksimum kullanım sayısı
            expires_hours: Geçerlilik süresi (saat)

        Returns:
            {code, expires_at}
        """
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url('/api/admin/join-code/generate'),
            json={
                'max_uses': max_uses,
                'expires_hours': expires_hours,
            },
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json()

    def get_users(self) -> List[Dict[str, Any]]:
        """Kullanıcı listesini al"""
        self._ensure_authenticated()

        response = self._session.get(
            self._get_url('/api/admin/users'),
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json().get('users', [])

    def create_user(self, username: str, password: str,
                   email: str = "", role: str = "avukat") -> Dict[str, Any]:
        """Yeni kullanıcı oluştur"""
        self._ensure_authenticated()

        response = self._session.post(
            self._get_url('/api/admin/users'),
            json={
                'username': username,
                'password': password,
                'email': email,
                'role': role,
            },
            timeout=15,
            verify=False
        )

        response.raise_for_status()
        return response.json()
