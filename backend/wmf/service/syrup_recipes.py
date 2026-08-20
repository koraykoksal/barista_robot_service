"""
service/syrup_recipes.py

Şurup kanal yapılandırması ve içecek → şurup tarifi eşlemesi.

NEDEN AYRI BİR MODÜL:
  Bu iki sözlük önceden route/syrup.py (eski routers/syrup.py) içinde
  modül seviyesi değişken olarak duruyordu. order_service.py sipariş
  akışının ortasında şunu yapıyordu:

      from routers.syrup import get_syrup_recipe

  Yani bir SERVİS, bir ROTA dosyasından veri okuyordu. Katman yönü
  tersine dönüyordu (route → service olması gerekirken service → route)
  ve HTTP katmanını silmeden sipariş akışını test etmek imkânsızdı.

  Veri artık burada; hem route/syrup.py hem order_service.py buradan
  okuyor. Sözlükler referansla paylaşıldığı için route içindeki mevcut
  mutasyonlar (atama, pop) olduğu gibi çalışmaya devam eder.

KALICILIK UYARISI:
  Bu veri BELLEKTE tutulur — servis yeniden başlayınca kanal adları
  varsayılana döner ve tanımlı şurup tarifleri kaybolur. Kalıcı olması
  gerekiyorsa MongoDB'ye taşınmalı (stok koleksiyonlarıyla aynı desen).
"""

from typing import Any, Dict, Optional

from core.config import SYRUP_CHANNELS


# ─────────────────────────────────────────────
# KANAL YAPILANDIRMASI
# ─────────────────────────────────────────────
# kanal numarası → { name, description, color }

channel_config: Dict[int, Dict[str, str]] = {
    1: {"name": "Vanilya",        "description": "", "color": "#FFF3B0"},
    2: {"name": "Karamel",        "description": "", "color": "#C68642"},
    3: {"name": "Çikolata",       "description": "", "color": "#4E2600"},
    4: {"name": "Beyaz Çikolata", "description": "", "color": "#FFF8F0"},
    5: {"name": "Fındık",         "description": "", "color": "#7B4F00"},
    6: {"name": "Çilek",          "description": "", "color": "#E5352A"},
    7: {"name": "Kanal 7",        "description": "", "color": ""},
    8: {"name": "Kanal 8",        "description": "", "color": ""},
}

# Yapılandırmada eksik kanal kalmasın (SYRUP_CHANNELS .env'den gelir)
for _ch in range(1, SYRUP_CHANNELS + 1):
    channel_config.setdefault(_ch, {"name": f"Kanal {_ch}", "description": "", "color": ""})


# ─────────────────────────────────────────────
# İÇECEK TARİFLERİ
# ─────────────────────────────────────────────
# button_number → { channel, ml, note }
# Boş başlar; /syrup/recipes/{button_number} ucundan doldurulur.

syrup_recipes: Dict[int, Dict[str, Any]] = {}


# ─────────────────────────────────────────────
# ERİŞİM
# ─────────────────────────────────────────────

def get_syrup_recipe(button_number: Any) -> Optional[Dict[str, Any]]:
    """
    Belirtilen içecek için şurup tarifi varsa döner, yoksa None.
    Sipariş akışında ADIM 2.5'te çağrılır.

    Buton numarası string gelebilir ("12"); normalize edilir.
    """
    try:
        btn = int(button_number)
    except (TypeError, ValueError):
        return None
    return syrup_recipes.get(btn)


def channel_name(channel: Any, default: Optional[str] = None) -> str:
    """Kanal adı — loglama ve API yanıtları için."""
    try:
        ch = int(channel)
    except (TypeError, ValueError):
        return default or "Bilinmeyen kanal"
    return channel_config.get(ch, {}).get("name") or (default or f"Motor {ch}")
