"""
routers/order.py

Sipariş ile ilgili endpoint'ler:
  POST /order_standart   — sipariş başlat
  GET  /order/status/:id — job durumu polling
  POST /check_beverage   — makine hazır mı?
  POST /connect-test     — WS bağlantı testi
  POST /send             — debug ham WS
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from service.registry     import coffee, monitor
from service.order_service import run_order_flow
from core.logging import log, log_order_detail
from core.machine_errors import describe_machine_errors
from core import catalog
from core.config import COFFEE_OVERALL_TIMEOUT, COFFEE_RECV_TIMEOUT, COFFEE_SILENT_ROUNDS

router = APIRouter()

# ─────────────────────────────────────────────
# MODELLER
# ─────────────────────────────────────────────

class SendRequest(BaseModel):
    message: Dict[str, Any]


# ─────────────────────────────────────────────
# JOB STORE — order router'ı içinde tutulur
# app.py lifespan'dan erişmek için getter sağlanır
# ─────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]]  = {}
_jobs_lock: asyncio.Lock          = asyncio.Lock()
_active_task: Optional[asyncio.Task] = None
_active_task_lock: asyncio.Lock   = asyncio.Lock()
_order_flow_lock: asyncio.Lock    = asyncio.Lock()


def get_jobs() -> Dict[str, Any]:
    return _jobs


# ─────────────────────────────────────────────
# SİPARİŞ BAŞLAT
# ─────────────────────────────────────────────

@router.post("/order_standart", status_code=200)
async def order_standart(request: SendRequest, http_request: Request):
    global _active_task

    button_number = request.message.get("a_iBtnNbr")
    client_ip     = http_request.client.host if http_request.client else "?"
    job_id        = str(uuid.uuid4())

    log_order_detail(job_id, request.message, client_ip)

    # Çakışan sipariş kontrolü
    async with _active_task_lock:
        if _active_task and not _active_task.done():
            raise HTTPException(
                status_code=409,
                detail="Makine/robot şu anda başka bir siparişi işliyor. Lütfen bekleyin.",
            )

        log(job_id, "CREATED", f"Job oluşturuldu | button={button_number}")

        async with _jobs_lock:
            _jobs[job_id] = {
                "status"     : "running",
                "phase"      : "created",
                "rcp_state"  : None,
                "started_at" : time.time(),
                "finished_at": None,
                "error"      : None,
                "result"     : None,
            }

    async def run_with_lock():
        global _active_task
        async with _order_flow_lock:
            await run_order_flow(
                job_id        = job_id,
                message       = request.message,
                button_number = button_number,
                jobs          = _jobs,
                jobs_lock     = _jobs_lock,
            )
        async with _active_task_lock:
            current = asyncio.current_task()
            if _active_task is current:
                _active_task = None
                log(job_id, "FINALLY", "active_order_task temizlendi.")

    task = asyncio.create_task(run_with_lock())
    async with _active_task_lock:
        _active_task = task

    print(f"[ORDER] Job kuyruğa alındı → job_id={job_id}")
    return {"job_id": job_id}


# ─────────────────────────────────────────────
# SİPARİŞ DURUM POLLING
# ─────────────────────────────────────────────

@router.get("/order/status/{job_id}", status_code=200)
async def order_status(job_id: str):
    async with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job_id bulunamadı.")
        return {
            "job_id"   : job_id,
            "status"   : job["status"],
            "phase"    : job["phase"],
            "rcp_state": job["rcp_state"],
            "error"    : job["error"],
        }


# ─────────────────────────────────────────────
# CHECK BEVERAGE
# ─────────────────────────────────────────────

@router.post("/check_beverage", status_code=200)
async def check_beverage(request: SendRequest, http_request: Request):
    """checkBeverage mesajını makineye gönderir, returnvalue döner."""
    from datetime import datetime
    client_ip = http_request.client.host if http_request.client else "?"
    btn_raw   = str(request.message.get("a_iBtnNbr", "?"))
    btn_int   = int(btn_raw) if btn_raw.isdigit() else -1
    bev_name  = catalog.name(btn_raw)
    now       = datetime.now().strftime("%H:%M:%S")

    print(f"[CHECK_BEVERAGE] {now} | IP={client_ip} | {bev_name} (btn={btn_raw})")

    try:
        response = await coffee.check_beverage(request.message)
        result   = response if isinstance(response, dict) else {}
        code     = result.get("returnvalue")

        machine_error_detail = None
        if code == 4:
            try:
                mstate = await monitor.get_state()
                errors = mstate.get("errors") or []
                if errors:
                    machine_error_detail = describe_machine_errors(errors)
            except Exception:
                pass

        return {
            "ws_uri"              : coffee.ws_uri,
            "sent"                : request.message,
            "result"              : response,
            "machine_error_detail": machine_error_detail,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"check_beverage error: {e}")


# ─────────────────────────────────────────────
# WS BAĞLANTI TESTİ
# ─────────────────────────────────────────────

@router.post("/connect-test", status_code=200)
async def connect_test():
    """Kahve makinesine WS bağlantı testi (mesaj göndermez)."""
    return await coffee.connect_test()


# ─────────────────────────────────────────────
# DEBUG: HAM WS
# ─────────────────────────────────────────────

@router.post("/send", status_code=200)
async def send_raw(request: SendRequest):
    """
    ⚠️  SADECE DEBUG/TEST.
    Robot sinyalleri çalışmaz — gerçek sipariş için /order_standart kullanın.
    """
    print(f"[SEND] ⚠️  Ham WS (robot sinyali YOK): {request.message}")
    results = await coffee.send_and_wait_rcp_finished(
        request.message,
        overall_timeout   = COFFEE_OVERALL_TIMEOUT,
        recv_timeout      = COFFEE_RECV_TIMEOUT,
        max_silent_rounds = COFFEE_SILENT_ROUNDS,
    )
    return {"response": results}
