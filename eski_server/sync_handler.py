# -*- coding: utf-8 -*-
"""
Senkronizasyon İşleyicisi

Bu modül, istemciden gelen değişiklikleri işler ve
istemciye gönderilecek değişiklikleri hazırlar.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import (
    SYNCABLE_TABLES, GlobalRevision, SyncLog,
    User, Permission, Dosya, DosyaAtama, DosyaTimeline,
    Status, Finans, OdemePlani, Taksit, OdemeKaydi, Masraf,
    MuvekkilKasasi, FinansTimeline, FinansHarici, OdemePlaniHarici,
    OdemelerHarici, MasraflarHarici, HariciMuvekkilKasasi,
    HariciFinansTimeline, Tebligat, Arabuluculuk, Gorev,
    Attachment, CustomTab, CustomTabDosya, Ayar
)
from schemas import SyncChange, SyncRequest, SyncResponse, TokenData

logger = logging.getLogger(__name__)


def get_next_revision(db: Session, firm_id: str) -> int:
    """Firma için bir sonraki revision numarasını al ve artır."""

    global_rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).with_for_update().first()

    if global_rev is None:
        global_rev = GlobalRevision(firm_id=firm_id, current_revision=0)
        db.add(global_rev)

    global_rev.current_revision += 1
    global_rev.updated_at = datetime.utcnow()
    db.flush()

    return global_rev.current_revision


def get_current_revision(db: Session, firm_id: str) -> int:
    """Firma için mevcut revision numarasını al."""

    global_rev = db.query(GlobalRevision).filter(
        GlobalRevision.firm_id == firm_id
    ).first()

    return global_rev.current_revision if global_rev else 0


def process_incoming_changes(
    db: Session,
    firm_id: str,
    device_id: str,
    user_uuid: str,
    changes: List[SyncChange]
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    İstemciden gelen değişiklikleri işle.

    Returns:
        (işlenen_kayıt_sayısı, hatalar_listesi)
    """

    processed = 0
    errors = []

    for change in changes:
        try:
            table_name = change.table
            operation = change.op
            record_uuid = change.uuid
            data = change.data

            if table_name not in SYNCABLE_TABLES:
                errors.append({
                    "uuid": record_uuid,
                    "table": table_name,
                    "error": f"Bilinmeyen tablo: {table_name}"
                })
                continue

            model_class = SYNCABLE_TABLES[table_name]

            # Revision al
            new_revision = get_next_revision(db, firm_id)

            if operation == 'insert':
                # Yeni kayıt ekle
                record = model_class(
                    uuid=record_uuid,
                    firm_id=firm_id,
                    revision=new_revision,
                    device_id=device_id,
                    created_by=user_uuid,
                    updated_by=user_uuid,
                    **_filter_data_for_model(data, model_class)
                )
                db.add(record)
                processed += 1

            elif operation == 'update':
                # Mevcut kaydı güncelle
                record = db.query(model_class).filter(
                    model_class.uuid == record_uuid,
                    model_class.firm_id == firm_id
                ).first()

                if record:
                    # Last-write-wins: Gelen veriyi uygula
                    filtered_data = _filter_data_for_model(data, model_class)
                    for key, value in filtered_data.items():
                        setattr(record, key, value)
                    record.revision = new_revision
                    record.updated_at = datetime.utcnow()
                    record.updated_by = user_uuid
                    record.device_id = device_id
                    processed += 1
                else:
                    # Kayıt yoksa insert yap (conflict resolution)
                    record = model_class(
                        uuid=record_uuid,
                        firm_id=firm_id,
                        revision=new_revision,
                        device_id=device_id,
                        created_by=user_uuid,
                        updated_by=user_uuid,
                        **_filter_data_for_model(data, model_class)
                    )
                    db.add(record)
                    processed += 1

            elif operation == 'delete':
                # Soft delete
                record = db.query(model_class).filter(
                    model_class.uuid == record_uuid,
                    model_class.firm_id == firm_id
                ).first()

                if record:
                    record.is_deleted = True
                    record.revision = new_revision
                    record.updated_at = datetime.utcnow()
                    record.updated_by = user_uuid
                    record.device_id = device_id
                    processed += 1

        except Exception as e:
            logger.exception(f"Değişiklik işlenirken hata: {change}")
            errors.append({
                "uuid": change.uuid,
                "table": change.table,
                "error": str(e)
            })

    return processed, errors


def get_outgoing_changes(
    db: Session,
    firm_id: str,
    last_sync_revision: int,
    device_id: str
) -> List[SyncChange]:
    """
    İstemciye gönderilecek değişiklikleri al.

    last_sync_revision'dan sonra olan ve bu cihazdan gelmeyen
    tüm değişiklikleri döndürür.
    """

    changes = []

    for table_name, model_class in SYNCABLE_TABLES.items():
        try:
            # Bu firmaya ait, belirtilen revision'dan sonra olan,
            # farklı cihazdan gelen değişiklikleri al
            records = db.query(model_class).filter(
                model_class.firm_id == firm_id,
                model_class.revision > last_sync_revision,
                # Kendi değişikliklerini geri gönderme
                # (aynı cihazdan gelenleri hariç tut)
                # model_class.device_id != device_id  # İsteğe bağlı
            ).all()

            for record in records:
                # Kayıt verilerini dict'e çevir
                data = _model_to_dict(record, table_name)

                # Operation belirleme
                if record.is_deleted:
                    op = 'delete'
                else:
                    # created_at ve updated_at karşılaştırarak karar ver
                    # Basit yaklaşım: revision > last_sync ise update
                    op = 'update'

                changes.append(SyncChange(
                    table=table_name,
                    op=op,
                    uuid=record.uuid,
                    data=data,
                    revision=record.revision,
                    updated_at=record.updated_at.isoformat() if record.updated_at else None
                ))

        except Exception as e:
            logger.exception(f"Tablo okunurken hata: {table_name}")
            continue

    return changes


def _filter_data_for_model(data: Dict[str, Any], model_class) -> Dict[str, Any]:
    """
    Gelen veriyi model'in kabul ettiği alanlarla filtrele.
    """

    # Model'in sütunlarını al
    columns = {c.name for c in model_class.__table__.columns}

    # Sistem alanlarını hariç tut (bunlar otomatik yönetilir)
    system_fields = {
        'uuid', 'firm_id', 'revision', 'is_deleted',
        'created_at', 'updated_at', 'created_by', 'updated_by', 'device_id'
    }

    filtered = {}
    for key, value in data.items():
        if key in columns and key not in system_fields:
            filtered[key] = value

    return filtered


def _model_to_dict(record, table_name: str) -> Dict[str, Any]:
    """
    SQLAlchemy model'ini dictionary'e çevir.
    """

    # Sistem alanlarını hariç tut
    system_fields = {
        'uuid', 'firm_id', 'revision', 'is_deleted',
        'created_at', 'updated_at', 'created_by', 'updated_by', 'device_id'
    }

    data = {}
    for column in record.__table__.columns:
        if column.name not in system_fields:
            value = getattr(record, column.name)
            # Datetime'ı string'e çevir
            if isinstance(value, datetime):
                value = value.isoformat()
            data[column.name] = value

    return data


def log_sync(
    db: Session,
    firm_id: str,
    device_id: str,
    user_uuid: str,
    sync_type: str,
    records_sent: int,
    records_received: int,
    last_revision: int,
    status: str,
    error_message: str = None
) -> SyncLog:
    """Senkronizasyon logla."""

    log = SyncLog(
        firm_id=firm_id,
        device_id=device_id,
        user_uuid=user_uuid,
        sync_type=sync_type,
        records_sent=records_sent,
        records_received=records_received,
        last_revision=last_revision,
        status=status,
        error_message=error_message,
        completed_at=datetime.utcnow() if status in ('success', 'error') else None
    )
    db.add(log)
    return log


def perform_sync(
    db: Session,
    token_data: TokenData,
    request: SyncRequest
) -> SyncResponse:
    """
    Ana senkronizasyon işlemi.

    1. İstemciden gelen değişiklikleri işle (push)
    2. İstemciye gönderilecek değişiklikleri al (pull)
    3. Sonuçları döndür
    """

    firm_id = token_data.firm_id
    user_uuid = token_data.user_uuid
    device_id = request.device_id

    try:
        # 1. Gelen değişiklikleri işle (varsa)
        processed = 0
        errors = []

        if request.changes:
            processed, errors = process_incoming_changes(
                db=db,
                firm_id=firm_id,
                device_id=device_id,
                user_uuid=user_uuid,
                changes=request.changes
            )

        # 2. Gönderilecek değişiklikleri al
        outgoing_changes = get_outgoing_changes(
            db=db,
            firm_id=firm_id,
            last_sync_revision=request.last_sync_revision,
            device_id=device_id
        )

        # 3. Mevcut revision'ı al
        current_revision = get_current_revision(db, firm_id)

        # 4. Commit
        db.commit()

        # 5. Log
        log_sync(
            db=db,
            firm_id=firm_id,
            device_id=device_id,
            user_uuid=user_uuid,
            sync_type='full',
            records_sent=processed,
            records_received=len(outgoing_changes),
            last_revision=current_revision,
            status='success'
        )
        db.commit()

        return SyncResponse(
            success=True,
            new_revision=current_revision,
            changes=outgoing_changes,
            errors=errors,
            message=f"Senkronizasyon tamamlandı. Gönderilen: {processed}, Alınan: {len(outgoing_changes)}"
        )

    except Exception as e:
        db.rollback()
        logger.exception("Senkronizasyon hatası")

        # Hata logla
        try:
            log_sync(
                db=db,
                firm_id=firm_id,
                device_id=device_id,
                user_uuid=user_uuid,
                sync_type='full',
                records_sent=0,
                records_received=0,
                last_revision=request.last_sync_revision,
                status='error',
                error_message=str(e)
            )
            db.commit()
        except:
            pass

        return SyncResponse(
            success=False,
            new_revision=request.last_sync_revision,
            changes=[],
            errors=[{"error": str(e)}],
            message=f"Senkronizasyon hatası: {str(e)}"
        )
