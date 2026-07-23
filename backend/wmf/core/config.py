"""
config.py

Tüm yapılandırma tek yerden yönetilir ve artık ortam değişkenlerinden
okunur. Sabit değerler yalnızca .env yoksa devreye giren varsayılanlardır.

DEĞİŞENLER (v2):
  • IP, port, token, timeout değerleri .env'den okunuyor
  • DRINK_NAMES / ART_RECIPE_MAP / ORDER_ART_BUTTON_NUMBERS kaldırıldı —
    ikinci ve yanlış bir buton numaralandırma şemasıydı, üstelik
    /order_art diye bir endpoint hiç yoktu (ölü konfigürasyon)
  • BEVERAGE_NAMES ve BREW_TIMERS artık catalog.py'den türetiliyor
"""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from core import catalog

# .env dosyasını bu dosyanın yanından yükle (çalışma dizininden bağımsız)
# .env dosyası uygulama kökünde (backend/wmf/.env) durur.
# config.py artık core/ altında olduğu için bir üst klasöre çıkıyoruz.
# Çalışma dizininden bağımsız çalışsın diye mutlak yol kullanılıyor.
APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(APP_ROOT / ".env")


# ─────────────────────────────────────────────
# ORTAM DEĞİŞKENİ YARDIMCILARI
# ─────────────────────────────────────────────

def _str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value.strip() if value and value.strip() else default


def _int(key: str, default: int) -> int:
    try:
        return int(_str(key, str(default)))
    except ValueError:
        print(f"[config] ⚠️  {key} sayıya çevrilemedi, varsayılan kullanılıyor: {default}")
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(_str(key, str(default)))
    except ValueError:
        print(f"[config] ⚠️  {key} sayıya çevrilemedi, varsayılan kullanılıyor: {default}")
        return default


def _list(key: str, default: str) -> List[str]:
    raw = _str(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ─────────────────────────────────────────────
# ROBOT
# ─────────────────────────────────────────────
ROBOT_IP = _str("ROBOT_IP", "127.0.0.1")

ROBOT_MODE_SWITCH_TIMEOUT  = _float("ROBOT_MODE_SWITCH_TIMEOUT", 10.0)
ROBOT_MODE_POLL_INTERVAL   = _float("ROBOT_MODE_POLL_INTERVAL", 0.3)
ROBOT_STATUS_POLL_INTERVAL = _float("ROBOT_STATUS_POLL_INTERVAL", 2.0)


# ─────────────────────────────────────────────
# KAHVE MAKİNESİ (WMF CM-Remote)
# ─────────────────────────────────────────────
COFFEE_MACHINE_IP    = _str("COFFEE_MACHINE_IP", "192.168.1.111")
COFFEE_MACHINE_PORT  = _int("COFFEE_MACHINE_PORT", 25000)
COFFEE_MACHINE_TOKEN = _str("COFFEE_MACHINE_TOKEN", "")


# ─────────────────────────────────────────────
# SYRUP DİSPENSER (LogoSurup)
# ─────────────────────────────────────────────
SYRUP_HOST     = _str("SYRUP_HOST", "192.168.1.155")
SYRUP_PORT     = _int("SYRUP_PORT", 5000)
SYRUP_TIMEOUT  = _float("SYRUP_TIMEOUT", 15.0)
SYRUP_CHANNELS = _int("SYRUP_CHANNELS", 8)


# ─────────────────────────────────────────────
# GÜVENLİK
# ─────────────────────────────────────────────
ADMIN_TOKEN  = _str("ADMIN_TOKEN", "")
CORS_ORIGINS = _list("CORS_ORIGINS", "http://localhost:5173")


# ─────────────────────────────────────────────
# SİPARİŞ AKIŞI ZAMAN AŞIMLARI (saniye)
# ─────────────────────────────────────────────
COFFEE_OVERALL_TIMEOUT = _float("COFFEE_OVERALL_TIMEOUT", 120.0)
COFFEE_RECV_TIMEOUT    = _float("COFFEE_RECV_TIMEOUT", 20.0)
COFFEE_SILENT_ROUNDS   = _int("COFFEE_SILENT_ROUNDS", 6)
DI_WAIT_TIMEOUT        = _float("DI_WAIT_TIMEOUT", 60.0)

# Tamamlanan sipariş kayıtlarının bellekte tutulma süresi.
# Bu süre sonunda _jobs sözlüğünden silinirler (bellek sızıntısı önlemi).
JOB_RETENTION_SECONDS = _int("JOB_RETENTION_SECONDS", 900)   # 15 dk


# ─────────────────────────────────────────────
# LOGLAMA
# ─────────────────────────────────────────────
LOG_LEVEL   = _str("LOG_LEVEL", "INFO")        # DEBUG | INFO | WARNING | ERROR
LOG_DIR     = _str("LOG_DIR", "logs")          # göreliyse APP_ROOT'a göre
LOG_MAX_MB  = _int("LOG_MAX_MB", 10)           # dosya başına boyut sınırı
LOG_BACKUPS = _int("LOG_BACKUPS", 5)           # kaç eski dosya saklansın


# ─────────────────────────────────────────────
# VERİTABANI — ÇİFT KATMAN
# ─────────────────────────────────────────────
#
# SQLite yerel ve her zaman erişilebilir; kiosk internetsiz kaldığında
# bile stok işlemleri kesintisiz sürsün diye TÜM yazmalar önce oraya
# gider. MongoDB uzun vadeli kayıt ve raporlama katmanıdır; yazmalar
# bir kuyruk (outbox) üzerinden ona aktarılır.
#
# Neden Mongo'ya doğrudan yazılmıyor: her stok işlemi bulut gidiş-dönüşü
# beklerdi. Bağlantı koptuğunda sipariş akışı stok adımında takılır,
# gecikmelerde ise robot boşta bekler.
SQLITE_PATH = _str("SQLITE_PATH", "data/kiosk.db")   # göreliyse APP_ROOT'a göre

# Kuyruğun MongoDB'ye boşaltılma sıklığı (saniye)
SYNC_INTERVAL = _float("SYNC_INTERVAL", 20.0)

# Tek turda en fazla kaç kayıt aktarılsın (uzun kopukluk sonrası
# tek seferde binlerce kaydı göndermeyi engeller)
SYNC_BATCH = _int("SYNC_BATCH", 200)

# MongoDB tamamen devre dışı bırakılabilir (yalnızca yerel çalışma)
MONGO_ENABLED = _str("MONGO_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")


# ─────────────────────────────────────────────
# İÇECEK BİLGİLERİ — catalog.py'den türetilir
# ─────────────────────────────────────────────
# Elle senkron tutulmaz. İçecek eklemek/çıkarmak için catalog.py'yi düzenleyin.
BEVERAGE_NAMES = catalog.BEVERAGE_NAMES
BREW_TIMERS    = catalog.BREW_TIMERS


# ─────────────────────────────────────────────
# SİPARİŞ PARAMETRE ETİKETLERİ (log için)
# ─────────────────────────────────────────────
BARISTA_LABELS = {"0": "Hafif (%85)", "1": "Normal (%100)", "2": "Güçlü (%115)"}
SML_LABELS     = {"0": "Small", "1": "Medium", "2": "Large"}
DECAF_LABELS   = {"0": "Normal", "1": "Decaf"}
MILK_LABELS    = {"-1": "Tarife göre (default)", "0": "Normal süt", "1": "Yağsız süt"}
SIRUP_LABELS   = {"-1": "Tarife göre (default)", "0": "Şuruupsuz",
                  "1": "Şurup 1", "2": "Şurup 2", "3": "Şurup 3", "4": "Şurup 4"}


# ─────────────────────────────────────────────
# MAKİNE HATA KODLARI
# ─────────────────────────────────────────────
MACHINE_ERROR_MESSAGES: dict = {
    68:  "Çekirdek kahve bölmesi boş veya kapağı açık",
    69:  "Çekirdek kahve bölmesi boş veya kapağı açık (2. öğütücü)",
    70:  "Çekirdek kahve bölmesi boş veya kapağı açık (3. öğütücü)",
    71:  "Çekirdek kahve bölmesi boş veya kapağı açık (4. öğütücü)",
    74:  "Panel açık",
    75:  "Posa çekmecesi dolu veya yerinde değil",
    76:  "Posa çekmecesi dolu veya yerinde değil",
    80:  "Su deposu boş veya yerinde değil",
    82:  "Süt konteyneri boş veya yerinde değil",
    83:  "Süt konteyneri boş veya yerinde değil (2. konteyner)",
    90:  "Temizlik gerekli",
    92:  "Acil temizlik gerekli",
    136: "Makine ısınıyor",
}


# ─────────────────────────────────────────────
# BAŞLANGIÇ DOĞRULAMASI
# ─────────────────────────────────────────────

def validate() -> None:
    """
    app.py başlarken çağrılır. Eksik/riskli ayarları erkenden bildirir.
    Uygulamayı durdurmaz — sahada yarım yapılandırmayla da açılabilmeli.
    """
    warnings = []

    if not ADMIN_TOKEN:
        warnings.append(
            "ADMIN_TOKEN boş — yönetici uçları (stok yenileme, robot DO yazma, "
            "program durdurma) KORUMASIZ. Sahaya çıkmadan .env içine doldurun."
        )

    if not COFFEE_MACHINE_TOKEN:
        warnings.append("COFFEE_MACHINE_TOKEN boş — makine isteği reddedebilir.")

    if "*" in CORS_ORIGINS:
        warnings.append("CORS_ORIGINS '*' içeriyor — üretimde açık origin kullanmayın.")

    if ROBOT_IP in ("127.0.0.1", "localhost"):
        warnings.append(
            f"ROBOT_IP={ROBOT_IP} — simülatöre bakıyor. "
            "Gerçek robot için .env içinde ROBOT_IP değerini güncelleyin."
        )

    if MONGO_ENABLED and not os.getenv("MONGO_URI"):
        warnings.append("MONGO_URI ortam değişkeni yok — varsayılan yerel bağlantı denenecek.")

    if not MONGO_ENABLED:
        warnings.append(
            "MONGO_ENABLED=false — yalnızca yerel SQLite kullanılacak, "
            "buluta hiçbir kayıt aktarılmayacak."
        )

    if LOG_LEVEL.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        warnings.append(f"LOG_LEVEL={LOG_LEVEL} tanınmıyor — INFO kullanılacak.")

    if warnings:
        print("=" * 60)
        for w in warnings:
            print(f"[config] ⚠️  {w}")
        print("=" * 60)
    else:
        print("[config] ✅ Yapılandırma doğrulandı.")
