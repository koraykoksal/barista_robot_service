"""
routers/machine.py

Makine bilgisi endpoint'leri:
  GET /machine/status
  GET /machine/info
  GET /machine/diagnostic
  GET /machine/service
  GET /machine/cleaning
  GET /read_do     (debug)
  POST /set_do     (debug)
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.machine_errors import describe_machine_errors
from service.registry import robot_mgr, monitor, machine_info

router = APIRouter()


class SendRequest(BaseModel):
    message: Dict[str, Any]


# ─────────────────────────────────────────────
# MAKİNE DURUMU
# ─────────────────────────────────────────────

@router.get("/machine/status", status_code=200)
async def machine_status():
    """
    MachineMonitor'ın tuttuğu anlık makine durumu.

    Ham hata kodlarına ek olarak okunabilir bir açıklama da döner.
    Önceden yalnızca [68, 75] gibi kod listesi dönüyordu; arayüz bunu
    kullanıcıya gösteremiyordu. Kod→metin tablosu backend'de olduğu
    için çeviriyi de backend yapar — arayüzün ikinci bir kopya tutması
    gerekmez.
    """
    state = await monitor.get_state()

    blocking = state.get("blocking_errors") or []
    errors   = state.get("errors") or []

    state["error_description"] = (
        describe_machine_errors(blocking) if blocking
        else describe_machine_errors(errors) if errors
        else None
    )
    return state


@router.get("/machine/info", status_code=200)
async def machine_info_full():
    """Tam makine bilgisi: diagnostic + service + cleaning."""
    print("[API] GET /machine/info")
    try:
        return await machine_info.get_full_machine_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Makine bilgisi alınamadı: {e}")


@router.get("/machine/diagnostic", status_code=200)
async def machine_diagnostic():
    """Su/buhar kazanı sıcaklığı, basınç, RAM, Flash."""
    try:
        return await machine_info.get_diagnostic()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine/service", status_code=200)
async def machine_service():
    """Bakım sayaçları + öğütücü tipleri."""
    try:
        stats      = await machine_info.get_service_stats()
        portioners = await machine_info.get_portioner_info()
        return {"ok": True, "service": stats, "portioners": portioners}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine/cleaning", status_code=200)
async def machine_cleaning():
    """Temizlik ve durulama takvimi."""
    try:
        return await machine_info.get_all_cleaning_states()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# DEBUG: ROBOT DO/DI
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# ROBOT DURUM & KONTROL
# ─────────────────────────────────────────────

@router.get("/robot/status", status_code=200)
async def robot_status():
    """
    Robotun anlık mod ve çalışma durumu.
    Frontend polling ile can_order flag'ini okur.

    can_order = True  → sipariş verilebilir
    can_order = False → sipariş ekranı pasif
    """
    status = await asyncio.to_thread(robot_mgr.get_robot_status)
    status["robot_ip"] = robot_mgr.robot_ip
    return status


@router.post("/robot/set_auto", status_code=200)
async def robot_set_auto():
    """Robotu otomatik moda geçirir."""
    ok = await asyncio.to_thread(robot_mgr.set_auto_mode_and_wait)
    if not ok:
        raise HTTPException(status_code=503,
            detail="Robot otomatik moda geçiş başarısız veya timeout.")
    return {"ok": True, "message": "Robot otomatik moda geçirildi."}


@router.post("/robot/set_manual", status_code=200)
async def robot_set_manual():
    """Robotu manuel moda geçirir."""
    ok = await asyncio.to_thread(robot_mgr.set_manual_mode)
    if not ok:
        raise HTTPException(status_code=503,
            detail="Robot manuel moda geçiş başarısız veya timeout.")
    return {"ok": True, "message": "Robot manuel moda geçirildi."}


@router.post("/robot/program/run", status_code=200)
async def robot_program_run():
    """Yüklü programı başlatır. Robot otomatik modda olmalı."""
    err = await asyncio.to_thread(robot_mgr.program_run)
    if err != 0:
        raise HTTPException(status_code=500,
            detail=f"ProgramRun başarısız (err={err}).")
    return {"ok": True, "message": "Program başlatıldı.", "sdk_err": err}


@router.post("/robot/program/stop", status_code=200)
async def robot_program_stop():
    """Çalışan programı durdurur."""
    err = await asyncio.to_thread(robot_mgr.program_stop)
    if err != 0:
        raise HTTPException(status_code=500,
            detail=f"ProgramStop başarısız (err={err}).")
    return {"ok": True, "message": "Program durduruldu.", "sdk_err": err}


@router.post("/robot/program/pause", status_code=200)
async def robot_program_pause():
    """Çalışan programı duraklatır."""
    err = await asyncio.to_thread(robot_mgr.program_pause)
    if err != 0:
        raise HTTPException(status_code=500,
            detail=f"ProgramPause başarısız (err={err}).")
    return {"ok": True, "message": "Program duraklatıldı.", "sdk_err": err}


@router.post("/robot/program/resume", status_code=200)
async def robot_program_resume():
    """Duraklatılmış programı devam ettirir."""
    err = await asyncio.to_thread(robot_mgr.program_resume)
    if err != 0:
        raise HTTPException(status_code=500,
            detail=f"ProgramResume başarısız (err={err}).")
    return {"ok": True, "message": "Program devam ettiriliyor.", "sdk_err": err}


# ─────────────────────────────────────────────
# DO / DI OKUMA & YAZMA
# ─────────────────────────────────────────────
# ⚠️  Route sırası: /all endpoint'leri /{id} parametreli route'lardan
# ÖNCE tanımlanmalı. Aksi halde FastAPI "all" stringini int olarak
# parse etmeye çalışır → 422 Unprocessable Entity hatası.
# ─────────────────────────────────────────────


@router.get("/robot/do/all", status_code=200)
async def robot_read_do_all():
    """
    Tüm DO pinlerinin (0–15) mevcut durumunu tek sorguda okur.

    Yanıt:
        pins : dict — { "0": {"value": 0, "label": "LOW"}, "1": ... }
    """
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    pins = {}
    for i in range(16):
        val = await asyncio.to_thread(robot_mgr.read_do_status, i)
        pins[str(i)] = {
            "value": val if val >= 0 else None,
            "label": "HIGH" if val == 1 else ("LOW" if val == 0 else "ERROR"),
        }
    return {"pins": pins}


@router.get("/robot/di/all", status_code=200)
async def robot_read_di_all():
    """
    Sipariş akışında kullanılan DI pinlerinin (0–7) mevcut durumunu okur.

    Yanıt:
        pins : dict — { "0": {"value": 0, "label": "LOW"}, "1": ... }
    """
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    pins = {}
    for i in range(8):
        val = await asyncio.to_thread(robot_mgr.read_di_status, i)
        pins[str(i)] = {
            "value": val if val >= 0 else None,
            "label": "HIGH" if val == 1 else ("LOW" if val == 0 else "ERROR"),
        }
    return {"pins": pins}


@router.get("/robot/do/{do_id}", status_code=200)
async def robot_read_do(do_id: int):
    """
    Belirtilen DO pininin mevcut durumunu okur.

    do_id : 0–15 arası Digital Output pin numarası

    Yanıt:
        do_id  : int — sorgulan pin
        value  : int — 0 (LOW) veya 1 (HIGH)
        label  : str — "LOW" veya "HIGH"
    """
    if not 0 <= do_id <= 15:
        raise HTTPException(status_code=422, detail="do_id 0–15 arasında olmalı.")
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    value = await asyncio.to_thread(robot_mgr.read_do_status, do_id)
    if value < 0:
        raise HTTPException(status_code=500, detail=f"DO{do_id} okuması başarısız (err={value}).")
    return {
        "do_id": do_id,
        "value": value,
        "label": "HIGH" if value == 1 else "LOW",
    }


@router.get("/robot/di/{di_id}", status_code=200)
async def robot_read_di(di_id: int):
    """
    Belirtilen DI pininin mevcut durumunu okur.

    di_id : Digital Input pin numarası

    Yanıt:
        di_id  : int — sorgulan pin
        value  : int — 0 (LOW) veya 1 (HIGH)
        label  : str — "LOW" veya "HIGH"
    """
    if di_id < 0:
        raise HTTPException(status_code=422, detail="Geçersiz di_id.")
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    value = await asyncio.to_thread(robot_mgr.read_di_status, di_id)
    if value < 0:
        raise HTTPException(status_code=500, detail=f"DI{di_id} okuması başarısız (err={value}).")
    return {
        "di_id": di_id,
        "value": value,
        "label": "HIGH" if value == 1 else "LOW",
    }


@router.post("/robot/do/{do_id}", status_code=200)
async def robot_write_do(do_id: int, body: dict):
    """
    Belirtilen DO pinini HIGH veya LOW yapar.

    do_id : 0–15 arası Digital Output pin numarası
    body  : { "value": true/false }  veya  { "value": 1/0 }

    Yanıt:
        do_id   : int
        value   : bool  — ayarlanan değer
        label   : str   — "HIGH" veya "LOW"
        sdk_err : int   — 0 başarı
    """
    if not 0 <= do_id <= 15:
        raise HTTPException(status_code=422, detail="do_id 0–15 arasında olmalı.")
    raw = body.get("value")
    if raw is None:
        raise HTTPException(status_code=422, detail="Body'de 'value' alanı gerekli: true/false veya 1/0.")
    status = bool(raw)
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    err = await asyncio.to_thread(robot_mgr.set_do, do_id, status)
    if err != 0:
        raise HTTPException(
            status_code=500,
            detail=f"DO{do_id}={'HIGH' if status else 'LOW'} yazma başarısız (sdk_err={err})."
        )
    return {
        "do_id"  : do_id,
        "value"  : status,
        "label"  : "HIGH" if status else "LOW",
        "sdk_err": err,
    }


# ── Eski debug endpoint'ler (deprecated) ──────────────

@router.get("/read_do", status_code=200, deprecated=True)
async def read_do_legacy():
    """⚠️  Eski endpoint. GET /robot/do/{do_id} kullanın."""
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    result = robot_mgr.read_do_status(1)
    return {"ok": True, "response": result, "deprecated": "GET /robot/do/1 kullanın"}


@router.post("/set_do", status_code=200, deprecated=True)
async def set_do_legacy(request: SendRequest):
    """⚠️  Eski endpoint. POST /robot/do/{do_id} kullanın."""
    ok = await asyncio.to_thread(robot_mgr._is_connected_quick)
    if not ok:
        raise HTTPException(status_code=503, detail="Robot bağlı değil.")
    result = await asyncio.to_thread(robot_mgr.set_do, 2, True)
    return {"ok": True, "response": result, "deprecated": "POST /robot/do/2 kullanın"}
