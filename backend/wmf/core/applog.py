"""
core/applog.py

Uygulama loglaması — kurulum + sipariş akışı yardımcıları.

Önceki sürümde her şey print() ile stdout'a yazılıyordu. Kiosk 7/24
çalıştığı ve genellikle bir servis yöneticisi altında başlatıldığı için
bunun üç sorunu vardı:

  • Servis yeniden başlayınca geçmiş kayboluyordu.
  • Seviye ayrımı yoktu; hata ile bilgi aynı yığında akıyordu.
  • Sahada "dün akşam ne oldu" sorusunun cevabı yoktu.

Artık dosyaya da yazılıyor, boyut sınırıyla döndürülüyor (disk dolmasın)
ve seviye .env'den ayarlanabiliyor.

DOSYALAR (varsayılan backend/wmf/logs/):
  backend.log   tüm kayıtlar
  error.log     yalnızca WARNING ve üstü — sorun ararken bakılacak yer

Bu modül core/logging.py'nin yerini aldı. Eski ad stdlib'in `logging`
modülüyle karışıyordu.

KULLANIM:
    from core.applog import get_logger
    log = get_logger(__name__)
    log.info("Sipariş başladı")
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from core import catalog
from core.config import (
    APP_ROOT,
    BARISTA_LABELS,
    DECAF_LABELS,
    LOG_BACKUPS,
    LOG_DIR,
    LOG_LEVEL,
    LOG_MAX_MB,
    MILK_LABELS,
    SIRUP_LABELS,
    SML_LABELS,
)

_configured = False

# Konsol ve dosya için ayrı biçim: konsolda kısa, dosyada tam.
_CONSOLE_FMT = "%(asctime)s %(levelname)-7s %(name)-22s %(message)s"
_FILE_FMT    = "%(asctime)s %(levelname)-7s %(name)-28s [%(filename)s:%(lineno)d] %(message)s"
_DATE_FMT    = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> Path:
    """
    Kök logger'ı yapılandırır. app.py başlangıcında BİR KEZ çağrılır.
    Log klasörünün yolunu döndürür.
    """
    global _configured

    log_dir = Path(LOG_DIR) if Path(LOG_DIR).is_absolute() else APP_ROOT / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    if _configured:
        return log_dir

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)          # süzme handler seviyesinde
    root.handlers.clear()

    # ── Konsol ────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, _DATE_FMT))
    root.addHandler(console)

    max_bytes = max(1, LOG_MAX_MB) * 1024 * 1024

    # ── Tüm kayıtlar ──────────────────────────
    full = logging.handlers.RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=max_bytes, backupCount=LOG_BACKUPS, encoding="utf-8",
    )
    full.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    full.setFormatter(logging.Formatter(_FILE_FMT, _DATE_FMT))
    root.addHandler(full)

    # ── Yalnızca uyarı ve hatalar ─────────────
    # Sahada "sorun ne" sorusunun cevabı tek dosyada olsun.
    errors = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=max_bytes, backupCount=LOG_BACKUPS, encoding="utf-8",
    )
    errors.setLevel(logging.WARNING)
    errors.setFormatter(logging.Formatter(_FILE_FMT, _DATE_FMT))
    root.addHandler(errors)

    # Gürültülü kütüphaneleri kıs — bunlar DEBUG'da her paketi basıyor
    for noisy in ("websockets", "pymongo", "motor", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True

    boot = logging.getLogger("core.applog")
    boot.info("=" * 58)
    boot.info("Loglama hazır → %s (seviye=%s, %d MB × %d dosya)",
              log_dir, LOG_LEVEL.upper(), LOG_MAX_MB, LOG_BACKUPS + 1)
    boot.info("=" * 58)
    return log_dir


def get_logger(name: str) -> logging.Logger:
    """Modül logger'ı. setup_logging() çağrılmamışsa da güvenle çalışır."""
    return logging.getLogger(name)


# ══════════════════════════════════════════════
# SİPARİŞ AKIŞI LOGLARI
# ══════════════════════════════════════════════

_order_log = logging.getLogger("order")


def log(job_id: str, phase: str, msg: str) -> None:
    """
    Sipariş akışı adımı.

        [1a2b3c4d | STEP_2_DI1          ] DI1=True bekleniyor...

    Sabit genişlikli faz alanı uzun akış loglarını hizalı tutar.
    """
    short = job_id[:8] if job_id else "--------"
    _order_log.info("[%s | %-25s] %s", short, phase, msg)


def log_order_detail(job_id: str, message: Dict[str, Any], client_ip: str = "?") -> None:
    """
    Frontend'den gelen sipariş parametrelerini okunabilir biçimde yazar.

    Ham JSON'da a_iBarista="1" tek başına bir şey ifade etmiyor;
    etiket tablolarıyla insan diline çevriliyor.
    """
    btn_raw  = str(message.get("a_iBtnNbr", "?"))
    bev_name = catalog.name(btn_raw)

    def label(table: Dict[str, str], key: str) -> str:
        raw = str(message.get(key, "?"))
        return table.get(raw, raw)

    portioner = str(message.get("a_iBeanPortioner", "0"))

    lines = [
        "─" * 58,
        "📥 YENİ SİPARİŞ",
        f"   Zaman      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"   Client IP  : {client_ip}",
        f"   Job ID     : {job_id}",
        f"   Fonksiyon  : {message.get('function', '?')}",
        f"   İçecek     : {bev_name}  (ButtonNumber={btn_raw})",
        f"   Yoğunluk   : {label(BARISTA_LABELS, 'a_iBarista')}",
        f"   Boyut      : {label(SML_LABELS,     'a_iSML')}",
        f"   Decaf      : {label(DECAF_LABELS,   'a_iDecaf')}",
        f"   Süt tipi   : {label(MILK_LABELS,    'a_iMilktype')}",
        f"   Şurup      : {label(SIRUP_LABELS,   'a_iSirupType')}",
        f"   Şurup boy  : {label(SML_LABELS,     'a_iSirupSML')}",
        f"   Öğütücü    : {'Tarife göre' if portioner == '0' else f'Portioner {portioner}'}",
        f"   Bardak boy.: %{message.get('a_iCupSizeAdj', '100')}",
        f"   Ham mesaj  : {json.dumps(message, ensure_ascii=False)}",
        "─" * 58,
    ]
    _order_log.info("\n".join(lines))
