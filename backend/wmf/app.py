"""
app.py  —  v2 modüler yapı

Bu dosya artık sadece:
  • FastAPI uygulaması oluşturur
  • CORS tanımlar
  • lifespan (startup / shutdown) yönetir
  • Router'ları bağlar

İş mantığı şu dosyalara taşındı:
  config.py         → sabitler (IP, port, token, timer, ...)
  services.py       → singleton servis nesneleri (robot, coffee, monitor, ...)
  order_utils.py    → loglama, timer, hata açıklama, sinyal temizleme
  order_service.py  → tüm sipariş akışı (14 adım)
  routers/order.py  → /order_standart, /order/status, /check_beverage, ...
  routers/machine.py→ /machine/status, /machine/info, /read_do, ...
  routers/stock.py  → /stock/status, /stock/refill, /stock/thresholds, ...
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import __version__
from services  import robot_mgr, coffee, monitor,syrup
from database  import init_db, close_db
from routers   import order as order_router
from routers   import machine as machine_router
from routers   import stock as stock_router
from routers   import syrup as syrup_router


# ══════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(f"[STARTUP] WMF Coffee Service v{__version__.__version__} başlatılıyor...")
    print("=" * 60)

    # Robot
    robot_mgr.start()
    print("[STARTUP] RobotManager başlatıldı.")

    robot_ok = await asyncio.to_thread(_check_robot)
    if not robot_ok:
        print("[STARTUP] ⚠️  Robot bağlantısı kurulamadı — uygulama yine de başlatılıyor.")

    # Kahve makinesi WS testi
    # coffee_ok = await _check_coffee_ws()
    # if not coffee_ok:
    #     print("[STARTUP] ⚠️  Kahve makinesi WS bağlantısı kurulamadı — uygulama yine de başlatılıyor.")

    # MachineMonitor
    # await monitor.start()
    # print("[STARTUP] ✅ MachineMonitor başlatıldı.")


    # Surup Control
    syrup_ok = await _check_syrup()
    if not syrup_ok:
        print("[STARTUP] ⚠️  Syrup Dispenser bağlantısı kurulamadı — uygulama yine de başlatılıyor.")


    # MongoDB
    try:
        print("[STARTUP] MongoDB başlatılıyor...")
        await init_db()
    except Exception as e:
        print(f"[STARTUP] ⚠️  MongoDB başlatma hatası (devam): {e}")

    # print("=" * 60)
    # print(f"[STARTUP] ✅ Hazır.  Robot:{robot_ok} | Kahve:{coffee_ok}")
    # print("=" * 60)

    yield   # ← uygulama burada çalışır

    # ── Shutdown ──────────────────────────────
    print("[SHUTDOWN] Servisler durduruluyor...")

    # Aktif sipariş task iptal
    from routers.order import _active_task, _active_task_lock
    try:
        async with _active_task_lock:
            if _active_task and not _active_task.done():
                print("[SHUTDOWN] ⚠️  Aktif sipariş iptal ediliyor...")
                _active_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(_active_task), timeout=5.0)
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
        print("[SHUTDOWN] MongoDB kapatıldı.")
    except Exception as e:
        print(f"[SHUTDOWN] MongoDB hatası: {e}")

    print("[SHUTDOWN] ✅ Temiz çıkış.")


# ══════════════════════════════════════════════
# STARTUP YARDIMCILARI
# ══════════════════════════════════════════════

def _check_robot() -> bool:
    try:
        robot_mgr._ensure_connected()
        print("=" * 60)
        print(f"[STARTUP] ✅ Robot bağlandı.")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"[STARTUP] ❌ Robot bağlantısı: {e}")
        return False


async def _check_coffee_ws() -> bool:
    try:
        result = await coffee.connect_test()
        if result.get("ok"):
            print("=" * 60)
            print(f"[STARTUP] ✅ Kahve makinesi WS bağlandı.")
            print("=" * 60)
        return bool(result.get("ok"))
    except Exception as e:
        print(f"[STARTUP] ❌ Kahve makinesi WS: {e}")
        return False
    
async def _check_syrup() -> bool:
    try:
        result = await syrup.ping()
        if result.get("ok"):
            print("=" * 60)
            print(f"[STARTUP] ✅ Syrup Dispenser bağlantısı OK.")
            print("=" * 60)
        return bool(result.get("ok"))
    except Exception as e:
        print(f"❌ Syrup Dispenser : {e}")
        return False


# ══════════════════════════════════════════════
# UYGULAMA
# ══════════════════════════════════════════════

app = FastAPI(
    title   = "WMF Coffee Service API",
    version = __version__.__version__,
    lifespan= lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers     = ["*"],
    expose_headers    = ["*"],
)


# ══════════════════════════════════════════════
# ROUTER BAĞLANTILARI
# ══════════════════════════════════════════════

app.include_router(order_router.router)
app.include_router(machine_router.router)
app.include_router(stock_router.router)
app.include_router(syrup_router.router)


# ══════════════════════════════════════════════
# KÖKK ENDPOINT
# ══════════════════════════════════════════════

@app.get("/", status_code=200)
async def root():
    return {
        "response": "Coffee Service is running.",
        "version" : __version__.__version__,
    }
