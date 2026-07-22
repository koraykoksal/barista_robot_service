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

# config, .env yüklemesini yapar — bu import sayesinde os.getenv çalışır
from core import config  # noqa: F401  — .env yüklemesini tetikler


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
    # Aşama 3: sipariş başladığında rezerve edilen, bittiğinde serbest
    # bırakılan geçici miktarlar. Eşik hesabı (kalan - rezerve) üzerinden
    # yapılır; böylece aynı anda iki sipariş aynı son bardağı alamaz.
    "reserved"   : {"coffee_g": 0.0, "milk_ml": 0.0, "choc_g": 0.0, "cups": 0},
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

async def init_db() -> None:
    """
    Uygulama başlarken çağrılır.
    Bağlantıyı test eder, eksik dokümanları varsayılanlarla oluşturur,
    indeksleri kurar.
    """
    now = _now()

    try:
        await get_client().admin.command("ping")
        print("=" * 60)
        print(f"[DB] ✅ MongoDB bağlantısı başarılı → {MONGO_DB}")
        print(f"[DB]    {_mask_uri(MONGO_URI)}")
        print("=" * 60)
    except Exception as ping_err:
        print(f"[DB] ❌ MongoDB ping hatası: {ping_err}")
        print(f"[DB]    Denenen adres: {_mask_uri(MONGO_URI)}")
        raise

    # ── stock ─────────────────────────────────
    stock = col_stock()
    existing = await stock.find_one({"_id": "current"})
    if existing is None:
        await stock.insert_one({**DEFAULT_STOCK, "updated_at": now})
        print(f"[DB] stock dokümanı oluşturuldu: {DEFAULT_STOCK['cups']} bardak, "
              f"{DEFAULT_STOCK['coffee_g']}g kahve")
    else:
        # Eski kayıtlarda 'reserved' alanı yok — geriye dönük ekle
        if "reserved" not in existing:
            await stock.update_one(
                {"_id": "current"},
                {"$set": {"reserved": DEFAULT_STOCK["reserved"], "updated_at": now}},
            )
            print("[DB] stock dokümanına 'reserved' alanı eklendi (migrasyon).")
        print(f"[DB] stock mevcut: coffee={existing.get('coffee_g')}g "
              f"milk={existing.get('milk_ml')}ml choc={existing.get('choc_g')}g "
              f"cups={existing.get('cups')}")

    # ── stock_thresholds ──────────────────────
    thresh = col_thresholds()
    existing_t = await thresh.find_one({"_id": "current"})
    if existing_t is None:
        await thresh.insert_one({**DEFAULT_THRESHOLDS, "updated_at": now})
        print(f"[DB] stock_thresholds dokümanı oluşturuldu: {DEFAULT_THRESHOLDS}")
    else:
        print(f"[DB] eşikler mevcut: coffee_min={existing_t.get('coffee_g')}g "
              f"milk_min={existing_t.get('milk_ml')}ml cups_min={existing_t.get('cups')}")

    # ── indeksler ─────────────────────────────
    # Log koleksiyonları sürekli büyür; tarih indeksi olmadan
    # sort(-1).limit(N) sorguları tüm koleksiyonu tarar.
    try:
        await col_order_logs().create_index([("ordered_at", -1)])
        await col_refill_logs().create_index([("refilled_at", -1)])
        print("[DB] İndeksler hazır.")
    except Exception as idx_err:
        print(f"[DB] ⚠️  İndeks oluşturma hatası (yoksayıldı): {idx_err}")

    print("=" * 60)
    print("[DB] ✅ Veritabanı başlatma tamamlandı.")
    print("=" * 60)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        print("[DB] MongoDB bağlantısı kapatıldı.")
