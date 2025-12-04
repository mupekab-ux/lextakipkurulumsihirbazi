#!/usr/bin/env python3
"""Finans sözleşmesi alanlarını hızlıca güncelleyen smoke testi."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
APP_DIR = PROJECT_ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.db import initialize_database  # noqa: E402
from app.models import update_finans_contract  # noqa: E402
from app.utils import tl_to_cents  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finans sözleşme alanlarını güncelleyen basit doğrulama betiği."
    )
    parser.add_argument("--dosya-id", type=int, help="Hedef dosya kimliği")
    parser.add_argument("--finans-id", type=int, help="Mevcut finans kaydı kimliği")
    parser.add_argument(
        "--fixed",
        type=float,
        default=0.0,
        help="Sabit ücret (TL)",
    )
    parser.add_argument(
        "--percent",
        type=float,
        default=0.0,
        help="Yüzde oranı",
    )
    parser.add_argument(
        "--target",
        default="0",
        help="Hedef tahsilat (TL cinsinden, örn. 15000.75)",
    )
    parser.add_argument("--notes", help="Notlar", default=None)
    parser.add_argument(
        "--deferred",
        action="store_true",
        help="Yüzde tahsilatı iş sonuna ertelendi mi?",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    if args.dosya_id is None and args.finans_id is None:
        logging.error("'dosya-id' veya 'finans-id' parametrelerinden en az biri gerekli.")
        return 2

    initialize_database()

    success = update_finans_contract(
        args.dosya_id,
        finans_id=args.finans_id,
        sozlesme_ucreti=args.fixed,
        sozlesme_yuzdesi=args.percent,
        tahsil_hedef_cents=tl_to_cents(args.target),
        notlar=args.notes,
        yuzde_is_sonu=args.deferred,
    )

    if success:
        logging.info("Finans kaydı başarıyla güncellendi.")
        return 0

    logging.error("Finans kaydı bulunamadı; herhangi bir satır güncellenmedi.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
