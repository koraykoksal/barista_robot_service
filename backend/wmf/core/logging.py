"""
core/logging.py

Tutarlı konsol loglama.

order_utils.py bölündü:
  log / log_order_detail          → buraya
  describe_machine_errors /
  check_monitor_state             → core/machine_errors.py
  cleanup_signals                 → service/order_service.py
    (robot_mgr'a bağımlıydı; core katmanında servise bağımlılık olamaz)
"""

import json
from datetime import datetime
from typing import Any, Dict

from core import catalog
from core.config import (
    BARISTA_LABELS,
    DECAF_LABELS,
    MILK_LABELS,
    SIRUP_LABELS,
    SML_LABELS,
)


# ─────────────────────────────────────────────
# TEMEL LOG
# ─────────────────────────────────────────────

def log(job_id: str, phase: str, msg: str) -> None:
    """
    [job_id_kısa | faz] mesaj

    Sabit genişlikli faz alanı sayesinde uzun akış logları
    hizalı okunur.
    """
    short = job_id[:8] if job_id else "--------"
    print(f"[{short} | {phase:25s}] {msg}")


# ─────────────────────────────────────────────
# SİPARİŞ DETAY LOGU
# ─────────────────────────────────────────────

def log_order_detail(job_id: str, message: Dict[str, Any], client_ip: str = "?") -> None:
    """
    Frontend'den gelen sipariş parametrelerini okunabilir biçimde basar.

    Ham JSON'da a_iBarista="1" gibi değerler tek başına bir şey ifade
    etmiyor; etiket tablolarıyla insan diline çevriliyor.
    """
    sep = "─" * 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    btn_raw  = str(message.get("a_iBtnNbr", "?"))
    bev_name = catalog.name(btn_raw)

    def label(table: Dict[str, str], key: str) -> str:
        raw = str(message.get(key, "?"))
        return table.get(raw, raw)

    print(f"\n{sep}")
    print("  📥 YENİ SİPARİŞ")
    print(f"  Zaman      : {now}")
    print(f"  Client IP  : {client_ip}")
    print(f"  Job ID     : {job_id}")
    print(f"  Fonksiyon  : {message.get('function', '?')}")
    print(sep)
    print(f"  İçecek     : {bev_name}  (ButtonNumber={btn_raw})")
    print(f"  Yoğunluk   : {label(BARISTA_LABELS, 'a_iBarista')}")
    print(f"  Boyut      : {label(SML_LABELS,     'a_iSML')}")
    print(f"  Decaf      : {label(DECAF_LABELS,   'a_iDecaf')}")
    print(f"  Süt tipi   : {label(MILK_LABELS,    'a_iMilktype')}")
    print(f"  Şurup      : {label(SIRUP_LABELS,   'a_iSirupType')}")
    print(f"  Şurup boy  : {label(SML_LABELS,     'a_iSirupSML')}")

    portioner = str(message.get("a_iBeanPortioner", "0"))
    print(f"  Öğütücü    : {'Tarife göre' if portioner == '0' else f'Portioner {portioner}'}")
    print(f"  Bardak boy.: %{message.get('a_iCupSizeAdj', '100')}")
    print(f"  Ham mesaj  : {json.dumps(message, ensure_ascii=False)}")
    print(sep)
