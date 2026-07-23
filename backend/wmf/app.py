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
from service.registry import monitor, robot_mgr, syrup
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

    # ── Robot ──
    robot_mgr.start()
    log.info("RobotManager başlatıldı.")
    robot_ok = await asyncio.to_thread(_check_robot)

    # ── Kahve makinesi izleyici ──
    monitor_ok = await _check_monitor()

    # ── Syrup dispenser ──
    syrup_ok = await _check_syrup()

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

def _check_robot() -> bool:
    try:
        robot_mgr._ensure_connected()
        log.info("Robot bağlandı.")
        return True
    except Exception as e:
        log.warning("Robot bağlantısı kurulamadı: %s", e)
        return False


async def _check_monitor() -> bool:
    """
    order_service sipariş öncesi monitor.get_state() çağırıyor;
    başlatılmazsa durum sözlüğü boş kalır ve her sipariş
    "makine çevrimdışı" diye reddedilebilir.
    """
    try:
        await monitor.start()
        log.info("MachineMonitor başlatıldı.")
        return True
    except Exception as e:
        log.warning("MachineMonitor başlatılamadı: %s", e)
        return False


async def _check_syrup() -> bool:
    try:
        result = await syrup.ping()
        ok = bool(result.get("ok"))
        log.info("Syrup Dispenser: %s", "bağlı" if ok else "yanıt yok")
        return ok
    except Exception as e:
        log.warning("Syrup Dispenser bağlantısı kurulamadı: %s", e)
        return False


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
