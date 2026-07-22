"""
database.py

MongoDB bağlantı yönetimi — Motor (async).

Koleksiyonlar:
  stock           → tek doküman, güncel kalan malzeme miktarları
  stock_thresholds→ tek doküman, uyarı eşikleri
  order_logs      → her siparişin malzeme tüketim kaydı
  refill_logs     → her stok yenileme kaydı
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
MONGO_URI  = "mongodb+srv://cobot_barista:1133Kk--..@cluster0.btxg3i.mongodb.net/wmf_demo?appName=Cluster0"
MONGO_DB   = "wmf_demo"

# ─────────────────────────────────────────────
# İSTEK BAŞINA ERIŞILEN KOLEKSİYONLAR
# ─────────────────────────────────────────────
_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10000,  # 10s bağlantı timeout
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
# BAŞLANGIÇ SEED — koleksiyonlar boşsa oluştur
# ─────────────────────────────────────────────

DEFAULT_STOCK = {
    "_id"              : "current",
    "coffee_g"         : 200.0,   # toplam dolum miktarı (g)
    "milk_ml"          : 5000.0,  # toplam dolum (ml) — 5 litre
    "choc_g"           : 150.0,   # toplam dolum (g)
    "cups"             : 70,      # adet
    "updated_at"       : None,
}

DEFAULT_THRESHOLDS = {
    "_id"        : "current",
    "coffee_g"   : 50.0,    # bu değerin altı → tüm ekran pasif
    "milk_ml"    : 350.0,   # bu değerin altı → sütlü içecekler pasif
    "choc_g"     : 50.0,    # bu değerin altı → çikolatalı içecekler pasif
    "cups"       : 2,       # bu değerin altı → tüm ekran pasif
    "updated_at" : None,
}


async def init_db() -> None:
    """
    Uygulama başlarken çağrılır.
    Atlas bağlantısını test eder; stock ve stock_thresholds
    dokümanları yoksa varsayılanlarla oluşturur.
    """
    import datetime
    now = datetime.datetime.utcnow()

    # Bağlantı testi
    try:
        await get_client().admin.command("ping")
        print("="* 60)
        print(f"[DB] ✅ MongoDB Atlas bağlantısı başarılı → {MONGO_DB}")
        print("="* 60)
    except Exception as ping_err:
        print(f"[DB] ❌ MongoDB Atlas ping hatası: {ping_err}")
        raise

    stock = col_stock()
    existing = await stock.find_one({"_id": "current"})
    if existing is None:
        doc = {**DEFAULT_STOCK, "updated_at": now}
        await stock.insert_one(doc)
        print(f"[DB] stock dokümanı oluşturuldu: {doc}")
    else:
        print(f"[DB] stock dokümanı mevcut: coffee={existing.get('coffee_g')}g "
              f"milk={existing.get('milk_ml')}ml choc={existing.get('choc_g')}g "
              f"cups={existing.get('cups')}")

    thresh = col_thresholds()
    existing_t = await thresh.find_one({"_id": "current"})
    if existing_t is None:
        doc_t = {**DEFAULT_THRESHOLDS, "updated_at": now}
        await thresh.insert_one(doc_t)
        print(f"[DB] stock_thresholds dokümanı oluşturuldu: {doc_t}")
    else:
        print(f"[DB] stock_thresholds dokümanı mevcut: "
              f"coffee_min={existing_t.get('coffee_g')}g "
              f"milk_min={existing_t.get('milk_ml')}ml")

    print("="* 60)
    print("[DB] ✅ Veritabanı başlatma tamamlandı.")
    print("="* 60)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        print("[DB] MongoDB bağlantısı kapatıldı.")
