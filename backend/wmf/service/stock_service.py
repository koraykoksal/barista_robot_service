"""
service/stock_service.py

Stok yönetimi — çift katmanlı veri deposu üzerinde.

VERİ AKIŞI:

    sipariş / yenileme
            │
            ▼
    ┌───────────────────┐     kuyruk      ┌──────────────────┐
    │  SQLite (yerel)   │ ──────────────► │ MongoDB (bulut)  │
    │  anlık, kesintisiz│   sync_service  │ kalıcı, raporlama│
    └───────────────────┘                 └──────────────────┘

  Tüm YAZMALAR önce SQLite'a gider ve senkron tamamlanır. Böylece
  internet kopsa bile stok işlemleri sürer, sipariş akışı takılmaz.
  MongoDB'ye aktarım arka planda, kuyruk üzerinden yapılır.

  Tüm OKUMALAR SQLite'tan yapılır — anlık ve her zaman erişilebilir.

NEDEN MONGO'YA DOĞRUDAN YAZILMIYOR:
  Her stok işlemi bulut gidiş-dönüşü beklerdi. Bağlantı koptuğunda
  sipariş ADIM 8'de takılır; yavaşlamalarda robot boşta bekler.
  Kiosk'un çalışması buluta bağımlı olmamalı.

DEĞİŞENLER:
  • Okuma/yazma MongoDB'den SQLite'a taşındı
  • Stok negatife düşemiyor (MAX(0, ...) ile)
  • İçecek profili catalog.py'den geliyor — ikinci bir tablo yok
  • print() yerine loglama
"""

from typing import Any, Dict, List, Optional

from core import catalog, sqlite_store
from core.applog import get_logger

log = get_logger(__name__)


# ══════════════════════════════════════════════
# OKUMA
# ══════════════════════════════════════════════

async def get_stock() -> Dict[str, Any]:
    import asyncio
    return await asyncio.to_thread(sqlite_store.get_stock)


async def get_thresholds() -> Dict[str, Any]:
    import asyncio
    return await asyncio.to_thread(sqlite_store.get_thresholds)


async def get_stock_status() -> Dict[str, Any]:
    """
    Güncel stok + eşikleri karşılaştırıp hangi içeceklerin
    verilebileceğini belirler. Arayüz bu ucu yokluyor.
    """
    import asyncio
    stock  = await asyncio.to_thread(sqlite_store.get_stock)
    thresh = await asyncio.to_thread(sqlite_store.get_thresholds)
    syrups = await asyncio.to_thread(sqlite_store.get_syrup_stock)

    coffee_g = float(stock.get("coffee_g", 0))
    milk_ml  = float(stock.get("milk_ml", 0))
    choc_g   = float(stock.get("choc_g", 0))
    cups     = int(stock.get("cups", 0))

    t_coffee = float(thresh.get("coffee_g", 50))
    t_milk   = float(thresh.get("milk_ml", 350))
    t_choc   = float(thresh.get("choc_g", 50))
    t_cups   = int(thresh.get("cups", 2))

    coffee_critical = coffee_g < t_coffee   # kahveli her şey durur
    cups_critical   = cups     < t_cups     # her şey durur
    milk_critical   = milk_ml  < t_milk     # yalnızca sütlüler
    choc_critical   = choc_g   < t_choc     # yalnızca çikolatalılar

    all_disabled = coffee_critical or cups_critical

    alerts: List[Dict[str, Any]] = []
    if cups_critical:
        alerts.append({"type": "critical", "material": "cups",
                       "message": f"Bardak adedi kritik seviyede! Kalan: {cups} adet (eşik: {t_cups})",
                       "action": "all_disabled"})
    if coffee_critical:
        alerts.append({"type": "critical", "material": "coffee",
                       "message": f"Çekirdek kahve kritik seviyede! Kalan: {coffee_g:.1f}g (eşik: {t_coffee}g)",
                       "action": "all_disabled"})
    if milk_critical and not all_disabled:
        alerts.append({"type": "warning", "material": "milk",
                       "message": f"Süt miktarı düşük! Kalan: {milk_ml:.0f}ml (eşik: {t_milk}ml)",
                       "action": "milk_disabled"})
    if choc_critical and not all_disabled:
        alerts.append({"type": "warning", "material": "chocolate",
                       "message": f"Çikolata miktarı düşük! Kalan: {choc_g:.1f}g (eşik: {t_choc}g)",
                       "action": "choc_disabled"})

    # ── Şurup kanalları ──
    # Eşiğin altındaki kanaldan şurup akıtılırsa dozaj yarıda biter
    # (EVT:DISP:ABORT) ve reçete eksik kalır. O kanalı kullanan
    # içecekler sipariş edilemez. Kanal → durum haritası döndürülür;
    # frontend hangi içeceğin hangi kanalı kullandığını tarifle eşler.
    syrup_channels = {}
    for row in syrups:
        ch = int(row["channel"])
        ml = float(row["ml"])
        th = float(row["threshold"])
        low = ml < th
        syrup_channels[ch] = {
            "channel": ch, "name": row.get("name"),
            "ml": ml, "threshold": th, "capacity": float(row.get("capacity", 0)),
            "low": low,
        }
        if low:
            alerts.append({
                "type": "warning", "material": f"syrup_{ch}",
                "message": f"{row.get('name', f'Kanal {ch}')} şurubu düşük! "
                           f"Kalan: {ml:.0f}ml (eşik: {th:.0f}ml)",
                "action": "syrup_disabled",
            })

    # Eşiğin altındaki kanal numaraları — frontend/order kapısı için
    disabled_syrup_channels = [ch for ch, v in syrup_channels.items() if v["low"]]

    overall = "ok"
    if alerts:
        overall = "critical" if any(a["type"] == "critical" for a in alerts) else "warning"

    log.debug("Durum → kahve=%.1fg süt=%.0fml çik=%.1fg bardak=%d | %s",
              coffee_g, milk_ml, choc_g, cups, overall)

    return {
        "stock":      {"coffee_g": coffee_g, "milk_ml": milk_ml, "choc_g": choc_g, "cups": cups},
        "thresholds": {"coffee_g": t_coffee, "milk_ml": t_milk, "choc_g": t_choc, "cups": t_cups},
        "status": {
            "overall": overall,
            "all_disabled": all_disabled,
            "milk_disabled": milk_critical,
            "choc_disabled": choc_critical,
        },
        "syrup_channels": syrup_channels,
        "disabled_syrup_channels": disabled_syrup_channels,
        "alerts": alerts,
        "updated_at": stock.get("updated_at"),
    }


async def get_order_logs(limit: int = 50) -> List[Dict]:
    import asyncio
    return await asyncio.to_thread(sqlite_store.get_order_logs, limit)


async def get_refill_logs(limit: int = 20) -> List[Dict]:
    import asyncio
    return await asyncio.to_thread(sqlite_store.get_refill_logs, limit)


# ══════════════════════════════════════════════
# YAZMA
# ══════════════════════════════════════════════

# Reçete alınamadığında kullanılan varsayılanlar — catalog.py'den
DEFAULT_COFFEE_G = catalog.DEFAULT_COFFEE_G
DEFAULT_MILK_ML  = catalog.DEFAULT_MILK_ML
DEFAULT_CHOC_G   = catalog.DEFAULT_CHOC_G


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
    Sipariş sonrası stok düşer ve sipariş logunu yazar.

    Miktar verilmemişse içeceğin katalog profiline göre varsayılan
    kullanılır — böylece reçete makineden alınamadığında da makul
    bir düşüm yapılır.
    """
    import asyncio

    uses = catalog.ingredients(button_number)

    if coffee_g <= 0 and uses["coffee"]:
        coffee_g = DEFAULT_COFFEE_G
    if milk_ml <= 0 and uses["milk"]:
        milk_ml = DEFAULT_MILK_ML
    if choc_g <= 0 and uses["choc"]:
        choc_g = DEFAULT_CHOC_G

    # Profilde olmayan malzemeler düşülmez — yanlış reçete gelirse
    # sütsüz bir içecek sütü tüketmiş görünmesin.
    if not uses["coffee"]:
        coffee_g = 0.0
    if not uses["milk"]:
        milk_ml = 0.0
    if not uses["choc"]:
        choc_g = 0.0

    return await asyncio.to_thread(
        sqlite_store.consume,
        int(button_number), float(coffee_g), float(milk_ml), float(choc_g), int(cups),
        job_id, recipe_name or catalog.name(button_number), raw_recipe,
    )


async def refill_stock(
    coffee_g: Optional[float] = None,
    milk_ml : Optional[float] = None,
    choc_g  : Optional[float] = None,
    cups    : Optional[int]   = None,
    note    : str = "",
) -> Dict[str, Any]:
    """
    Stok yenileme.

    DİKKAT: Girilen değer mevcut miktara EKLENMEZ, onun YERİNE yazılır.
    Boş bırakılan alanlara dokunulmaz.
    """
    import asyncio
    return await asyncio.to_thread(
        sqlite_store.refill,
        {"coffee_g": coffee_g, "milk_ml": milk_ml, "choc_g": choc_g, "cups": cups},
        note,
    )


async def update_thresholds(
    coffee_g: Optional[float] = None,
    milk_ml : Optional[float] = None,
    choc_g  : Optional[float] = None,
    cups    : Optional[int]   = None,
) -> Dict[str, Any]:
    import asyncio
    return await asyncio.to_thread(
        sqlite_store.set_thresholds,
        {"coffee_g": coffee_g, "milk_ml": milk_ml, "choc_g": choc_g, "cups": cups},
    )


async def get_syrup_stock() -> List[Dict]:
    import asyncio
    return await asyncio.to_thread(sqlite_store.get_syrup_stock)


async def consume_syrup(channel: int, ml: float, job_id: str = "") -> Dict[str, Any]:
    """Sipariş sırasında şurup akıtıldıktan sonra kanaldan düşer."""
    import asyncio
    return await asyncio.to_thread(sqlite_store.consume_syrup, int(channel), float(ml), job_id)


async def refill_syrup(channel: int, ml=None, threshold=None,
                       capacity=None, name=None) -> Dict[str, Any]:
    import asyncio
    return await asyncio.to_thread(
        sqlite_store.refill_syrup, int(channel), ml, threshold, capacity, name
    )


async def check_syrup_available(channel: int, need_ml: float) -> Dict[str, Any]:
    """
    Sipariş öncesi kapı kontrolü: kanalda yeterli şurup var mı?

    "Yeterli" = kalan miktar hem eşiğin üstünde hem de bu siparişin
    ihtiyacını karşılayacak kadar. İkisi birden aranır çünkü eşik
    güvenlik payı, need_ml ise bu siparişin gereksinimidir.
    """
    import asyncio
    row = await asyncio.to_thread(sqlite_store.get_syrup_channel, int(channel))
    if not row:
        return {"ok": False, "reason": "channel_missing",
                "message": f"Kanal {channel} tanımlı değil."}

    ml = float(row["ml"])
    th = float(row["threshold"])
    enough = ml >= th and ml >= float(need_ml)
    return {
        "ok": enough,
        "channel": int(channel),
        "name": row.get("name"),
        "remaining_ml": ml,
        "threshold": th,
        "need_ml": float(need_ml),
        "reason": None if enough else ("below_threshold" if ml < th else "insufficient"),
    }


# ══════════════════════════════════════════════
# REÇETE AYRIŞTIRMA
# ══════════════════════════════════════════════

def extract_recipe_amounts(recipe_parts: List[Dict]) -> Dict[str, float]:
    """
    Makinenin getRecipeComposition yanıtından malzeme miktarlarını çıkarır.

    Parts yapısı makine yazılımına göre değişebildiği için birden fazla
    alan adı denenir; tanınmayan bileşenler yoksayılır.
    """
    amounts = {"coffee_g": 0.0, "milk_ml": 0.0, "choc_g": 0.0}

    for part in recipe_parts or []:
        if not isinstance(part, dict):
            continue

        name = str(part.get("Name") or part.get("Ingredient") or part.get("Type") or "").lower()
        raw  = part.get("Amount", part.get("Quantity", part.get("Value", 0)))
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue

        if any(k in name for k in ("coffee", "bean", "espresso", "kahve", "çekirdek")):
            amounts["coffee_g"] += value
        elif any(k in name for k in ("milk", "süt", "sut")):
            amounts["milk_ml"] += value
        elif any(k in name for k in ("choc", "cocoa", "çikolata", "cikolata", "kakao")):
            amounts["choc_g"] += value

    return amounts
