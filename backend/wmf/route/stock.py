"""
routers/stock.py

Stok yönetimi endpoint'leri:
  GET  /stock/status
  PUT  /stock/refill
  PUT  /stock/thresholds
  GET  /stock/logs/orders
  GET  /stock/logs/refills
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.security import require_admin
from service import stock_service
from service.sync_service import sync

router = APIRouter()


# ─────────────────────────────────────────────
# MODELLER
# ─────────────────────────────────────────────

class RefillRequest(BaseModel):
    coffee_g : Optional[float] = None
    milk_ml  : Optional[float] = None
    choc_g   : Optional[float] = None
    cups     : Optional[int]   = None
    note     : str             = ""


class ThresholdRequest(BaseModel):
    coffee_g : Optional[float] = None
    milk_ml  : Optional[float] = None
    choc_g   : Optional[float] = None
    cups     : Optional[int]   = None


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

class SyrupRefillRequest(BaseModel):
    ml        : Optional[float] = None    # yeniden yazılır (eklenmez)
    threshold : Optional[float] = None
    capacity  : Optional[float] = None
    dose_ml   : Optional[float] = None    # sipariş başına akıtılacak miktar
    name      : Optional[str]   = None


@router.get("/stock/syrup", status_code=200)
async def stock_syrup_list():
    """Tüm şurup kanallarının stok durumu."""
    return {"channels": await stock_service.get_syrup_stock()}


@router.put("/stock/syrup/{channel}", status_code=200,
            dependencies=[Depends(require_admin)])
async def stock_syrup_refill(channel: int, req: SyrupRefillRequest):
    """
    Bir şurup kanalını günceller. ml YENİDEN YAZILIR (eklenmez).
    """
    if channel < 1 or channel > 8:
        raise HTTPException(status_code=422, detail="Kanal 1–8 aralığında olmalı.")
    try:
        return await stock_service.refill_syrup(
            channel, ml=req.ml, threshold=req.threshold,
            capacity=req.capacity, name=req.name, dose_ml=req.dose_ml,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/stock/status", status_code=200)
async def stock_status():
    """
    Güncel stok + eşik analizi.
    Frontend 5sn polling ile çağırır.
    Yanıtta: all_disabled / milk_disabled / choc_disabled / alerts
    """
    try:
        return await stock_service.get_stock_status()
    except Exception as e:
        print(f"[STOCK] /stock/status hata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Yazma uçları X-Admin-Token ile korunur.
#
# Bu koruma Aşama 0'da eklenmişti ama uçlara TAKILMAMIŞTI: arayüz
# başlığı gönderiyordu, backend hiç bakmıyordu. Yani ağdaki herhangi
# bir cihaz stok kayıtlarını sıfırlayabiliyordu.
#
# ADMIN_TOKEN .env'de boşsa koruma devre dışı kalır ve açılışta uyarı
# basılır (bkz. core/config.validate).
@router.put("/stock/refill", status_code=200, dependencies=[Depends(require_admin)])
async def stock_refill(req: RefillRequest):
    """Stok değerlerini sıfırdan ayarlar (örn. coffee_g=200 → 200g'a set et)."""
    try:
        result = await stock_service.refill_stock(
            coffee_g=req.coffee_g, milk_ml=req.milk_ml,
            choc_g=req.choc_g, cups=req.cups, note=req.note,
        )
        print(f"[STOCK] Stok yenilendi: {result['refilled']}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[STOCK] /stock/refill hata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/stock/thresholds", status_code=200, dependencies=[Depends(require_admin)])
async def stock_thresholds(req: ThresholdRequest):
    """Uyarı eşiklerini günceller."""
    try:
        return await stock_service.update_thresholds(
            coffee_g=req.coffee_g, milk_ml=req.milk_ml,
            choc_g=req.choc_g, cups=req.cups,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/logs/orders", status_code=200)
async def stock_order_logs(limit: int = 50):
    """Son N sipariş tüketim logu."""
    try:
        return await stock_service.get_order_logs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/logs/refills", status_code=200)
async def stock_refill_logs(limit: int = 20):
    """Son N dolum logu."""
    try:
        return await stock_service.get_refill_logs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/sync", status_code=200)
async def stock_sync_status():
    """
    Yerel kuyruk ve MongoDB bağlantı durumu.

    pending > 0 ve mongo_online = false ise kiosk çevrimdışı çalışıyor
    ve kayıtlar birikiyor demektir — veri kaybı yok, bağlantı gelince
    aktarılacaklar.
    """
    return await sync.status()


@router.post("/stock/sync", status_code=200, dependencies=[Depends(require_admin)])
async def stock_sync_now():
    """Kuyruğu hemen boşaltmayı dener (beklemeden)."""
    try:
        return await sync.drain_once()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Senkronizasyon başarısız: {e}")
