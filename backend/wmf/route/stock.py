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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from service import stock_service

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


@router.put("/stock/refill", status_code=200)
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


@router.put("/stock/thresholds", status_code=200)
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
