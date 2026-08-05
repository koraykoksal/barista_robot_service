"""
routers/syrup.py

LogoSurup dispenser endpoint'leri:

  GET  /syrup/ping                      — CMD:SYS:PING bağlantı testi
  GET  /syrup/motors                    — --list-motors  (EVT:IO:PRESENCE)
  GET  /syrup/presence/stream           — --watch-presence (SSE push stream)
  POST /syrup/dispense                  — --motor N --ml X  /  --ch N --ml X
  GET  /syrup/config                    — kanal → şurup adı haritası
  PUT  /syrup/config/{channel}          — kanal adı güncelle
  GET  /syrup/recipes                   — içecek → kanal & miktar haritası
  PUT  /syrup/recipes/{button_number}   — içecek syrup tarifi kaydet
  DELETE /syrup/recipes/{button_number} — içecek syrup tarifini sil
"""

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from service.registry     import syrup
from service.syrup_service import SyrupDeviceError
from service import syrup_recipes as syrup_recipes_store

router = APIRouter(prefix="/syrup", tags=["syrup"])


# ─────────────────────────────────────────────
# MODELLER
# ─────────────────────────────────────────────

class DispenseRequest(BaseModel):
    channel : Optional[int]   = Field(None, ge=1, le=8,
        description="Kanal numarası (1–8) — channel veya motor alanından biri zorunlu")
    motor   : Optional[int]   = Field(None, ge=1, le=8,
        description="Motor numarası (1–8) — channel ile aynı anlama gelir")
    ml      : Optional[float] = Field(None, gt=0,
        description="mL cinsinden miktar")
    qty_ml  : Optional[float] = Field(None, gt=0,
        description="mL cinsinden miktar (ml ile aynı)")
    timeout : Optional[float] = Field(None, gt=0,
        description="İşlem timeout (s)")

    def resolved_channel(self) -> int:
        ch = self.channel or self.motor
        if not ch:
            raise ValueError("'channel' veya 'motor' alanından biri zorunludur.")
        return ch

    def resolved_qty(self) -> float:
        qty = self.ml or self.qty_ml
        if not qty:
            raise ValueError("'ml' veya 'qty_ml' alanından biri zorunludur.")
        return qty


class ChannelConfigRequest(BaseModel):
    name        : str = Field(..., description="Şurup adı (ör. 'Vanilya')")
    description : str = Field("",  description="Açıklama")
    color       : str = Field("",  description="Renk kodu (ör. '#FFD700')")


class SyrupRecipeRequest(BaseModel):
    channel : int   = Field(..., ge=1, le=8, description="Kanal / motor numarası (1–8)")
    ml      : float = Field(..., gt=0,       description="mL cinsinden miktar")
    note    : str   = Field("",              description="Not")


# ─────────────────────────────────────────────
# IN-MEMORY KONFIG
# ─────────────────────────────────────────────

# Kanal yapılandırması ve içecek tarifleri artık service katmanında.
# Önceden burada, rota dosyasının içinde duruyordu ve order_service.py
# "from routers.syrup import get_syrup_recipe" ile buraya uzanıyordu —
# yani bir servis, bir rotadan veri okuyordu. Sözlükler referansla
# paylaşıldığı için aşağıdaki mevcut atama/pop işlemleri aynen çalışır.
_channel_config = syrup_recipes_store.channel_config
_syrup_recipes  = syrup_recipes_store.syrup_recipes

# watch-presence için aktif stop event
_presence_stop: Optional[asyncio.Event] = None


# ─────────────────────────────────────────────
# PING  — CMD:SYS:PING
# ─────────────────────────────────────────────

@router.get("/ping", status_code=200)
async def syrup_ping():
    """
    LogoSurup cihazına CMD:SYS:PING gönderir.
    Cihaz offline olsa da HTTP 200 döner (ok=false ile bildirilir).
    """
    try:
        return await syrup.ping()
    except Exception as e:
        return {"ok": False, "host": syrup.host, "port": syrup.port, "error": str(e)}


# ─────────────────────────────────────────────
# LIST MOTORS  — --list-motors
# ─────────────────────────────────────────────

@router.get("/motors", status_code=200)
async def syrup_list_motors():
    """
    Tüm motorların (kanalların) fiziksel bağlantı durumunu döner.

    CLI karşılığı: --list-motors
    Protokol: EVT:IO:PRESENCE:CH01=1,CH02=0,...

    Yanıt örneği:
        {
          "motors": [
            { "motor": 1, "channel": "CH01", "connected": true,  "name": "Vanilya" },
            { "motor": 2, "channel": "CH02", "connected": false, "name": "Karamel" },
            ...
          ]
        }
    """
    result = await syrup.list_motors()

    if not result.get("ok"):
        raise HTTPException(
            status_code=503,
            detail={
                "source" : "syrup_connection",
                "error"  : result.get("error", "Bağlantı kurulamadı"),
                "host"   : syrup.host,
                "port"   : syrup.port,
            }
        )

    # Kanal config ile zenginleştir
    for m in result.get("motors", []):
        ch   = m.get("motor")
        conf = _channel_config.get(ch, {})
        m["name"]        = conf.get("name", f"Motor {ch}")
        m["description"] = conf.get("description", "")
        m["color"]       = conf.get("color", "")

    return result


# ─────────────────────────────────────────────
# WATCH PRESENCE  — --watch-presence  (SSE)
# ─────────────────────────────────────────────

@router.get("/presence/stream")
async def syrup_watch_presence():
    """
    Motor tak/çıkar olaylarını Server-Sent Events (SSE) ile akıtır.

    CLI karşılığı: --watch-presence
    Protokol: Kalıcı TCP bağlantısı — EVT:IO:PRESENCE ve EVT:IO:CH=* dinlenir.

    Tarayıcıdan kullanım:
        const es = new EventSource('/syrup/presence/stream');
        es.onmessage = e => console.log(JSON.parse(e.data));

    Gelen event tipleri:
        { event: "presence",      channels: {...}, motors: [...] }
        { event: "channel_state", channel: 1, state: true }
        { event: "error",         error_code: "E405", description: "..." }
        { event: "connection_error", error: "...", reconnect_in: 2.0 }
    """
    stop = asyncio.Event()

    async def event_generator():
        try:
            async for evt in syrup.watch_presence(stop_event=stop):
                # Kanal config ile zenginleştir
                if evt.get("event") == "presence" and "motors" in evt:
                    for m in evt["motors"]:
                        ch = m.get("motor")
                        if ch:
                            conf        = _channel_config.get(ch, {})
                            m["name"]   = conf.get("name", f"Motor {ch}")
                            m["color"]  = conf.get("color", "")
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            stop.set()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control"            : "no-cache",
            "X-Accel-Buffering"        : "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────────────────────────
# DISPENSE  — --motor N --ml X  /  --ch N --ml X
# ─────────────────────────────────────────────

@router.post("/dispense", status_code=200)
async def syrup_dispense(req: DispenseRequest):
    """
    Belirtilen motordan (kanaldan) belirtilen mL şurup akıtır.

    CLI karşılığı:
      --motor 1 --ml 5    veya   --ch 1 --ml 5

    Protokol:
      → CMD:DISP:CH=01:QTY=5:UNIT=ML
      ← RSP:DISP:ACCEPT:CH=01:QTY=5.000:UNIT=ML:DUR_MS=700:DIR=F
      ← EVT:DISP:COMPLETE:CH=01

    İstek örnekleri:
        { "motor": 1, "ml": 5.0 }
        { "channel": 1, "qty_ml": 5.0 }
        { "motor": 3, "ml": 12.5, "timeout": 20 }
    """
    try:
        channel = req.resolved_channel()
        qty_ml  = req.resolved_qty()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result = await syrup.dispense(channel, qty_ml, req.timeout)
        # Kanal adını ekle
        result["motor"]        = channel
        result["channel_name"] = _channel_config.get(channel, {}).get("name", f"Motor {channel}")
        return result

    except SyrupDeviceError as e:
        p = e.parsed
        raise HTTPException(
            status_code=p["http_status"],
            detail={
                "source"     : "syrup_device",
                "error_code" : p["error_code"],
                "error_msg"  : p["error_msg"],
                "description": p["description"],
                "raw"        : p["raw"],
            }
        )
    except TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail={
                "source"     : "syrup_timeout",
                "error_code" : "TIMEOUT",
                "description": str(e),
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (ConnectionError, OSError) as e:
        # Cihaza hiç ulaşılamadı — /syrup/motors ile aynı kodu döndür.
        raise HTTPException(
            status_code=503,
            detail={"source": "syrup_connection", "error_code": "UNREACHABLE",
                    "description": str(e), "host": syrup.host, "port": syrup.port}
        )
    except Exception as e:
        # "bağlantı reddedildi" gibi mesajlar OSError sarmalayabilir;
        # metinden de yakala ki 500 yerine anlaşılır 503 dönsün.
        msg = str(e)
        if "bağlan" in msg.lower() or "connect" in msg.lower() or "refused" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail={"source": "syrup_connection", "error_code": "UNREACHABLE",
                        "description": msg, "host": syrup.host, "port": syrup.port}
            )
        raise HTTPException(
            status_code=500,
            detail={"source": "syrup_internal", "error_code": "INTERNAL", "description": msg}
        )


# ─────────────────────────────────────────────
# KANAL KONFİGÜRASYONU
# ─────────────────────────────────────────────

@router.get("/config", status_code=200)
async def syrup_config_get():
    """Tüm motor → şurup adı atamasını döner."""
    return {
        "motors": {
            str(ch): {"motor": ch, **_channel_config.get(ch, {})}
            for ch in range(1, 9)
        }
    }


@router.put("/config/{channel}", status_code=200)
async def syrup_config_update(channel: int, req: ChannelConfigRequest):
    """
    Bir motorun (kanalın) şurup adını ve açıklamasını günceller.

    PUT /syrup/config/1
    { "name": "Vanilya", "description": "Klasik vanilya", "color": "#FFD700" }
    """
    if not 1 <= channel <= 8:
        raise HTTPException(status_code=422, detail="Motor numarası 1–8 arası olmalı.")
    _channel_config[channel] = {
        "name"       : req.name,
        "description": req.description,
        "color"      : req.color,
    }
    return {"ok": True, "motor": channel, "config": _channel_config[channel]}


# ─────────────────────────────────────────────
# SYRUP TARİFLERİ
# ─────────────────────────────────────────────

@router.get("/recipes", status_code=200)
async def syrup_recipes_get():
    """
    Tüm içecek → syrup tarifi atamasını döner.
    button_number bazlı: hangi içecek hangi motordan kaç mL şurup alır.
    """
    enriched = {}
    for btn, recipe in _syrup_recipes.items():
        ch = recipe.get("channel")
        enriched[str(btn)] = {
            **recipe,
            "motor_name": _channel_config.get(ch, {}).get("name", "") if ch else "",
        }
    return {"recipes": enriched, "count": len(enriched)}


@router.put("/recipes/{button_number}", status_code=200)
async def syrup_recipe_set(button_number: int, req: SyrupRecipeRequest):
    """
    Bir içeceğin syrup tarifini ayarlar.

    PUT /syrup/recipes/3
    { "channel": 1, "ml": 10.0, "note": "Vanilya latte" }

    Bu tarif sipariş akışında (order_service.py) otomatik kullanılır:
    DI1=True (robot bardağı aldı) → syrup.dispense() → startBeverage
    """
    _syrup_recipes[button_number] = {
        "channel": req.channel,
        "ml"     : req.ml,
        "note"   : req.note,
    }
    return {
        "ok"           : True,
        "button_number": button_number,
        "recipe"       : _syrup_recipes[button_number],
        "motor_name"   : _channel_config.get(req.channel, {}).get("name", ""),
    }


@router.delete("/recipes/{button_number}", status_code=200)
async def syrup_recipe_delete(button_number: int):
    """İçecek syrup tarifini kaldırır."""
    if button_number not in _syrup_recipes:
        raise HTTPException(
            status_code=404,
            detail=f"button_number={button_number} için syrup tarifi yok."
        )
    removed = _syrup_recipes.pop(button_number)
    return {"ok": True, "button_number": button_number, "removed": removed}
