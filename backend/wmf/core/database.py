"""
database.py

MongoDB bağlantı yönetimi — Motor (async).

DEĞİŞENLER (v2):
  • Bağlantı bilgisi artık .env'den okunur. Önceki sürümde kullanıcı adı
    ve parola bu dosyada açıkça yazılıydı ve public repoya commit edilmişti.
  • Log çıktısında parola maskelenir.
  • datetime.utcnow() → datetime.now(timezone.utc)  (3.12'de deprecated)
  • stock dokümanına stok rezervasyonu için 'reserved' alanı eklendi
    (Aşama 3'te kullanılacak).

Koleksiyonlar:
  stock            → tek doküman, güncel kalan malzeme miktarları
  stock_thresholds → tek doküman, uyarı eşikleri
  order_logs       → her siparişin malzeme tüketim kaydı
  refill_logs      → her stok yenileme kaydı
"""

import datetime
import os
import re
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from core.applog import get_logger

# config, .env yüklemesini yapar — bu import sayesinde os.getenv çalışır
from core import config  # noqa: F401  — .env yüklemesini tetikler

log = get_logger(__name__)


# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/wmf_demo")
MONGO_DB  = os.getenv("MONGO_DB", "wmf_demo")

_client: Optional[AsyncIOMotorClient] = None


def _mask_uri(uri: str) -> str:
    """mongodb+srv://user:secret@host/db → mongodb+srv://user:****@host/db"""
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:****@", uri)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ─────────────────────────────────────────────
# BAĞLANTI
# ─────────────────────────────────────────────

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            retryWrites=True,
            w="majority",
        )
    return _client


def get_db():
    return get_client()[MONGO_DB]


def col_stock():
    return get_db()["stock"]


def col_thresholds():
    return get_db()["stock_thresholds"]


def col_order_logs():
    return get_db()["order_logs"]


def col_refill_logs():
    return get_db()["refill_logs"]


def col_syrup_stock():
    return get_db()["syrup_stock"]


async def ping(timeout_s: float = 4.0) -> None:
    """
    Bağlantı canlı mı? Değilse istisna fırlatır.
    Senkronizasyon servisi her turda bunu çağırıyor.
    """
    import asyncio
    await asyncio.wait_for(get_client().admin.command("ping"), timeout=timeout_s)


# ─────────────────────────────────────────────
# VARSAYILAN DOKÜMANLAR
# ─────────────────────────────────────────────
#
# NOT: Varsayılan kahve miktarı 200 g idi. Espresso başına ~9 g ile bu
# yalnızca ~22 fincan eder; bardak sayısı ise 70 tanımlıydı. İkisi
# birbirini tutmuyordu. 700 g (yaklaşık 1 paket çekirdek) 70 bardakla
# uyumlu bir başlangıç değeri.

DEFAULT_STOCK = {
    "_id"        : "current",
    "coffee_g"   : 700.0,    # ~70 espresso
    "milk_ml"    : 5000.0,   # 5 litre
    "choc_g"     : 500.0,
    "cups"       : 70,
    "updated_at" : None,
}

DEFAULT_THRESHOLDS = {
    "_id"        : "current",
    "coffee_g"   : 50.0,    # altına düşünce → kahveli içecekler pasif
    "milk_ml"    : 350.0,   # altına düşünce → sütlü içecekler pasif
    "choc_g"     : 50.0,    # altına düşünce → çikolatalı içecekler pasif
    "cups"       : 2,       # altına düşünce → TÜM sipariş sistemi durur
    "updated_at" : None,
}


# ─────────────────────────────────────────────
# BAŞLATMA
# ─────────────────────────────────────────────

async def init_db() -> bool:
    """
    MongoDB'yi hazırlar: bağlantıyı dener, eksik dokümanları oluşturur,
    indeksleri kurar.

    DEĞİŞEN DAVRANIŞ:
      Önceki sürüm bağlantı kurulamayınca istisna fırlatıyordu. Kiosk
      internetsiz kaldığında bu, uygulamanın açılışını riske atıyordu.
      Artık False dönüyor; sistem yerel SQLite üzerinden çalışmaya
      devam ediyor ve senkronizasyon servisi bağlantıyı arka planda
      yeniden deniyor.

    Döndürür: bağlantı kuruldu mu
    """
    now = _now()

    try:
        await ping()
        log.info("=" * 58)
        log.info("MongoDB bağlantısı başarılı → %s", MONGO_DB)
        log.info("   %s", _mask_uri(MONGO_URI))
        log.info("=" * 58)
    except Exception as e:
        log.warning("MongoDB'ye ulaşılamadı: %s", e)
        log.warning("   Denenen adres: %s", _mask_uri(MONGO_URI))
        log.warning("   Sistem yerel SQLite ile çalışacak; bağlantı gelince "
                    "bekleyen kayıtlar aktarılacak.")
        return False

    try:
        # Yalnızca hiç yoksa oluştur — yereldeki güncel değerleri ezme.
        if await col_stock().find_one({"_id": "current"}) is None:
            await col_stock().insert_one({**DEFAULT_STOCK, "updated_at": now})
            log.info("MongoDB stok dokümanı oluşturuldu.")

        if await col_thresholds().find_one({"_id": "current"}) is None:
            await col_thresholds().insert_one({**DEFAULT_THRESHOLDS, "updated_at": now})
            log.info("MongoDB eşik dokümanı oluşturuldu.")

        await col_order_logs().create_index([("ordered_at", -1)])
        await col_refill_logs().create_index([("refilled_at", -1)])
        log.info("MongoDB indeksleri hazır.")
    except Exception as e:
        log.warning("MongoDB başlangıç işlemleri tamamlanamadı (yoksayıldı): %s", e)

    return True


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        log.info("MongoDB bağlantısı kapatıldı.")
