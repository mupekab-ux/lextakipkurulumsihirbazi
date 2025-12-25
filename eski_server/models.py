# -*- coding: utf-8 -*-
"""
LexTakip Sunucu Veritabanı Modelleri

Tüm tablolar:
- uuid: Benzersiz tanımlayıcı (PRIMARY KEY)
- firm_id: Firma ayrımı için
- revision: Senkronizasyon için versiyon numarası
- is_deleted: Soft delete için
- created_at, updated_at: Zaman damgaları
"""

import uuid as uuid_lib
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Index, BigInteger, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


def generate_uuid():
    """Yeni UUID oluştur."""
    return str(uuid_lib.uuid4())


class BaseMixin:
    """Tüm tablolar için ortak alanlar."""

    uuid = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    firm_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    revision = Column(BigInteger, nullable=False, default=0, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    device_id = Column(String(100), nullable=True)  # Hangi cihazdan geldi


# =============================================================================
# FİRMA
# =============================================================================

class Firm(Base):
    """Firma/Ofis tablosu - multi-tenant için."""

    __tablename__ = "firms"

    uuid = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)  # Kısa kod (ör: "HUKUKOFISI1")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    settings = Column(JSON, nullable=True)  # Firma özel ayarları


# =============================================================================
# KULLANICI
# =============================================================================

class User(Base, BaseMixin):
    """Kullanıcılar tablosu."""

    __tablename__ = "users"

    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="avukat")
    is_active = Column(Boolean, nullable=False, default=True)
    email = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint('firm_id', 'username', name='uq_user_firm_username'),
        Index('ix_users_firm_username', 'firm_id', 'username'),
    )


class Permission(Base, BaseMixin):
    """Yetki tablosu."""

    __tablename__ = "permissions"

    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    allowed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint('firm_id', 'role', 'action', name='uq_permission_firm_role_action'),
    )


# =============================================================================
# DOSYA/DAVA
# =============================================================================

class Dosya(Base, BaseMixin):
    """Ana dosya/dava tablosu."""

    __tablename__ = "dosyalar"

    buro_takip_no = Column(Integer, nullable=True)
    dosya_esas_no = Column(String(100), nullable=True)
    muvekkil_adi = Column(String(255), nullable=True)
    muvekkil_rolu = Column(String(100), nullable=True)
    karsi_taraf = Column(String(255), nullable=True)
    dosya_konusu = Column(Text, nullable=True)
    mahkeme_adi = Column(String(255), nullable=True)
    dava_acilis_tarihi = Column(String(20), nullable=True)  # ISO format
    durusma_tarihi = Column(String(20), nullable=True)
    dava_durumu = Column(String(255), nullable=True)
    is_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)
    tekrar_dava_durumu_2 = Column(String(255), nullable=True)
    is_tarihi_2 = Column(String(20), nullable=True)
    aciklama_2 = Column(Text, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index('ix_dosyalar_firm_buro', 'firm_id', 'buro_takip_no'),
        Index('ix_dosyalar_firm_esas', 'firm_id', 'dosya_esas_no'),
        Index('ix_dosyalar_firm_muvekkil', 'firm_id', 'muvekkil_adi'),
    )


class DosyaAtama(Base, BaseMixin):
    """Dosya-Kullanıcı atamaları."""

    __tablename__ = "dosya_atamalar"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=False)
    user_uuid = Column(UUID(as_uuid=False), nullable=False)

    __table_args__ = (
        UniqueConstraint('firm_id', 'dosya_uuid', 'user_uuid', name='uq_dosya_atama'),
        Index('ix_dosya_atama_dosya', 'firm_id', 'dosya_uuid'),
        Index('ix_dosya_atama_user', 'firm_id', 'user_uuid'),
    )


class DosyaTimeline(Base, BaseMixin):
    """Dosya değişiklik geçmişi."""

    __tablename__ = "dosya_timeline"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    user = Column(String(100), nullable=True)
    type = Column(String(50), nullable=True)
    title = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_dosya_timeline_dosya', 'firm_id', 'dosya_uuid'),
    )


# =============================================================================
# DURUM
# =============================================================================

class Status(Base, BaseMixin):
    """Dava durumları tablosu."""

    __tablename__ = "statuses"

    ad = Column(String(255), nullable=False)
    color_hex = Column(String(10), nullable=True)
    owner = Column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint('firm_id', 'ad', name='uq_status_firm_ad'),
    )


# =============================================================================
# FİNANS
# =============================================================================

class Finans(Base, BaseMixin):
    """Finans kayıtları - dosya bazlı."""

    __tablename__ = "finans"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=True, index=True)  # NULL olabilir (harici finans için)
    sozlesme_ucreti = Column(Float, nullable=True)
    sozlesme_yuzdesi = Column(Float, nullable=True)
    sozlesme_ucreti_cents = Column(BigInteger, nullable=True)
    tahsil_hedef_cents = Column(BigInteger, nullable=False, default=0)
    tahsil_edilen_cents = Column(BigInteger, nullable=False, default=0)
    masraf_toplam_cents = Column(BigInteger, nullable=False, default=0)
    masraf_tahsil_cents = Column(BigInteger, nullable=False, default=0)
    notlar = Column(Text, nullable=True)
    yuzde_is_sonu = Column(Boolean, nullable=False, default=False)
    son_guncelleme = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_finans_dosya', 'firm_id', 'dosya_uuid'),
    )


class OdemePlani(Base, BaseMixin):
    """Ödeme planları."""

    __tablename__ = "odeme_plani"

    finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    taksit_sayisi = Column(Integer, nullable=False, default=0)
    periyot = Column(String(20), nullable=False, default='Ay')
    vade_gunu = Column(Integer, nullable=False, default=7)
    baslangic_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_odeme_plani_finans', 'firm_id', 'finans_uuid'),
    )


class Taksit(Base, BaseMixin):
    """Taksitler."""

    __tablename__ = "taksitler"

    finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    vade_tarihi = Column(String(20), nullable=False)
    tutar_cents = Column(BigInteger, nullable=False, default=0)
    durum = Column(String(50), nullable=False, default='Ödenecek')
    odeme_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_taksit_finans', 'firm_id', 'finans_uuid'),
        Index('ix_taksit_vade', 'firm_id', 'vade_tarihi'),
    )


class OdemeKaydi(Base, BaseMixin):
    """Ödeme kayıtları."""

    __tablename__ = "odeme_kayitlari"

    finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    tarih = Column(String(20), nullable=False)
    tutar_cents = Column(BigInteger, nullable=False)
    yontem = Column(String(100), nullable=True)
    aciklama = Column(Text, nullable=True)
    taksit_uuid = Column(UUID(as_uuid=False), nullable=True)

    __table_args__ = (
        Index('ix_odeme_kaydi_finans', 'firm_id', 'finans_uuid'),
    )


class Masraf(Base, BaseMixin):
    """Masraf kayıtları."""

    __tablename__ = "masraflar"

    finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    kalem = Column(String(255), nullable=False)
    tutar_cents = Column(BigInteger, nullable=False)
    tarih = Column(String(20), nullable=True)
    tahsil_durumu = Column(String(50), nullable=False, default='Bekliyor')
    tahsil_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_masraf_finans', 'firm_id', 'finans_uuid'),
    )


class MuvekkilKasasi(Base, BaseMixin):
    """Müvekkil kasası kayıtları."""

    __tablename__ = "muvekkil_kasasi"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    tarih = Column(String(20), nullable=False)
    tutar_kurus = Column(BigInteger, nullable=False)
    islem_turu = Column(String(50), nullable=False)
    aciklama = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_muvekkil_kasasi_dosya', 'firm_id', 'dosya_uuid'),
    )


class FinansTimeline(Base, BaseMixin):
    """Finans işlem geçmişi."""

    __tablename__ = "finans_timeline"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    timestamp = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    user = Column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_finans_timeline_dosya', 'firm_id', 'dosya_uuid'),
    )


# =============================================================================
# HARİCİ FİNANS (Dosya bağımsız)
# =============================================================================

class FinansHarici(Base, BaseMixin):
    """Harici finans kayıtları - dosya bağımsız."""

    __tablename__ = "finans_harici"

    harici_bn = Column(String(100), nullable=True)
    harici_muvekkil = Column(String(255), nullable=True)
    harici_esas_no = Column(String(100), nullable=True)
    sabit_ucret_cents = Column(BigInteger, nullable=False, default=0)
    yuzde_orani = Column(Float, nullable=True, default=0)
    tahsil_edilen_cents = Column(BigInteger, nullable=False, default=0)
    masraf_toplam_cents = Column(BigInteger, nullable=False, default=0)
    masraf_tahsil_cents = Column(BigInteger, nullable=False, default=0)
    tahsil_hedef_cents = Column(BigInteger, nullable=False, default=0)
    yuzde_is_sonu = Column(Boolean, nullable=False, default=False)
    notlar = Column(Text, nullable=True)


class OdemePlaniHarici(Base, BaseMixin):
    """Harici finans ödeme planları."""

    __tablename__ = "odeme_plani_harici"

    harici_finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    vade_tarihi = Column(String(20), nullable=True)
    tutar_cents = Column(BigInteger, nullable=False, default=0)
    durum = Column(String(50), nullable=False, default='Ödenecek')
    sira = Column(Integer, nullable=True)
    odeme_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)


class OdemelerHarici(Base, BaseMixin):
    """Harici finans ödemeleri."""

    __tablename__ = "odemeler_harici"

    harici_finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    tarih = Column(String(20), nullable=True)
    tutar_cents = Column(BigInteger, nullable=False, default=0)
    tahsil_durumu = Column(String(50), nullable=True, default='Bekliyor')
    tahsil_tarihi = Column(String(20), nullable=True)
    yontem = Column(String(100), nullable=True)
    aciklama = Column(Text, nullable=True)
    plan_taksit_uuid = Column(UUID(as_uuid=False), nullable=True)


class MasraflarHarici(Base, BaseMixin):
    """Harici finans masrafları."""

    __tablename__ = "masraflar_harici"

    harici_finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    tarih = Column(String(20), nullable=True)
    kalem = Column(String(255), nullable=True)
    tutar_cents = Column(BigInteger, nullable=True)
    tahsil_cents = Column(BigInteger, nullable=True)
    tahsil_durumu = Column(String(50), nullable=True, default='Bekliyor')
    tahsil_tarihi = Column(String(20), nullable=True)
    aciklama = Column(Text, nullable=True)


class HariciMuvekkilKasasi(Base, BaseMixin):
    """Harici finans müvekkil kasası."""

    __tablename__ = "harici_muvekkil_kasasi"

    harici_finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    tarih = Column(String(20), nullable=False)
    tutar_kurus = Column(BigInteger, nullable=False)
    islem_turu = Column(String(50), nullable=False)
    aciklama = Column(Text, nullable=True)


class HariciFinansTimeline(Base, BaseMixin):
    """Harici finans işlem geçmişi."""

    __tablename__ = "harici_finans_timeline"

    harici_finans_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    timestamp = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    user = Column(String(100), nullable=True)


# =============================================================================
# TEBLİGAT
# =============================================================================

class Tebligat(Base, BaseMixin):
    """Tebligat kayıtları."""

    __tablename__ = "tebligatlar"

    dosya_no = Column(String(100), nullable=True)
    kurum = Column(String(255), nullable=True)
    geldigi_tarih = Column(String(20), nullable=True)
    teblig_tarihi = Column(String(20), nullable=True)
    is_son_gunu = Column(String(20), nullable=True)
    icerik = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_tebligat_tarih', 'firm_id', 'is_son_gunu'),
        Index('ix_tebligat_dosya', 'firm_id', 'dosya_no'),
    )


# =============================================================================
# ARABULUCULUK
# =============================================================================

class Arabuluculuk(Base, BaseMixin):
    """Arabuluculuk kayıtları."""

    __tablename__ = "arabuluculuk"

    davaci = Column(String(255), nullable=True)
    davali = Column(String(255), nullable=True)
    arb_adi = Column(String(255), nullable=True)
    arb_tel = Column(String(50), nullable=True)
    toplanti_tarihi = Column(String(20), nullable=True)
    toplanti_saati = Column(String(10), nullable=True)
    konu = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_arabuluculuk_tarih', 'firm_id', 'toplanti_tarihi'),
    )


# =============================================================================
# GÖREVLER
# =============================================================================

class Gorev(Base, BaseMixin):
    """Görevler/Yapılacaklar tablosu."""

    __tablename__ = "gorevler"

    tarih = Column(String(20), nullable=True)
    konu = Column(String(500), nullable=False)
    aciklama = Column(Text, nullable=True)
    atanan_kullanicilar = Column(Text, nullable=True)  # JSON veya comma-separated
    kaynak_turu = Column(String(50), nullable=False, default='MANUEL')
    olusturan_kullanici = Column(String(100), nullable=True)
    olusturma_zamani = Column(String(30), nullable=False)
    tamamlandi = Column(Boolean, nullable=False, default=False)
    tamamlanma_zamani = Column(String(30), nullable=True)
    dosya_uuid = Column(UUID(as_uuid=False), nullable=True)
    gorev_turu = Column(String(50), nullable=True)

    __table_args__ = (
        Index('ix_gorev_tarih', 'firm_id', 'tarih'),
        Index('ix_gorev_dosya', 'firm_id', 'dosya_uuid'),
    )


# =============================================================================
# EKLER (ATTACHMENTS)
# =============================================================================

class Attachment(Base, BaseMixin):
    """Dosya ekleri metadata."""

    __tablename__ = "attachments"

    dosya_uuid = Column(UUID(as_uuid=False), nullable=False, index=True)
    original_name = Column(String(500), nullable=True)
    stored_path = Column(String(1000), nullable=True)
    mime = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA256 hash
    added_at = Column(String(30), nullable=True)

    __table_args__ = (
        Index('ix_attachment_dosya', 'firm_id', 'dosya_uuid'),
    )


# =============================================================================
# ÖZEL SEKMELER
# =============================================================================

class CustomTab(Base, BaseMixin):
    """Özel sekmeler."""

    __tablename__ = "custom_tabs"

    name = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint('firm_id', 'name', name='uq_custom_tab_name'),
    )


class CustomTabDosya(Base, BaseMixin):
    """Özel sekme-dosya ilişkileri."""

    __tablename__ = "custom_tabs_dosyalar"

    custom_tab_uuid = Column(UUID(as_uuid=False), nullable=False)
    dosya_uuid = Column(UUID(as_uuid=False), nullable=False)

    __table_args__ = (
        UniqueConstraint('firm_id', 'custom_tab_uuid', 'dosya_uuid', name='uq_custom_tab_dosya'),
    )


# =============================================================================
# AYARLAR
# =============================================================================

class Ayar(Base, BaseMixin):
    """Uygulama ayarları."""

    __tablename__ = "ayarlar"

    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('firm_id', 'key', name='uq_ayar_key'),
    )


# =============================================================================
# SENKRONİZASYON
# =============================================================================

class SyncLog(Base):
    """Senkronizasyon logları - hangi cihaz ne zaman sync yaptı."""

    __tablename__ = "sync_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    firm_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    device_id = Column(String(100), nullable=False)
    user_uuid = Column(UUID(as_uuid=False), nullable=True)
    sync_type = Column(String(20), nullable=False)  # 'push', 'pull', 'full'
    records_sent = Column(Integer, nullable=False, default=0)
    records_received = Column(Integer, nullable=False, default=0)
    last_revision = Column(BigInteger, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default='in_progress')
    error_message = Column(Text, nullable=True)


class GlobalRevision(Base):
    """Global revision counter - her firma için."""

    __tablename__ = "global_revisions"

    firm_id = Column(UUID(as_uuid=False), primary_key=True)
    current_revision = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# TABLO LİSTESİ - Senkronizasyon için
# =============================================================================

SYNCABLE_TABLES = {
    'users': User,
    'permissions': Permission,
    'dosyalar': Dosya,
    'dosya_atamalar': DosyaAtama,
    'dosya_timeline': DosyaTimeline,
    'statuses': Status,
    'finans': Finans,
    'odeme_plani': OdemePlani,
    'taksitler': Taksit,
    'odeme_kayitlari': OdemeKaydi,
    'masraflar': Masraf,
    'muvekkil_kasasi': MuvekkilKasasi,
    'finans_timeline': FinansTimeline,
    'finans_harici': FinansHarici,
    'odeme_plani_harici': OdemePlaniHarici,
    'odemeler_harici': OdemelerHarici,
    'masraflar_harici': MasraflarHarici,
    'harici_muvekkil_kasasi': HariciMuvekkilKasasi,
    'harici_finans_timeline': HariciFinansTimeline,
    'tebligatlar': Tebligat,
    'arabuluculuk': Arabuluculuk,
    'gorevler': Gorev,
    'attachments': Attachment,
    'custom_tabs': CustomTab,
    'custom_tabs_dosyalar': CustomTabDosya,
    'ayarlar': Ayar,
}
