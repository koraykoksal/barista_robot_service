"""
stock_service.py

Stok yönetim servisi — MongoDB Motor (async).

Sorumluluklar:
  - Her sipariş sonrası malzeme tüketimini düş
  - Stok durumunu ve eşikleri döndür
  - Eşik ihlali analizi yap (hangi içecekler pasif?)
  - Stok yenileme (refill) kaydet
  - Sipariş logu kaydet
"""

import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from database import (
    col_stock,
    col_thresholds,
    col_order_logs,
    col_refill_logs,
)

# ─────────────────────────────────────────────
# İÇECEK — malzeme türü haritası
# Her ButtonNumber için hangi malzemeleri tükettiği
# ─────────────────────────────────────────────

# uses_milk      : True → sütlü içecek
# uses_chocolate : True → çikolata içeren içecek
# uses_coffee    : True → kahve çekirdeği kullanır
# uses_cup       : daima True (her sipariş 1 bardak)
BEVERAGE_PROFILE: Dict[int, Dict[str, bool]] = {
    1:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Espresso
    2:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Americano
    3:  {"uses_coffee": True,  "uses_milk": True,  "uses_chocolate": False, "uses_cup": True},  # Latte
    4:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Café Americano
    5:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Ristretto
    6:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # 2× Espresso
    7:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # 2× Café Crème
    8:  {"uses_coffee": True,  "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # 2× Café Americano
    12: {"uses_coffee": True,  "uses_milk": True,  "uses_chocolate": False, "uses_cup": True},  # Cappuccino
    14: {"uses_coffee": False, "uses_milk": True,  "uses_chocolate": True,  "uses_cup": True},  # Milk Chocolate
    47: {"uses_coffee": False, "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Hot Water Large
    48: {"uses_coffee": False, "uses_milk": False, "uses_chocolate": False, "uses_cup": True},  # Hot Water
}


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _to_str(doc: dict) -> dict:
    """MongoDB _id ve ObjectId alanlarını string'e çevirir (JSON serileştirme için)."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime.datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ══════════════════════════════════════════════
# STOK OKUMA
# ══════════════════════════════════════════════

async def get_stock() -> Dict[str, Any]:
    """Güncel stok miktarlarını döndürür."""
    doc = await col_stock().find_one({"_id": "current"})
    if doc is None:
        return {}
    return _to_str(doc)


async def get_thresholds() -> Dict[str, Any]:
    """Uyarı eşiklerini döndürür."""
    doc = await col_thresholds().find_one({"_id": "current"})
    if doc is None:
        return {}
    return _to_str(doc)


# ══════════════════════════════════════════════
# EŞİK ANALİZİ
# ══════════════════════════════════════════════

async def get_stock_status() -> Dict[str, Any]:
    """
    Güncel stok + eşikleri karşılaştırarak:
    - Hangi malzemelerin kritik seviyede olduğunu
    - Hangi içecek kategorilerinin pasif edilmesi gerektiğini
    - Genel sistem durumunu döndürür.

    Frontend bu endpoint'i polling ile çağırır.
    """
    stock  = await col_stock().find_one({"_id": "current"}) or {}
    thresh = await col_thresholds().find_one({"_id": "current"}) or {}

    coffee_g  = float(stock.get("coffee_g", 0))
    milk_ml   = float(stock.get("milk_ml", 0))
    choc_g    = float(stock.get("choc_g", 0))
    cups      = int(stock.get("cups", 0))

    t_coffee  = float(thresh.get("coffee_g", 50))
    t_milk    = float(thresh.get("milk_ml", 350))
    t_choc    = float(thresh.get("choc_g", 50))
    t_cups    = int(thresh.get("cups", 2))

    # ── Kritik kontroller ─────────────────────
    coffee_critical = coffee_g < t_coffee     # tüm içecekler pasif
    cups_critical   = cups     < t_cups       # tüm içecekler pasif
    milk_critical   = milk_ml  < t_milk       # sadece sütlü içecekler pasif
    choc_critical   = choc_g   < t_choc       # sadece çikolatalı içecekler pasif

    # Tüm sistemi kapatan durumlar
    all_disabled  = coffee_critical or cups_critical
    # Kategori bazlı
    milk_disabled = milk_critical
    choc_disabled = choc_critical

    # ── Uyarı mesajları ────────────────────────
    alerts: List[Dict[str, Any]] = []

    if cups_critical:
        alerts.append({
            "type"    : "critical",
            "material": "cups",
            "message" : f"Bardak adedi kritik seviyede! Kalan: {cups} adet (eşik: {t_cups})",
            "action"  : "all_disabled",
        })
    if coffee_critical:
        alerts.append({
            "type"    : "critical",
            "material": "coffee",
            "message" : f"Çekirdek kahve kritik seviyede! Kalan: {coffee_g:.1f}g (eşik: {t_coffee}g)",
            "action"  : "all_disabled",
        })
    if milk_critical and not all_disabled:
        alerts.append({
            "type"    : "warning",
            "material": "milk",
            "message" : f"Süt miktarı düşük! Kalan: {milk_ml:.0f}ml (eşik: {t_milk}ml)",
            "action"  : "milk_disabled",
        })
    if choc_critical and not all_disabled:
        alerts.append({
            "type"    : "warning",
            "material": "chocolate",
            "message" : f"Çikolata miktarı düşük! Kalan: {choc_g:.1f}g (eşik: {t_choc}g)",
            "action"  : "choc_disabled",
        })

    overall = "ok"
    if alerts:
        types = [a["type"] for a in alerts]
        overall = "critical" if "critical" in types else "warning"

    print(
        f"[StockService] Durum → kahve={coffee_g:.1f}g milk={milk_ml:.0f}ml "
        f"choc={choc_g:.1f}g cups={cups} | overall={overall}"
    )

    return {
        "stock": {
            "coffee_g": coffee_g,
            "milk_ml" : milk_ml,
            "choc_g"  : choc_g,
            "cups"    : cups,
        },
        "thresholds": {
            "coffee_g": t_coffee,
            "milk_ml" : t_milk,
            "choc_g"  : t_choc,
            "cups"    : t_cups,
        },
        "status": {
            "overall"      : overall,
            "all_disabled" : all_disabled,
            "milk_disabled": milk_disabled,
            "choc_disabled": choc_disabled,
        },
        "alerts"    : alerts,
        "updated_at": stock.get("updated_at"),
    }


# ══════════════════════════════════════════════
# STOK DÜŞÜRME — sipariş sonrası çağrılır
# ══════════════════════════════════════════════

async def consume_stock(
    button_number: int,
    coffee_g     : float = 0.0,
    milk_ml      : float = 0.0,
    choc_g       : float = 0.0,
    cups         : int   = 1,
    job_id       : str   = "",
    recipe_name  : str   = "",
    raw_recipe   : Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Bir sipariş tamamlandığında çağrılır.
    Stok dokümanındaki miktarları düşürür ve order_logs'a yazar.

    coffee_g / milk_ml / choc_g:
      getRecipeComposition'dan gelen gerçek reçete miktarları.
      API'ye erişilemediyse BEVERAGE_PROFILE'dan varsayılan kullanılır.
    """
    now = _now()

    # Eğer reçete miktarı gelmemişse BEVERAGE_PROFILE'dan varsayılan uygula
    profile = BEVERAGE_PROFILE.get(button_number, {})
    if coffee_g == 0 and profile.get("uses_coffee"):
        coffee_g = 9.0   # varsayılan espresso shot gramajı
    if milk_ml == 0 and profile.get("uses_milk"):
        milk_ml  = 150.0  # varsayılan süt miktarı
    if choc_g == 0 and profile.get("uses_chocolate"):
        choc_g   = 20.0   # varsayılan çikolata gramajı

    # ── Stok güncelle ─────────────────────────
    result = await col_stock().update_one(
        {"_id": "current"},
        {
            "$inc": {
                "coffee_g": -coffee_g,
                "milk_ml" : -milk_ml,
                "choc_g"  : -choc_g,
                "cups"    : -cups,
            },
            "$set": {"updated_at": now},
        },
    )

    print(
        f"[StockService] Stok düşüldü → btn={button_number} "
        f"coffee={coffee_g:.1f}g milk={milk_ml:.0f}ml "
        f"choc={choc_g:.1f}g cups={cups}"
    )

    # ── Sipariş logu ──────────────────────────
    log_doc = {
        "job_id"       : job_id,
        "button_number": button_number,
        "recipe_name"  : recipe_name,
        "coffee_g"     : coffee_g,
        "milk_ml"      : milk_ml,
        "choc_g"       : choc_g,
        "cups"         : cups,
        "raw_recipe"   : raw_recipe,
        "ordered_at"   : now,
    }
    await col_order_logs().insert_one(log_doc)
    print(f"[StockService] Sipariş logu yazıldı → job_id={job_id}")

    # Güncel stoğu döndür
    updated = await col_stock().find_one({"_id": "current"}) or {}
    return {
        "consumed": {
            "coffee_g": coffee_g,
            "milk_ml" : milk_ml,
            "choc_g"  : choc_g,
            "cups"    : cups,
        },
        "remaining": {
            "coffee_g": float(updated.get("coffee_g", 0)),
            "milk_ml" : float(updated.get("milk_ml", 0)),
            "choc_g"  : float(updated.get("choc_g", 0)),
            "cups"    : int(updated.get("cups", 0)),
        },
        "modified_count": result.modified_count,
    }


# ══════════════════════════════════════════════
# STOK YENİLEME
# ══════════════════════════════════════════════

async def refill_stock(
    coffee_g : Optional[float] = None,
    milk_ml  : Optional[float] = None,
    choc_g   : Optional[float] = None,
    cups     : Optional[int]   = None,
    note     : str = "",
) -> Dict[str, Any]:
    """
    Stok yenileme işlemi.
    Sadece belirtilen malzemeler güncellenir.
    Negatif değer gönderilemez.
    """
    now = _now()

    if all(v is None for v in [coffee_g, milk_ml, choc_g, cups]):
        raise ValueError("En az bir malzeme miktarı belirtilmeli.")

    set_fields: Dict[str, Any] = {"updated_at": now}
    added: Dict[str, Any] = {}

    if coffee_g is not None and coffee_g >= 0:
        set_fields["coffee_g"] = coffee_g
        added["coffee_g"] = coffee_g
    if milk_ml is not None and milk_ml >= 0:
        set_fields["milk_ml"] = milk_ml
        added["milk_ml"] = milk_ml
    if choc_g is not None and choc_g >= 0:
        set_fields["choc_g"] = choc_g
        added["choc_g"] = choc_g
    if cups is not None and cups >= 0:
        set_fields["cups"] = cups
        added["cups"] = cups

    await col_stock().update_one(
        {"_id": "current"},
        {"$set": set_fields},
        upsert=True,
    )

    # Refill logu
    log_doc = {
        "refilled"   : added,
        "note"       : note,
        "refilled_at": now,
    }
    ins = await col_refill_logs().insert_one(log_doc)
    print(f"[StockService] Stok yenilendi → {added} | log_id={ins.inserted_id}")

    updated = await col_stock().find_one({"_id": "current"}) or {}
    return {
        "refilled" : added,
        "note"     : note,
        "remaining": {
            "coffee_g": float(updated.get("coffee_g", 0)),
            "milk_ml" : float(updated.get("milk_ml", 0)),
            "choc_g"  : float(updated.get("choc_g", 0)),
            "cups"    : int(updated.get("cups", 0)),
        },
    }


# ══════════════════════════════════════════════
# EŞİK GÜNCELLEME
# ══════════════════════════════════════════════

async def update_thresholds(
    coffee_g : Optional[float] = None,
    milk_ml  : Optional[float] = None,
    choc_g   : Optional[float] = None,
    cups     : Optional[int]   = None,
) -> Dict[str, Any]:
    """Uyarı eşik değerlerini günceller."""
    now = _now()
    set_fields: Dict[str, Any] = {"updated_at": now}

    if coffee_g is not None: set_fields["coffee_g"] = coffee_g
    if milk_ml  is not None: set_fields["milk_ml"]  = milk_ml
    if choc_g   is not None: set_fields["choc_g"]   = choc_g
    if cups     is not None: set_fields["cups"]      = cups

    await col_thresholds().update_one(
        {"_id": "current"},
        {"$set": set_fields},
        upsert=True,
    )
    print(f"[StockService] Eşikler güncellendi → {set_fields}")

    updated = await col_thresholds().find_one({"_id": "current"}) or {}
    return _to_str(updated)


# ══════════════════════════════════════════════
# LOGLAR
# ══════════════════════════════════════════════

async def get_order_logs(limit: int = 50) -> List[Dict]:
    """Son N sipariş logunu döndürür."""
    cursor = col_order_logs().find().sort("ordered_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_str(d) for d in docs]


async def get_refill_logs(limit: int = 20) -> List[Dict]:
    """Son N dolum logunu döndürür."""
    cursor = col_refill_logs().find().sort("refilled_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_str(d) for d in docs]


# ══════════════════════════════════════════════
# REÇETE MİKTARLARINI ÇIKAR
# ══════════════════════════════════════════════

def extract_recipe_amounts(recipe_parts: List[Dict]) -> Dict[str, float]:
    """
    getRecipeComposition'dan dönen Parts listesinden
    coffee_g, milk_ml, choc_g değerlerini çıkarır.
    """
    coffee_g = 0.0
    milk_ml  = 0.0
    choc_g   = 0.0

    for part in recipe_parts or []:
        t = (part.get("Type") or part.get("type") or "").lower()

        if t == "coffee":
            coffee_g += float(part.get("QtyPowder") or 0)

        elif t in ("milk", "coldmilk"):
            milk_ml  += float(part.get("QtyMilk") or 0)

        elif t in ("milkfoam", "coldfoam"):
            milk_ml  += float(part.get("QtyFoam") or 0)

        elif t == "choc":
            choc_g   += float(part.get("QtyPowder") or 0)

    return {
        "coffee_g": round(coffee_g, 2),
        "milk_ml" : round(milk_ml, 2),
        "choc_g"  : round(choc_g, 2),
    }
