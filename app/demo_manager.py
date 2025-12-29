# -*- coding: utf-8 -*-
"""
TakibiEsasi Demo Modu Yöneticisi

14 günlük ücretsiz deneme süresi yönetimi.
Demo süresinde girilen veriler tam sürüme geçişte korunur.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import os


class DemoManager:
    """Demo modu yönetim sınıfı"""

    DEMO_DURATION_DAYS = 14

    def __init__(self, db_path: str = None):
        """
        Demo yöneticisini başlat.

        Args:
            db_path: Veritabanı dosya yolu. None ise varsayılan kullanılır.
        """
        if db_path is None:
            # Varsayılan veritabanı yolu
            if os.name == 'nt':  # Windows
                base_dir = Path(os.environ.get('LOCALAPPDATA', '')) / 'TakibiEsasi'
            else:  # macOS / Linux
                base_dir = Path.home() / '.takibiesasi'
            db_path = str(base_dir / 'data.db')

        self.db_path = db_path
        self._init_demo_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_demo_table(self) -> None:
        """Demo tablosunu oluştur (yoksa)"""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS demo_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    demo_start_date TEXT NOT NULL,
                    demo_end_date TEXT NOT NULL,
                    is_demo_active INTEGER DEFAULT 1,
                    license_key TEXT,
                    activated_at TEXT,
                    machine_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"Demo tablosu oluşturma hatası: {e}")
        finally:
            conn.close()

    def start_demo(self, email: str, machine_id: str = None) -> Dict[str, Any]:
        """
        Demo süresini başlat.

        Args:
            email: Kullanıcı e-posta adresi
            machine_id: Makine kimliği (opsiyonel)

        Returns:
            dict: Başarı durumu ve demo bilgileri
        """
        start_date = datetime.now()
        end_date = start_date + timedelta(days=self.DEMO_DURATION_DAYS)

        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Zaten demo var mı kontrol et
            cur.execute("SELECT * FROM demo_info WHERE email = ?", (email,))
            existing = cur.fetchone()

            if existing:
                # Aynı e-posta ile tekrar demo başlatılamaz
                conn.close()
                return {
                    "success": False,
                    "error": "Bu e-posta adresi ile daha önce demo başlatılmış.",
                    "error_code": "EMAIL_EXISTS"
                }

            # Makine ID ile kontrol (aynı makinede farklı e-posta)
            if machine_id:
                cur.execute("SELECT * FROM demo_info WHERE machine_id = ?", (machine_id,))
                existing_machine = cur.fetchone()
                if existing_machine:
                    conn.close()
                    return {
                        "success": False,
                        "error": "Bu bilgisayarda daha önce demo başlatılmış.",
                        "error_code": "MACHINE_EXISTS"
                    }

            # Yeni demo kaydı oluştur
            cur.execute("""
                INSERT INTO demo_info (email, demo_start_date, demo_end_date, machine_id, is_demo_active)
                VALUES (?, ?, ?, ?, 1)
            """, (
                email,
                start_date.strftime("%Y-%m-%d %H:%M:%S"),
                end_date.strftime("%Y-%m-%d %H:%M:%S"),
                machine_id
            ))

            conn.commit()

            return {
                "success": True,
                "email": email,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days_remaining": self.DEMO_DURATION_DAYS,
                "message": f"Demo başarıyla başlatıldı! {self.DEMO_DURATION_DAYS} gün boyunca tüm özellikleri kullanabilirsiniz."
            }

        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": f"Demo başlatma hatası: {str(e)}",
                "error_code": "DB_ERROR"
            }
        finally:
            conn.close()

    def get_demo_status(self) -> Dict[str, Any]:
        """
        Mevcut demo durumunu kontrol et.

        Returns:
            dict: Demo durumu bilgileri
                - status: "no_demo" | "demo_active" | "expired" | "licensed"
                - days_remaining: Kalan gün sayısı (demo_active ise)
                - email: Kayıtlı e-posta
                - end_date: Bitiş tarihi
        """
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT * FROM demo_info ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()

            if not row:
                return {
                    "status": "no_demo",
                    "needs_registration": True,
                    "message": "Demo kaydı bulunamadı. Lütfen e-posta adresinizle kayıt olun."
                }

            email = row["email"]
            end_date_str = row["demo_end_date"]
            license_key = row["license_key"]

            # Tam lisans var mı?
            if license_key:
                return {
                    "status": "licensed",
                    "email": email,
                    "license_key": license_key,
                    "activated_at": row["activated_at"],
                    "message": "Lisanslı sürüm aktif."
                }

            # Demo süresi kontrolü
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

            now = datetime.now()

            if now > end_date:
                return {
                    "status": "expired",
                    "email": email,
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "expired_days_ago": (now - end_date).days,
                    "message": "Demo süreniz dolmuştur. Verileriniz güvende, satın alarak devam edebilirsiniz."
                }

            # Demo aktif
            days_remaining = (end_date - now).days
            hours_remaining = int((end_date - now).seconds / 3600)

            return {
                "status": "demo_active",
                "email": email,
                "days_remaining": days_remaining,
                "hours_remaining": hours_remaining,
                "end_date": end_date.strftime("%Y-%m-%d"),
                "start_date": row["demo_start_date"],
                "message": f"Demo aktif. {days_remaining} gün {hours_remaining} saat kaldı."
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Demo durumu kontrol edilemedi."
            }
        finally:
            conn.close()

    def activate_license(self, license_key: str) -> Dict[str, Any]:
        """
        Demo'yu tam lisansa çevir.

        Args:
            license_key: Lisans anahtarı

        Returns:
            dict: Aktivasyon sonucu
        """
        if not license_key or len(license_key) < 10:
            return {
                "success": False,
                "error": "Geçersiz lisans anahtarı formatı."
            }

        conn = self._get_connection()
        cur = conn.cursor()

        try:
            # Mevcut demo kaydını güncelle
            activated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("""
                UPDATE demo_info
                SET license_key = ?, activated_at = ?, is_demo_active = 0
                WHERE id = (SELECT id FROM demo_info ORDER BY id DESC LIMIT 1)
            """, (license_key, activated_at))

            if cur.rowcount == 0:
                # Demo kaydı yoksa yeni oluştur
                cur.execute("""
                    INSERT INTO demo_info (email, demo_start_date, demo_end_date, license_key, activated_at, is_demo_active)
                    VALUES (?, ?, ?, ?, ?, 0)
                """, (
                    "licensed_user@takibiesasi.com",
                    activated_at,
                    activated_at,
                    license_key,
                    activated_at
                ))

            conn.commit()

            return {
                "success": True,
                "license_key": license_key,
                "activated_at": activated_at,
                "message": "Lisans başarıyla aktifleştirildi! Tüm özelliklere sınırsız erişiminiz var."
            }

        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": f"Lisans aktivasyon hatası: {str(e)}"
            }
        finally:
            conn.close()

    def is_demo_mode(self) -> bool:
        """Demo modunda mı? (aktif veya süresi dolmuş)"""
        status = self.get_demo_status()
        return status.get("status") in ["demo_active", "expired", "no_demo"]

    def is_demo_active(self) -> bool:
        """Demo aktif ve kullanılabilir mi?"""
        status = self.get_demo_status()
        return status.get("status") == "demo_active"

    def is_licensed(self) -> bool:
        """Tam lisans var mı?"""
        status = self.get_demo_status()
        return status.get("status") == "licensed"

    def is_expired(self) -> bool:
        """Demo süresi dolmuş mu?"""
        status = self.get_demo_status()
        return status.get("status") == "expired"

    def needs_registration(self) -> bool:
        """Demo kaydı gerekiyor mu?"""
        status = self.get_demo_status()
        return status.get("status") == "no_demo"

    def get_days_remaining(self) -> int:
        """Kalan gün sayısı"""
        status = self.get_demo_status()
        return status.get("days_remaining", 0)

    def get_demo_email(self) -> Optional[str]:
        """Kayıtlı demo e-postası"""
        status = self.get_demo_status()
        return status.get("email")

    def extend_demo(self, extra_days: int = 7) -> Dict[str, Any]:
        """
        Demo süresini uzat (admin fonksiyonu).

        Args:
            extra_days: Eklenecek gün sayısı

        Returns:
            dict: Uzatma sonucu
        """
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT demo_end_date FROM demo_info ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()

            if not row:
                return {"success": False, "error": "Demo kaydı bulunamadı."}

            try:
                current_end = datetime.strptime(row["demo_end_date"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_end = datetime.strptime(row["demo_end_date"], "%Y-%m-%d")

            # Eğer süre dolmuşsa bugünden itibaren uzat
            if current_end < datetime.now():
                new_end = datetime.now() + timedelta(days=extra_days)
            else:
                new_end = current_end + timedelta(days=extra_days)

            cur.execute("""
                UPDATE demo_info
                SET demo_end_date = ?, is_demo_active = 1
                WHERE id = (SELECT id FROM demo_info ORDER BY id DESC LIMIT 1)
            """, (new_end.strftime("%Y-%m-%d %H:%M:%S"),))

            conn.commit()

            return {
                "success": True,
                "new_end_date": new_end.strftime("%Y-%m-%d"),
                "message": f"Demo süresi {extra_days} gün uzatıldı."
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            conn.close()


# Singleton instance
_demo_manager_instance: Optional[DemoManager] = None


def get_demo_manager(db_path: str = None) -> DemoManager:
    """
    DemoManager singleton instance al.

    Args:
        db_path: Veritabanı yolu (ilk çağrıda gerekli)

    Returns:
        DemoManager instance
    """
    global _demo_manager_instance

    if _demo_manager_instance is None:
        _demo_manager_instance = DemoManager(db_path)

    return _demo_manager_instance
