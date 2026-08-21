"""
app.py — uygulama girişi

Görevi yalnızca:
  • loglamayı kurmak
  • FastAPI uygulamasını oluşturmak
  • CORS tanımlamak
  • lifespan (startup / shutdown) yönetmek
  • router'ları bağlamak

KATMANLAR:
  core/     → yapılandırma, veri (SQLite + MongoDB), loglama, saf yardımcılar
  service/  → cihaz istemcileri, iş mantığı, senkronizasyon
  route/    → HTTP uçları

  Bağımlılık yönü tek yönlüdür:  route → service → core

VERİ KATMANI:
  Yazmalar yerel SQLite'a senkron gider; MongoDB'ye aktarım arka
  planda kuyruk üzerinden yapılır. Böylece internet koptuğunda kiosk
  çalışmaya devam eder ve hiçbir kayıt kaybolmaz.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config, sqlite_store
from core.applog import get_logger, setup_logging
from core.database import close_db, init_db
from core.security import admin_protection_enabled
from core.version import __version__
from route import machine as machine_route
from route import order as order_route
from route import stock as stock_route
from route import syrup as syrup_route
from service.registry import coffee, monitor, robot_mgr, syrup
from service.sync_service import bootstrap as sync_bootstrap
from service.sync_service import sync

# Loglama, diğer her şeyden önce kurulmalı — açılış mesajları da
# dosyaya düşsün.
setup_logging()
log = get_logger("app")


# ══════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 58)
    log.info("WMF Coffee Service v%s başlatılıyor...", __version__)
    log.info("=" * 58)

    config.validate()

    # ── Yerel veritabanı (her koşulda çalışmalı) ──
    try:
        boot = await sync_bootstrap()
        log.info("SQLite hazır (yeni=%s, başlangıç=%s, bekleyen kayıt=%d).",
                 boot["fresh"], boot["source"], boot["pending"])
        db_ok = True
    except Exception as e:
        log.critical("SQLite başlatılamadı: %s", e, exc_info=True)
        db_ok = False

    # ── MongoDB (isteğe bağlı; yoksa yerel devam eder) ──
    mongo_ok = False
    if config.MONGO_ENABLED:
        try:
            mongo_ok = await init_db()
        except Exception as e:
            log.warning("MongoDB başlatma hatası (yoksayıldı): %s", e)
    else:
        log.warning("MONGO_ENABLED=false — yalnızca yerel SQLite kullanılacak.")

    await sync.start()

    # ── Kahve makinesi izleyici ──
    monitor_ok = await _check_monitor()

    # ── Syrup dispenser ──
    # Robottan ÖNCE çalışır: robot bağlantısı arka planda sürekli
    # yeniden denendiği için, syrup kontrolünü onun arkasına koymak
    # syrup loglarını geciktiriyordu.
    syrup_ok = await _check_syrup()

    # ── Robot ──
    # start() bağlantıyı ARKA PLANDA kurar ve koparsa yeniden dener.
    # İlk denemeyi beklemek açılışı ~25 sn asıyordu; artık beklemiyoruz.
    # Robotun hazır olup olmadığını /robot/status ucu bildirir.
    robot_mgr.start()
    log.info("RobotManager arka planda başlatıldı (bağlantı hazır olunca /robot/status bildirir).")

    # Çökme/zorla kapanma sonrası güvenlik ağı — açılışı bloke etmez.
    asyncio.create_task(_reset_robot_signals_when_ready())
    robot_ok = robot_mgr._is_connected_quick() if hasattr(robot_mgr, "_is_connected_quick") else False

    log.info("=" * 58)
    log.info("Hazır. Robot:%s | Monitor:%s | Syrup:%s | SQLite:%s | Mongo:%s",
             robot_ok, monitor_ok, syrup_ok, db_ok, mongo_ok)
    log.info("Yönetici koruması: %s",
             "AÇIK" if admin_protection_enabled() else "KAPALI ⚠️")
    log.info("İzinli origin'ler: %s", config.CORS_ORIGINS)
    log.info("=" * 58)

    yield   # ← uygulama burada çalışır

    # ══ SHUTDOWN ══════════════════════════════
    log.info("Servisler durduruluyor...")

    # Aktif sipariş varsa iptal et
    try:
        async with order_route._active_task_lock:
            task = order_route._active_task
            if task and not task.done():
                log.warning("Aktif sipariş iptal ediliyor...")
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
    except Exception as e:
        log.warning("Sipariş iptal hatası (yoksayıldı): %s", e)

    # Kuyrukta bekleyen kayıtları son bir kez göndermeyi dener
    try:
        await sync.stop()
    except Exception as e:
        log.warning("Senkronizasyon durdurma hatası: %s", e)

    for label, fn in (
        ("RobotManager",   robot_mgr.stop),
        ("MachineMonitor", monitor.stop),
        ("MongoDB",        close_db),
        ("SQLite",         sqlite_store.close),
    ):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                await result
            log.info("%s durduruldu.", label)
        except Exception as e:
            log.warning("%s durdurma hatası: %s", label, e)

    log.info("Temiz çıkış.")


# ══════════════════════════════════════════════
# STARTUP YARDIMCILARI
# ══════════════════════════════════════════════

async def _check_monitor() -> bool:
    """
    Kahve makinesine bağlanır ve açılışta durumunu raporlar.

    order_service sipariş öncesi monitor.get_state() çağırıyor;
    başlatılmazsa durum sözlüğü boş kalır ve her sipariş
    "makine çevrimdışı" diye reddedilebilir.

    Syrup kontrolüyle aynı biçimde özet basar. Önceden yalnızca
    "MachineMonitor başlatıldı" yazıyordu; bağlantının kurulup
    kurulmadığı, hangi adrese gidildiği ve makinede aktif hata olup
    olmadığı log akışında kayboluyordu.

    Bağlantı arka planda kurulduğu için kısa bir süre beklenir; süre
    dolarsa açılış yine de devam eder (monitor denemeyi sürdürür).
    """
    from core.machine_errors import describe_machine_errors

    log.info("─" * 58)
    log.info("☕ Kahve makinesi kontrol ediliyor → %s", monitor.ws_uri)

    try:
        await monitor.start()
    except Exception as e:
        log.warning("☕ MachineMonitor başlatılamadı: %s", e)
        log.info("─" * 58)
        return False

    # Bağlantı _run() içinde kuruluyor — durumun oturması için bekle.
    deadline = asyncio.get_running_loop().time() + 6.0
    state = await monitor.get_state()
    while not state.get("online") and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.25)
        state = await monitor.get_state()

    if not state.get("online"):
        log.warning("☕ Makineye 6 sn içinde bağlanılamadı (%s). "
                    "Arka planda denemeye devam edilecek; /machine/status bildirir.",
                    monitor.ws_uri)
        log.info("─" * 58)
        return False

    log.info("☕ Makine BAĞLI (%s).", monitor.ws_uri)

    # Sipariş akışı checkBeverage/startBeverage için AYRI bir bağlantı
    # açar. Adresler ayrışırsa durum ekranı çalışır görünürken siparişler
    # başka makineye gider — bu yüzden açılışta karşılaştırılır.
    if coffee.ws_uri != monitor.ws_uri:
        log.warning("☕ ⚠️  Sipariş adresi ile izleme adresi FARKLI: "
                    "sipariş=%s izleme=%s", coffee.ws_uri, monitor.ws_uri)
    if not coffee.ws_token:
        log.warning("☕ COFFEE_MACHINE_TOKEN boş — makine isteği reddedebilir.")

    blocking = state.get("blocking_errors") or []
    errors   = state.get("errors") or []

    if blocking:
        log.warning("☕ Makinede ENGELLEYİCİ hata var → %s | %s",
                    blocking, describe_machine_errors(blocking))
        log.warning("☕ Bu hata giderilene kadar sipariş ekranı bloke kalır.")
    elif errors:
        log.info("☕ Makinede engelleyici olmayan hata(lar): %s", errors)
    else:
        log.info("☕ Makinede aktif hata yok.")

    log.info("☕ Kontrol tamam ✅")
    log.info("─" * 58)
    return True


async def _reset_robot_signals_when_ready(timeout: float = 60.0) -> None:
    """
    Robot bağlanır bağlanmaz çıkış sinyallerini BİR KEZ sıfırlar.

    NEDEN GEREKLİ:
      Uygulama kapanış işleyicisini çalıştıramadan öldürülebiliyor —
      Ctrl+C'nin süreci doğrudan sonlandırması, --reload'un işçiyi
      öldürmesi, güç kesintisi. Log'da bunun izi var: 21 açılışa karşılık
      yalnızca 12 düzgün kapanış.

      Kapanış çalışmazsa DO sinyalleri robotta ASILI KALIR. Örneğin DO2
      (teslim et) HIGH kalmışsa robot, uygulama yeniden açıldığında bayat
      bir komutla karşılaşır ve bir sonraki sipariş bozulur.

      Sipariş akışı zaten ADIM 0.5'te sıfırlıyor; buradaki kazanç, bir
      sonraki siparişi BEKLEMEDEN temizlemek.

    Robot bağlantısı arka planda kurulduğu için beklenir; süre dolarsa
    sessizce vazgeçilir (robot yoksa sıfırlanacak bir şey de yok).
    """
    from service.order_service import cleanup_signals

    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if await asyncio.to_thread(robot_mgr._is_connected_quick):
                break
            await asyncio.sleep(1.0)
        else:
            log.info("Robot %.0f sn içinde bağlanmadı — açılış sinyal "
                     "sıfırlaması atlandı.", timeout)
            return

        # Çalışan bir siparişin sinyallerini sıfırlamak akışı bozar.
        task = order_route._active_task
        if task and not task.done():
            log.info("Aktif sipariş var — açılış sinyal sıfırlaması atlandı.")
            return

        log.info("🤖 Robot bağlandı — önceki oturumdan kalmış olabilecek "
                 "sinyaller sıfırlanıyor...")
        await cleanup_signals("startup")
        log.info("🤖 Sinyaller temiz.")
    except Exception as e:
        log.warning("Açılış sinyal sıfırlaması yapılamadı (yoksayıldı): %s", e)


async def _check_syrup() -> bool:
    """
    Açılışta şurup sistemiyle haberleşip durumu raporlar:

      1. Cihaz ayakta mı (ping)
      2. Hangi kanallarda pompa fiziksel takılı (presence)
      3. Tanımlı tariflerin kanalları takılı ve yeterli mi

    Her koşulda konsola/loga özet basar. Sorun bulsa da açılışı
    engellemez — kahve tarafı şurupsuz çalışabilir.

    Cihaza ulaşılamazsa SYRUP_TIMEOUT (varsayılan 15 sn) boyunca
    beklememek için kontrol kısa bir zaman aşımıyla sarılır; açılış
    asılı kalmaz.
    """
    from service.syrup_recipes import syrup_recipes, channel_name
    from service import stock_service

    log.info("─" * 58)
    log.info("🧴 Syrup sistemi kontrol ediliyor → %s:%s", syrup.host, syrup.port)

    # ── 1) Ping ──
    # Açılışı asmamak için en fazla ~6 sn bekle.
    try:
        pong = await asyncio.wait_for(syrup.ping(), timeout=6.0)
        ok = bool(pong.get("ok"))
    except asyncio.TimeoutError:
        log.warning("🧴 Syrup: cihaz %s:%s yanıt vermedi (zaman aşımı). "
                    "Şuruplu içecekler denenmeyecek.", syrup.host, syrup.port)
        log.info("─" * 58)
        return False
    except Exception as e:
        log.warning("🧴 Syrup: cihaza ulaşılamadı (%s). "
                    "Şuruplu içecekler denenmeyecek.", e)
        log.info("─" * 58)
        return False

    if not ok:
        log.warning("🧴 Syrup: PING yanıtı yok — cihaz kapalı veya meşgul olabilir.")
        log.info("─" * 58)
        return False

    log.info("🧴 Syrup: cihaz AYAKTA (ping ok).")

    # ── 2) Presence — hangi kanallar takılı ──
    connected = {}
    try:
        motors = await asyncio.wait_for(syrup.list_motors(), timeout=6.0)
        connected = {m["motor"]: m["connected"] for m in motors.get("motors", [])}
        takili = [ch for ch, c in connected.items() if c]
        log.info("🧴 Syrup: takılı kanallar → %s", takili or "(hiçbiri)")
    except asyncio.TimeoutError:
        log.warning("🧴 Syrup: kanal durumu zaman aşımına uğradı.")
    except Exception as e:
        log.warning("🧴 Syrup: kanal durumu okunamadı (%s).", e)

    # ── 3) Tanımlı tariflerin kanalları sağlıklı mı ──
    try:
        syrup_stock = {row["channel"]: row for row in await stock_service.get_syrup_stock()}
    except Exception:
        syrup_stock = {}

    # Stok özeti — kaç kanal düşük
    low = [r for r in syrup_stock.values() if float(r["ml"]) < float(r["threshold"])]
    if low:
        for r in low:
            log.warning("🧴 Syrup: kanal %d (%s) eşiğin ALTINDA — %.0f/%.0f ml. "
                        "Bu kanalı kullanan içecekler engellenecek.",
                        r["channel"], r.get("name"), float(r["ml"]), float(r["threshold"]))
    else:
        log.info("🧴 Syrup: tüm kanal stokları eşiğin üstünde.")

    # Tarifi olan içeceklerin kanalları takılı mı
    recipe_count = len(syrup_recipes or {})
    if recipe_count:
        for btn, recipe in syrup_recipes.items():
            ch = recipe.get("channel")
            name = channel_name(ch)
            if ch in connected and not connected[ch]:
                log.warning("🧴 Syrup: buton %s → '%s' tarifi kanal %d kullanıyor "
                            "ama pompa TAKILI DEĞİL.", btn, name, ch)
        log.info("🧴 Syrup: %d içecek tarifi tanımlı.", recipe_count)
    else:
        log.info("🧴 Syrup: tanımlı içecek tarifi yok (şurup opsiyonel).")

    log.info("🧴 Syrup: kontrol tamam ✅")
    log.info("─" * 58)
    return True


# ══════════════════════════════════════════════
# UYGULAMA
# ══════════════════════════════════════════════

app = FastAPI(
    title    = "WMF Coffee Service API",
    version  = __version__,
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = config.CORS_ORIGINS,
    allow_credentials = False,
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers     = ["Content-Type", "X-Admin-Token"],
)

app.include_router(order_route.router)
app.include_router(machine_route.router)
app.include_router(stock_route.router)
app.include_router(syrup_route.router)


@app.get("/", status_code=200)
async def root():
    """Sağlık kontrolü — Docker HEALTHCHECK ve kiosk bu ucu kullanır."""
    return {
        "response"       : "Coffee Service is running.",
        "version"        : __version__,
        "admin_protected": admin_protection_enabled(),
    }
