# -*- coding: utf-8 -*-
"""
Sync Server Database Models
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime,
    ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


def generate_uuid():
    return uuid.uuid4()


class Firm(Base):
    __tablename__ = "firms"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    firm_key = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    uuid = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    firm_id = Column(PG_UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('firm_id', 'username', name='unique_username_per_firm'),
    )


class Device(Base):
    __tablename__ = "devices"

    uuid = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    firm_id = Column(PG_UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True)
    device_id = Column(String(255), nullable=False)
    device_name = Column(String(255), nullable=True)
    device_info = Column(JSON, nullable=True)
    is_approved = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('firm_id', 'device_id', name='unique_device_per_firm'),
    )


class JoinCode(Base):
    __tablename__ = "join_codes"

    uuid = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    firm_id = Column(PG_UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False)
    max_uses = Column(Integer, default=10)
    use_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(PG_UUID(as_uuid=True), nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    uuid = Column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.uuid"), nullable=False, index=True)
    device_id = Column(String(255), nullable=True)  # String, not UUID
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    revoked = Column(Boolean, default=False)


class SyncRecord(Base):
    __tablename__ = "sync_records"

    uuid = Column(PG_UUID(as_uuid=True), primary_key=True)
    firm_id = Column(PG_UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False, index=True)
    table_name = Column(String(50), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    data_encrypted = Column(Text, nullable=True)
    buro_takip_no = Column(Integer, nullable=True, index=True)
    revision = Column(Integer, default=1, nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    server_created_at = Column(DateTime, server_default=func.now())
    server_updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by_device = Column(String(255), nullable=True)  # String, not UUID
    updated_by_device = Column(String(255), nullable=True)  # String, not UUID

    __table_args__ = (
        Index('idx_sync_records_firm_table', 'firm_id', 'table_name'),
        Index('idx_sync_records_firm_updated', 'firm_id', 'updated_at'),
        Index('idx_sync_records_firm_revision', 'firm_id', 'revision'),
    )


class GlobalRevision(Base):
    __tablename__ = "global_revisions"

    firm_id = Column(PG_UUID(as_uuid=True), ForeignKey("firms.id"), primary_key=True)
    current_revision = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firm_id = Column(PG_UUID(as_uuid=True), index=True)
    device_id = Column(String(255), nullable=True)  # String, not UUID
    action = Column(String(50))
    record_uuid = Column(PG_UUID(as_uuid=True), nullable=True)
    table_name = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


SYNCED_TABLES = [
    'dosyalar', 'finans', 'odeme_plani', 'taksitler', 'odeme_kayitlari',
    'masraflar', 'muvekkil_kasasi', 'tebligatlar', 'arabuluculuk', 'gorevler',
    'users', 'permissions', 'dosya_atamalar', 'attachments', 'custom_tabs',
    'custom_tabs_dosyalar', 'dosya_timeline', 'finans_timeline', 'statuses',
]
