"""
catalog.py

İÇECEK KATALOĞU — TEK DOĞRULUK KAYNAĞI.

Bu dosyadan önce aynı bilgi dört ayrı yerde tutuluyordu ve birbirini
tutmuyordu:

  config.BEVERAGE_NAMES        btn 1 = "Espresso"
  config.DRINK_NAMES           btn 1 = "Soğuk süt"      ← farklı şema
  stock_service.BEVERAGE_PROFILE
  frontend/helper/Beverages.js

Teyit edilen doğru şema: buton 1 = Espresso (frontend'deki numaralandırma).
config.py içindeki DRINK_NAMES / ART_RECIPE_MAP / ORDER_ART_BUTTON_NUMBERS
başka bir makine dizilimine aitti ve kaldırıldı ( /order_art diye bir
endpoint de zaten yoktu ).

──────────────────────────────────────────────────────────────────
DİKKAT: ButtonNumber ≠ RecipeNumber
──────────────────────────────────────────────────────────────────
startBeverage / checkBeverage  →  a_iBtnNbr    = ButtonNumber
getRecipeComposition           →  RecipeNumber = RecipeNumber

Bu ikisi yalnızca Espresso'da aynı. Önceki kodda getRecipeComposition'a
ButtonNumber gönderiliyordu; Espresso dışındaki her içecekte yanlış
(veya boş) reçete dönüyor, stok da sessizce varsayılan değerlerle
düşülüyordu. recipe_number() bu eşlemeyi doğru yapar.
"""

from typing import Any, Dict, List, Optional


# ══════════════════════════════════════════════
# KATALOG
# ══════════════════════════════════════════════
#
# button        : a_iBtnNbr — makineye gönderilen buton numarası
# recipe        : RecipeNumber — getRecipeComposition için
# name_tr/en    : görünen ad
# uses_coffee   : çekirdek kahve tüketir mi
# uses_milk     : süt tüketir mi
# uses_choc     : çikolata tüketir mi
# brew_seconds  : tahmini hazırlanma süresi (Aşama 4'te makinenin
#                 startPushDispensingFinished olayıyla değişecek;
#                 şimdilik ilerleme çubuğu için referans)
# category      : "coffee" | "ice_cream"

BEVERAGES: List[Dict[str, Any]] = [
    {
        "button": 1,  "recipe": 1,
        "name_tr": "Espresso",   "name_en": "Espresso",
        "uses_coffee": True,  "uses_milk": False, "uses_choc": False,
        "brew_seconds": 23, "category": "coffee",
    },
    {
        "button": 2,  "recipe": 5,
        "name_tr": "Americano",  "name_en": "Americano",
        "uses_coffee": True,  "uses_milk": False, "uses_choc": False,
        "brew_seconds": 38, "category": "coffee",
    },
    {
        "button": 3,  "recipe": 91,
        "name_tr": "Latte",      "name_en": "Latte",
        "uses_coffee": True,  "uses_milk": True,  "uses_choc": False,
        "brew_seconds": 40, "category": "coffee",
    },
    {
        "button": 5,  "recipe": 3,
        "name_tr": "Ristretto",  "name_en": "Ristretto",
        "uses_coffee": True,  "uses_milk": False, "uses_choc": False,
        "brew_seconds": 20, "category": "coffee",
    },
    {
        "button": 12, "recipe": 88,
        "name_tr": "Cappuccino", "name_en": "Cappuccino",
        "uses_coffee": True,  "uses_milk": True,  "uses_choc": False,
        "brew_seconds": 28, "category": "coffee",
    },
    {
        "button": 14, "recipe": 95,
        "name_tr": "Sütlü Çikolata", "name_en": "Hot Chocolate",
        "uses_coffee": False, "uses_milk": True,  "uses_choc": True,
        "brew_seconds": 41, "category": "coffee",
    },
]


# ══════════════════════════════════════════════
# VARSAYILAN TÜKETİM MİKTARLARI
# ══════════════════════════════════════════════
# Yalnızca getRecipeComposition'a ulaşılamadığında kullanılır.
# Gerçek değer her zaman makineden gelen reçetedir.

DEFAULT_COFFEE_G = 9.0     # tek espresso shot
DEFAULT_MILK_ML  = 150.0
DEFAULT_CHOC_G   = 20.0
CUPS_PER_ORDER   = 1


# ══════════════════════════════════════════════
# İNDEKSLER
# ══════════════════════════════════════════════

_BY_BUTTON: Dict[int, Dict[str, Any]] = {b["button"]: b for b in BEVERAGES}


def _as_int(value: Any) -> Optional[int]:
    """'12' / 12 / 12.0 → 12 ; None / 'abc' → None"""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════
# SORGULAR
# ══════════════════════════════════════════════

def get(button: Any) -> Optional[Dict[str, Any]]:
    """Buton numarasına göre katalog kaydını döndürür. Yoksa None."""
    btn = _as_int(button)
    return _BY_BUTTON.get(btn) if btn is not None else None


def recipe_number(button: Any) -> Optional[int]:
    """
    getRecipeComposition'a gönderilecek RecipeNumber.
    Katalogda yoksa None döner — çağıran taraf varsayılana düşmeli.
    """
    item = get(button)
    return item["recipe"] if item else None


def name(button: Any, lang: str = "tr") -> str:
    """Loglama ve arayüz için içecek adı."""
    item = get(button)
    if not item:
        return f"Bilinmeyen içecek (btn={button})"
    return item.get(f"name_{lang.lower()}") or item["name_tr"]


def brew_seconds(button: Any) -> int:
    """Tahmini hazırlanma süresi. Katalogda yoksa 0."""
    item = get(button)
    return int(item["brew_seconds"]) if item else 0


def ingredients(button: Any) -> Dict[str, bool]:
    """
    İçeceğin hangi malzemeleri tükettiği.
    Katalogda yoksa en güvenli varsayım: hepsini tüketiyor kabul et,
    böylece stok kontrolü yanlışlıkla izin vermez.
    """
    item = get(button)
    if not item:
        return {"coffee": True, "milk": True, "choc": True, "cup": True}
    return {
        "coffee": bool(item["uses_coffee"]),
        "milk":   bool(item["uses_milk"]),
        "choc":   bool(item["uses_choc"]),
        "cup":    True,   # her sipariş 1 bardak
    }


def all_buttons() -> List[int]:
    return [b["button"] for b in BEVERAGES]


def as_public_list(lang: str = "tr") -> List[Dict[str, Any]]:
    """
    Frontend'e /catalog ucundan dönecek sadeleştirilmiş liste.
    Arayüzün kendi Beverages.js kopyasını tutmasına gerek kalmaz.
    """
    return [
        {
            "button":       b["button"],
            "name":         b.get(f"name_{lang.lower()}") or b["name_tr"],
            "name_tr":      b["name_tr"],
            "name_en":      b["name_en"],
            "category":     b["category"],
            "uses_coffee":  b["uses_coffee"],
            "uses_milk":    b["uses_milk"],
            "uses_choc":    b["uses_choc"],
            "brew_seconds": b["brew_seconds"],
        }
        for b in BEVERAGES
    ]


# ══════════════════════════════════════════════
# GERİYE UYUMLULUK
# ══════════════════════════════════════════════
# Eski kod config.BEVERAGE_NAMES ve config.BREW_TIMERS bekliyor.
# config.py bunları buradan türetiyor; elle senkron tutmaya gerek yok.

BEVERAGE_NAMES: Dict[int, str] = {b["button"]: b["name_tr"] for b in BEVERAGES}
BREW_TIMERS:    Dict[int, int] = {b["button"]: b["brew_seconds"] for b in BEVERAGES}
