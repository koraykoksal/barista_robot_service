"""
order_utils.py

Sipariş akışında kullanılan yardımcı fonksiyonlar:
  - Loglama
  - Timer hesaplama
  - Hata açıklama
  - Monitor durum kontrolü
  - Sinyal temizleme
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from config import (
    BREW_TIMERS,
    BEVERAGE_NAMES,
    BARISTA_LABELS,
    SML_LABELS,
    DECAF_LABELS,
    MILK_LABELS,
    SIRUP_LABELS,
    MACHINE_ERROR_MESSAGES,
)


# ─────────────────────────────────────────────
# LOGLAMA
# ─────────────────────────────────────────────

def log(job_id: str, phase: str, msg: str) -> None:
    """Tutarlı console loglama: [job_id_kısa | phase] mesaj"""
    short = job_id[:8] if job_id else "--------"
    print(f"[{short} | {phase:25s}] {msg}")


def log_order_detail(job_id: str, message: Dict[str, Any], client_ip: str = "?") -> None:
    """Frontend'den gelen sipariş parametrelerini okunabilir biçimde loglar."""
    sep = "─" * 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    btn_raw  = str(message.get("a_iBtnNbr", "?"))
    btn_int  = int(btn_raw) if btn_raw.isdigit() else -1
    bev_name = BEVERAGE_NAMES.get(btn_int, f"Bilinmeyen (btn={btn_raw})")

    barista   = BARISTA_LABELS.get(str(message.get("a_iBarista",   "?")), str(message.get("a_iBarista",   "?")))
    sml       = SML_LABELS.get(    str(message.get("a_iSML",       "?")), str(message.get("a_iSML",       "?")))
    decaf     = DECAF_LABELS.get(  str(message.get("a_iDecaf",     "?")), str(message.get("a_iDecaf",     "?")))
    milk      = MILK_LABELS.get(   str(message.get("a_iMilktype",  "?")), str(message.get("a_iMilktype",  "?")))
    sirup     = SIRUP_LABELS.get(  str(message.get("a_iSirupType", "?")), str(message.get("a_iSirupType", "?")))
    sirup_sml = SML_LABELS.get(    str(message.get("a_iSirupSML",  "?")), str(message.get("a_iSirupSML",  "?")))
    portioner = message.get("a_iBeanPortioner", "0")
    cup_adj   = message.get("a_iCupSizeAdj", "100")
    func      = message.get("function", "?")

    print(f"\n{sep}")
    print(f"  📥 YENİ SİPARİŞ GELDİ")
    print(f"  Zaman      : {now}")
    print(f"  Client IP  : {client_ip}")
    print(f"  Job ID     : {job_id}")
    print(f"  Fonksiyon  : {func}")
    print(sep)
    print(f"  İçecek     : {bev_name}  (ButtonNumber={btn_raw})")
    print(f"  Yoğunluk   : {barista}")
    print(f"  Boyut      : {sml}")
    print(f"  Decaf      : {decaf}")
    print(f"  Süt tipi   : {milk}")
    print(f"  Şurup      : {sirup}")
    print(f"  Şurup boy  : {sirup_sml}")
    print(f"  Öğütücü    : {'Tarife göre' if str(portioner) == '0' else f'Portioner {portioner}'}")
    print(f"  Bardak boy.: %{cup_adj}")
    print(f"  Ham mesaj  : {json.dumps(message, ensure_ascii=False)}")
    print(sep)


# ─────────────────────────────────────────────
# TIMER
# ─────────────────────────────────────────────

def get_brew_delay(button_number) -> int:
    """
    ButtonNumber'a göre kahve hazırlanma bekleme süresini döner (saniye).
    BREW_TIMERS sözlüğünde tanımlı değilse 0 döner.
    """
    try:
        btn = int(button_number) if button_number is not None else None
    except (ValueError, TypeError):
        btn = None
    return BREW_TIMERS.get(btn, 0)


# ─────────────────────────────────────────────
# MAKİNE HATA AÇIKLAMASI
# ─────────────────────────────────────────────

def describe_machine_errors(error_codes: list) -> str:
    """Hata kodu listesini okunabilir Türkçe metne çevirir."""
    if not error_codes:
        return "Bilinmeyen makine hatası"
    parts = [
        MACHINE_ERROR_MESSAGES.get(int(code), f"Makine hatası (kod: {code})")
        for code in error_codes
    ]
    return " | ".join(parts)


# ─────────────────────────────────────────────
# MONITOR DURUM KONTROLÜ
# ─────────────────────────────────────────────

def check_monitor_state(state: dict, context: str = "") -> None:
    """
    MachineMonitor'ın tuttuğu anlık durumu kontrol eder.
    Hata, offline veya temizlik varsa Exception fırlatır.
    Sipariş akışı başlamadan ÖNCE çağrılır.
    """
    prefix = f"[{context}] " if context else ""

    if not state.get("online", False):
        raise Exception(f"{prefix}Kahve makinesi çevrimdışı.")

    # has_blocking_error: sadece sipariş engelleyen hatalar (non-blocking yoksayılır)
    if state.get("has_blocking_error") and state.get("blocking_errors"):
        msg = describe_machine_errors(state["blocking_errors"])
        raise Exception(f"{prefix}Makine hazır değil (blocking hata): {msg}")
    elif state.get("has_error") and state.get("errors"):
        # Non-blocking hatalar varsa logla ama sipariş başlatmaya izin ver
        non_blocking = [e for e in state.get("errors", []) if e not in state.get("blocking_errors", [])]
        if non_blocking:
            print(f"[check_monitor_state] ℹ️  Non-blocking hatalar mevcut (yoksayıldı): {non_blocking}")

    if state.get("cleaning"):
        notif = state["cleaning"]
        ctype = notif.get("type", "sistem temizliği") if isinstance(notif, dict) else "sistem temizliği"
        raise Exception(f"{prefix}Makine temizlik modunda: {ctype}")

    if state.get("rinsing"):
        notif = state["rinsing"]
        rtype = notif.get("type", "durulama") if isinstance(notif, dict) else "durulama"
        raise Exception(f"{prefix}Makine durulama modunda: {rtype}")


# ─────────────────────────────────────────────
# DO SİNYAL TEMİZLEME
# ─────────────────────────────────────────────

async def cleanup_signals(job_id: str = "") -> None:
    """
    Hata / timeout sonrası DO0 ve DO2 sinyallerini LOW'a çeker.
    services modülünden robot_mgr alınır (circular import önlemi için lazy import).
    """
    from services import robot_mgr
    log(job_id, "CLEANUP", "DO0 ve DO2 → False yapılıyor (robot_mgr)...")
    for do_idx in (0, 2):
        try:
            await asyncio.to_thread(robot_mgr.set_do, do_idx, False)
            log(job_id, "CLEANUP", f"  DO{do_idx} → False ✅")
        except Exception as e:
            log(job_id, "CLEANUP", f"  DO{do_idx} → False HATA: {e}")
