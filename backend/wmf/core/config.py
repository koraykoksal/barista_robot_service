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
# ROBOT IO HARİTASI
# ─────────────────────────────────────────────
#
# Pin numaraları koda gömülmez: saha kablolaması değiştiğinde .env
# düzenlemek yeterli olsun. Sipariş akışı bu isimleri kullanır,
# çıplak sayıları değil.
#
#   UYGULAMA YAZAR (DO)              ROBOT YAZAR (DI)
#   ───────────────────              ────────────────
#   DO0  bardağı al                  DI9  buz alındı
#   DO7  kahve makinesine yerleştir  DI8  şurup istasyonunda
#   DO2  teslim et                   DI1  makineye yerleştirildi
#                                    DI3  teslim edildi
#
# SysVar (sistem değişkeni) robota siparişin TİPİNİ önceden bildirir:
# robot DO0'ı görüp bardağı aldığında hangi istasyonlara uğrayacağını
# bu değişkenlerden okur.
ROBOT_DO_TAKE_CUP  = _int("ROBOT_DO_TAKE_CUP",  0)   # → bardağı al, başla
ROBOT_DO_PLACE_CUP = _int("ROBOT_DO_PLACE_CUP", 7)   # → şurup bitti, makineye yerleştir
ROBOT_DO_DELIVER   = _int("ROBOT_DO_DELIVER",   2)   # → içecek hazır, teslim et

ROBOT_DI_CUP_PLACED = _int("ROBOT_DI_CUP_PLACED", 1)  # ← makineye yerleştirdim
ROBOT_DI_DELIVERED  = _int("ROBOT_DI_DELIVERED",  3)  # ← teslim ettim
ROBOT_DI_AT_SYRUP   = _int("ROBOT_DI_AT_SYRUP",   8)  # ← şurup istasyonundayım
ROBOT_DI_ICE_TAKEN  = _int("ROBOT_DI_ICE_TAKEN",  9)  # ← buzu aldım

# SysVar id aralığı SDK'da [1~20]; 0 GEÇERSİZDİR (sdk/Robot.py → SetSysVarValue).
# Robot programındaki "SysVar0/SysVar1" adlandırması burada 1 ve 2'ye eşlenir.
ROBOT_SYSVAR_SYRUP    = _int("ROBOT_SYSVAR_SYRUP",    1)   # 1 → şurup istasyonuna uğra
ROBOT_SYSVAR_ICE      = _int("ROBOT_SYSVAR_ICE",      2)   # 1 → buz istasyonuna uğra
ROBOT_SYSVAR_ICE_TYPE = _int("ROBOT_SYSVAR_ICE_TYPE", 3)   # 0 → buz, 1 → buz + su

# Buz istasyonunda ne alınacağı (SysVar3 değeri)
ICE_TYPE_ICE       = 0   # yalnızca buz
ICE_TYPE_ICE_WATER = 1   # buz + su

# SysVar yazımı ile DO yazımı arasındaki bekleme (saniye).
#
# NEDEN: SysVar XML-RPC üzerinden, DO ise ayrı bir çağrıyla gider.
# Robot DO0'ı görüp harekete başladığında SysVar değerinin denetleyicide
# çoktan oturmuş olması gerekir; aksi halde robot eski (veya sıfır)
# değeri okuyup yanlış istasyona gider.
ROBOT_SYSVAR_SETTLE = _float("ROBOT_SYSVAR_SETTLE", 0.5)

# Buz istasyonu robotun kendi rölesiyle tetiklenir; uygulama yalnızca
# DI ile "buz alındı" onayını bekler. Bu süre robotun buz alma
# hareketini kapsamalı.
ICE_WAIT_TIMEOUT   = _float("ICE_WAIT_TIMEOUT",   90.0)
SYRUP_WAIT_TIMEOUT = _float("SYRUP_WAIT_TIMEOUT", 90.0)


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

# Kanal başına akıtılacak varsayılan doz. Kanalın kendi dose_ml değeri
# (syrup_stock tablosu, /stock sayfasından düzenlenir) doluysa o kullanılır;
# bu değer yalnızca yeni kanal oluşturulurken başlangıç noktasıdır.
#
# ⚠️  Bu değeri sonradan değiştirmek MEVCUT kanalları güncellemez —
# doz veritabanında kanal başına tutulur. Zaten oluşmuş kanalların
# dozunu /stock sayfasındaki "Doz (ml)" alanından değiştirin.
SYRUP_DEFAULT_DOSE_ML = _float("SYRUP_DEFAULT_DOSE_ML", 18.0)


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

    # SysVar id'si SDK'da [1~20]. 0 veya 21+ verilirse SetSysVarValue hata
    # döner ve şuruplu/buzlu siparişler daha ilk adımda düşer.
    _sysvars = {
        "ROBOT_SYSVAR_SYRUP":    ROBOT_SYSVAR_SYRUP,
        "ROBOT_SYSVAR_ICE":      ROBOT_SYSVAR_ICE,
        "ROBOT_SYSVAR_ICE_TYPE": ROBOT_SYSVAR_ICE_TYPE,
    }
    for label, value in _sysvars.items():
        if not 1 <= value <= 20:
            warnings.append(
                f"{label}={value} — SDK sistem değişkeni aralığı [1~20]. "
                "Bu değerle bayrak yazılamaz."
            )

    if len(set(_sysvars.values())) != len(_sysvars):
        warnings.append(
            f"SysVar numaraları çakışıyor: {_sysvars} — "
            "robot bayrakları birbirinden ayırt edemez."
        )

    _do_pins = [ROBOT_DO_TAKE_CUP, ROBOT_DO_PLACE_CUP, ROBOT_DO_DELIVER]
    if len(set(_do_pins)) != len(_do_pins):
        warnings.append(f"Robot DO pinleri çakışıyor: {_do_pins}")

    _di_pins = [ROBOT_DI_CUP_PLACED, ROBOT_DI_DELIVERED,
                ROBOT_DI_AT_SYRUP, ROBOT_DI_ICE_TAKEN]
    if len(set(_di_pins)) != len(_di_pins):
        warnings.append(f"Robot DI pinleri çakışıyor: {_di_pins}")

    if warnings:
        print("=" * 60)
        for w in warnings:
            print(f"[config] ⚠️  {w}")
        print("=" * 60)
    else:
        print("[config] ✅ Yapılandırma doğrulandı.")
