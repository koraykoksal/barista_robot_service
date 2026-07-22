"""
app.py — uygulama girişi

Görevi yalnızca:
  • FastAPI uygulamasını oluşturmak
  • CORS tanımlamak
  • lifespan (startup / shutdown) yönetmek
  • router'ları bağlamak

KATMANLAR:
  core/     → yapılandırma, veri, saf yardımcılar
  service/  → cihaz istemcileri ve iş mantığı
  route/    → HTTP uçları

  Bağımlılık yönü tek yönlüdür:  route → service → core
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config
from core.database import close_db, init_db
from core.security import admin_protection_enabled
from core.version import __version__
from route import machine as machine_route
from route import order as order_route
from route import stock as stock_route
from route import syrup as syrup_route
from service.registry import monitor, robot_mgr, syrup


# ══════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(f"[STARTUP] WMF Coffee Service v{__version__} başlatılıyor...")
    print("=" * 60)

    config.validate()

    robot_mgr.start()
    print("[STARTUP] RobotManager başlatıldı.")

    robot_ok   = await asyncio.to_thread(_check_robot)
    monitor_ok = await _check_monitor()
    syrup_ok   = await _check_syrup()

    try:
        print("[STARTUP] MongoDB başlatılıyor...")
        await init_db()
        db_ok = True
    except Exception as e:
        print(f"[STARTUP] ⚠️  MongoDB başlatma hatası (devam): {e}")
        db_ok = False

    print("=" * 60)
    print(f"[STARTUP] Robot:{robot_ok} | Monitor:{monitor_ok} | Syrup:{syrup_ok} | DB:{db_ok}")
    print(f"[STARTUP] Yönetici koruması: {'AÇIK' if admin_protection_enabled() else 'KAPALI ⚠️'}")
    print(f"[STARTUP] İzinli origin'ler: {config.CORS_ORIGINS}")
    print("=" * 60)

    yield   # ← uygulama burada çalışır

    # ══ SHUTDOWN ══════════════════════════════
    print("[SHUTDOWN] Servisler durduruluyor...")

    # Aktif sipariş varsa iptal et
    try:
        async with order_route._active_task_lock:
            task = order_route._active_task
            if task and not task.done():
                print("[SHUTDOWN] ⚠️  Aktif sipariş iptal ediliyor...")
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
    except Exception as e:
        print(f"[SHUTDOWN] Task iptal hatası (yoksayıldı): {e}")

    try:
        robot_mgr.stop()
        print("[SHUTDOWN] RobotManager durduruldu.")
    except Exception as e:
        print(f"[SHUTDOWN] RobotManager hatası: {e}")

    try:
        await monitor.stop()
        print("[SHUTDOWN] MachineMonitor durduruldu.")
    except Exception as e:
        print(f"[SHUTDOWN] MachineMonitor hatası: {e}")

    try:
        await close_db()
    except Exception as e:
        print(f"[SHUTDOWN] MongoDB hatası: {e}")

    print("[SHUTDOWN] ✅ Temiz çıkış.")


# ══════════════════════════════════════════════
# STARTUP YARDIMCILARI
# ══════════════════════════════════════════════

def _check_robot() -> bool:
    try:
        robot_mgr._ensure_connected()
        print("[STARTUP] ✅ Robot bağlandı.")
        return True
    except Exception as e:
        print(f"[STARTUP] ❌ Robot bağlantısı: {e}")
        return False


async def _check_monitor() -> bool:
    """
    MachineMonitor önceki sürümde yorum satırındaydı, ancak
    order_service.py sipariş öncesi monitor.get_state() çağırıyor.
    Başlatılmazsa durum sözlüğü boş kalır ve check_monitor_state
    her siparişi "makine çevrimdışı" diye reddedebilir.
    """
    try:
        await monitor.start()
        print("[STARTUP] ✅ MachineMonitor başlatıldı.")
        return True
    except Exception as e:
        print(f"[STARTUP] ❌ MachineMonitor: {e}")
        return False


async def _check_syrup() -> bool:
    try:
        result = await syrup.ping()
        ok = bool(result.get("ok"))
        print(f"[STARTUP] {'✅' if ok else '❌'} Syrup Dispenser.")
        return ok
    except Exception as e:
        print(f"[STARTUP] ❌ Syrup Dispenser: {e}")
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
