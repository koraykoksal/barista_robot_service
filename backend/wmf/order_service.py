"""
order_service.py

Sipariş akışının tüm mantığı — app.py'den ayrıştırıldı.

Dışarıya açık tek fonksiyon:
    run_order_flow(job_id, message, button_number, jobs, jobs_lock)

Akış sırası:
  PRE    → makine monitor kontrolü
  0      → robot bağlantısı doğrula
  0.5    → DO0 + DO2 LOW (sıfırla)
  0.6    → DI1 + DI3 LOW doğrula
  ────────────────────────────────
  1  → DO0=True         bardak al
  2  → DI1=True bekle   robot hazır
  3  → startBeverage    kahve başlat (arka planda)
  4  → TIMER            içecek hazırlanıyor
  5  → DO2=True         içecek hazır
  6  → DI3=True bekle   robot teslim etti  → status=done (frontend bilgilen)
  7  → coffee_task kapat
  8  → stok düş + log yaz
"""

import asyncio
import json
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import websockets

from config        import (
    COFFEE_MACHINE_IP,
    COFFEE_MACHINE_PORT,
    COFFEE_MACHINE_TOKEN,
    COFFEE_OVERALL_TIMEOUT,
    COFFEE_RECV_TIMEOUT,
    COFFEE_SILENT_ROUNDS,
    DI_WAIT_TIMEOUT,
    ROBOT_MODE_SWITCH_TIMEOUT,
    ROBOT_MODE_POLL_INTERVAL,
)
from services      import robot_mgr, coffee, monitor, syrup
from routers.syrup import get_syrup_recipe
from machine_monitor import NON_BLOCKING_ERROR_CODES
from order_utils   import (
    log,
    get_brew_delay,
    describe_machine_errors,
    check_monitor_state,
    cleanup_signals,
)
from helper        import is_rcp_confirmation_required
import stock_service


# ─────────────────────────────────────────────
# ANA AKIŞ FONKSİYONU
# ─────────────────────────────────────────────

async def run_order_flow(
    job_id       : str,
    message      : Dict[str, Any],
    button_number: Any,
    jobs         : Dict[str, Any],
    jobs_lock    : asyncio.Lock,
) -> None:
    """
    Sipariş akışını baştan sona yürütür.
    Sonuç (done / error / timeout) jobs[job_id] içine yazılır.
    """

    coffee_task : Optional[asyncio.Task] = None
    watcher_task: Optional[asyncio.Task] = None
    t_start      = time.monotonic()
    abort_event  = asyncio.Event()

    # ── Job phase güncelleme ──────────────────
    async def _update(phase: str, status: str = "running") -> None:
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase"]  = phase
                jobs[job_id]["status"] = status

    # ── Rcp State callback ────────────────────
    async def on_rcp_state(state: int) -> None:
        log(job_id, "RCP_STATE", f"Rcp State → {state}")
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["rcp_state"] = state

    # ── Makine hata izleyicisi ────────────────
    async def watch_machine_errors() -> None:
        """
        startBeverage sırasında machine_monitor'ı izler.
        Sadece BLOCKING hatalar abort_event'i tetikler.
        NON_BLOCKING_ERROR_CODES (örn. 764) yoksayılır — sipariş devam eder.
        """
        known_blocking: set = set()
        while not abort_event.is_set():
            try:
                state      = await monitor.get_state()
                cur_errors = set(state.get("errors") or [])
                # Sadece blocking hataları filtrele
                cur_blocking  = cur_errors - NON_BLOCKING_ERROR_CODES
                new_blocking  = cur_blocking - known_blocking
                if new_blocking:
                    msg = describe_machine_errors(list(new_blocking))
                    log(job_id, "MACHINE_WATCHER",
                        f"🛑 Yeni blocking makine hatası: {new_blocking} → {msg}")
                    async with jobs_lock:
                        if job_id in jobs:
                            jobs[job_id]["machine_errors"]     = list(cur_blocking)
                            jobs[job_id]["machine_error_desc"] = msg
                    abort_event.set()
                    return
                # Non-blocking hatalar varsa sadece logla
                non_blocking = cur_errors & NON_BLOCKING_ERROR_CODES
                if non_blocking:
                    log(job_id, "MACHINE_WATCHER",
                        f"ℹ️  Non-blocking hatalar (yoksayıldı): {non_blocking}")
                known_blocking = cur_blocking
            except Exception:
                pass
            await asyncio.sleep(0.5)

    # ── Watcher + coffee_task temizleyici ─────
    async def _cancel_tasks() -> None:
        abort_event.set()
        for t in (watcher_task, coffee_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

    try:
        # ══ PRE-CHECK: Makine monitor ════════════
        log(job_id, "STEP_PRE_CHECK", "Makine durumu kontrol ediliyor...")
        current_state = await monitor.get_state()
        check_monitor_state(current_state, job_id[:8])
        log(job_id, "STEP_PRE_CHECK", "✅ Makine durumu temiz.")

        # ══ ADIM 0: Robot bağlantısı ══════════════
        log(job_id, "STEP_0_ROBOT", "Robot bağlantısı kontrol ediliyor...")
        await asyncio.to_thread(robot_mgr._ensure_connected)
        log(job_id, "STEP_0_ROBOT", "✅ Robot bağlı.")

        # ══ ADIM 0.1: Robot mod kontrolü ══════════
        # Sipariş başlamadan önce robot otomatik modda olmalı.
        # Değilse önce otomatik moda geçirilmeye çalışılır.
        # Geçiş başarısız olursa sipariş iptal edilir.
        log(job_id, "STEP_0_1_ROBOT_MODE", "Robot modu kontrol ediliyor...")
        robot_status = await asyncio.to_thread(robot_mgr.get_robot_status)

        if not robot_status["connected"]:
            raise Exception("Robot bağlı değil — sipariş başlatılamaz.")

        if robot_status["robot_mode"] != 0:
            log(job_id, "STEP_0_1_ROBOT_MODE",
                f"⚠️  Robot manuel modda ({robot_status['mode_label']}) — "
                f"otomatik moda geçiş deneniyor...")

            switched = await asyncio.to_thread(
                robot_mgr.set_auto_mode_and_wait,
                ROBOT_MODE_SWITCH_TIMEOUT,
                ROBOT_MODE_POLL_INTERVAL,
            )
            if not switched:
                raise Exception(
                    f"Robot otomatik moda geçiş başarısız "
                    f"({ROBOT_MODE_SWITCH_TIMEOUT}s içinde geçiş olmadı). "
                    f"Robotu manuel olarak otomatik moda alın."
                )
            log(job_id, "STEP_0_1_ROBOT_MODE", "✅ Robot otomatik moda geçirildi.")
        else:
            log(job_id, "STEP_0_1_ROBOT_MODE",
                f"✅ Robot zaten otomatik modda "
                f"(state={robot_status['state_label']}).")

        # ══ ADIM 0.5: DO sıfırla ══════════════════
        log(job_id, "STEP_0_5_RESET", "DO0 ve DO2 sıfırlanıyor (LOW)...")
        await asyncio.to_thread(robot_mgr.set_do, 0, False)
        await asyncio.to_thread(robot_mgr.set_do, 2, False)
        await asyncio.sleep(0.2)
        log(job_id, "STEP_0_5_RESET", "✅ DO sinyalleri sıfırlandı.")

        # ══ ADIM 0.6: DI temiz mi? ══════════════
        log(job_id, "STEP_0_6_DI", "DI1 ve DI3 LOW bekleniyor...")
        for di_id, label in [(1, "DI1"), (3, "DI3")]:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                val = await asyncio.to_thread(robot_mgr.read_di_status, di_id)
                if val == 0:
                    break
                log(job_id, "STEP_0_6_DI", f"⏳ {label} hâlâ HIGH...")
                await asyncio.sleep(0.1)
            else:
                log(job_id, "STEP_0_6_DI", f"⚠️  {label} 5s içinde LOW olmadı, devam.")
        log(job_id, "STEP_0_6_DI", "✅ DI sinyalleri temiz.")

        # ══ ADIM 1: DO0=True (bardak al) ══════════
        await _update("set_do0_true")
        log(job_id, "STEP_1_DO0", "DO0 → True (bardak al)...")
        err = await asyncio.to_thread(robot_mgr.set_do, 0, True)
        await asyncio.sleep(0.15)
        if err != 0:
            raise Exception(f"DO0=True başarısız, err={err}")
        log(job_id, "STEP_1_DO0", f"✅ DO0 → True (err={err})")

        # ══ ADIM 2: DI1=True bekle (robot hazır) ══
        await _update("wait_di1_robot_ready", "waiting")
        log(job_id, "STEP_2_DI1", f"DI1=True bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        t_wait  = time.monotonic()
        ok      = await asyncio.to_thread(robot_mgr.wait_di_true, 1, DI_WAIT_TIMEOUT, 0.1)
        elapsed = time.monotonic() - t_wait
        if not ok:
            raise TimeoutError(f"DI1=True timeout ({elapsed:.1f}s geçti)")
        log(job_id, "STEP_2_DI1", f"✅ DI1=True ({elapsed:.1f}s) — robot bardağı aldı")

        # ══ ADIM 2.5: SYRUP (varsa) ════════════════
        # DI1 geldi → robot bardağı aldı, pozisyonda.
        # Eğer bu içecek için syrup tarifi tanımlıysa şurup akıt.
        syrup_recipe = get_syrup_recipe(int(button_number)) if button_number else None
        if syrup_recipe:
            await _update("syrup_dispense")
            ch     = syrup_recipe["channel"]
            qty_ml = syrup_recipe["qty_ml"]
            log(job_id, "STEP_2_5_SYRUP",
                f"Syrup tarifi bulundu → kanal={ch} miktar={qty_ml}mL")
            try:
                syrup_result = await syrup.dispense(ch, qty_ml)
                log(job_id, "STEP_2_5_SYRUP",
                    f"✅ Syrup tamamlandı → {syrup_result.get('elapsed_s', '?')}s")
            except TimeoutError as syrup_e:
                raise TimeoutError(f"Syrup timeout: {syrup_e}")
            except Exception as syrup_e:
                raise Exception(f"Syrup hata: {syrup_e}")
        else:
            log(job_id, "STEP_2_5_SYRUP",
                f"Btn={button_number} için syrup tarifi yok — atlandı.")

        # ══ ADIM 3: startBeverage ══════════════════
        await _update("coffee_task_start")
        log(job_id, "STEP_3_COFFEE", "startBeverage gönderiliyor (arka planda)...")

        watcher_task = asyncio.create_task(watch_machine_errors())

        coffee_task  = asyncio.create_task(
            coffee.send_and_wait_rcp_finished(
                message,
                overall_timeout   = COFFEE_OVERALL_TIMEOUT,
                recv_timeout      = COFFEE_RECV_TIMEOUT,
                max_silent_rounds = COFFEE_SILENT_ROUNDS,
                on_state          = on_rcp_state,
                abort_event       = abort_event,
            )
        )
        log(job_id, "STEP_3_COFFEE", "☕ coffee_task + watcher_task başlatıldı.")

        # ══ ADIM 4: TIMER ══════════════════════════
        delay_sec = get_brew_delay(button_number)
        if delay_sec > 0:
            log(job_id, "STEP_4_TIMER", f"Button {button_number!r} → {delay_sec}s timer başladı...")
            await _update(f"timer_{delay_sec}s", "waiting")
            await asyncio.sleep(delay_sec)
            log(job_id, "STEP_4_TIMER", f"✅ Timer bitti ({delay_sec}s) — içecek hazır.")
        else:
            log(job_id, "STEP_4_TIMER", f"Button {button_number!r} için timer yok — devam.")

        # Timer sırasında BLOCKING makine hatası var mı?
        if abort_event.is_set():
            s        = await monitor.get_state()
            codes    = s.get("errors") or []
            blocking = [c for c in codes if c not in NON_BLOCKING_ERROR_CODES]
            desc     = describe_machine_errors(blocking) if blocking else "İçecek hazırlanırken makine hatası."
            raise Exception(f"Makine hatası (timer sırasında): {desc}")

        # ══ ADIM 5: DO2=True (içecek hazır) ═══════
        await _update("set_do2_true")
        log(job_id, "STEP_5_DO2", "DO2 → True (içecek hazır, robota teslim et)...")
        err2 = await asyncio.to_thread(robot_mgr.set_do, 2, True)
        await asyncio.sleep(0.20)
        if err2 != 0:
            raise Exception(f"DO2=True başarısız, err={err2}")
        log(job_id, "STEP_5_DO2", f"✅ DO2 → True (err={err2})")

        # ══ ADIM 6: DI3=True bekle (teslim edildi) ═
        await _update("wait_di3_robot_done", "waiting")
        log(job_id, "STEP_6_DI3", f"DI3=True bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        t_wait  = time.monotonic()
        ok3     = await asyncio.to_thread(robot_mgr.wait_di_true, 3, DI_WAIT_TIMEOUT, 0.1)
        elapsed = time.monotonic() - t_wait
        if not ok3:
            raise TimeoutError(f"DI3=True timeout ({elapsed:.1f}s — robot teslim sinyali gelmedi)")
        log(job_id, "STEP_6_DI3", f"✅ DI3=True ({elapsed:.1f}s) — robot teslim etti")

        # DI3 alındı → frontend'i HEMEN bilgilendir
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase"]  = "robot_delivered"
                jobs[job_id]["status"] = "done"
        log(job_id, "STEP_6_DI3", "✅ phase=robot_delivered, status=done")

        # ══ ADIM 7: coffee_task kapat ══════════════
        await _update("finalizing")
        log(job_id, "STEP_7_CLEANUP", "coffee_task kapatılıyor...")
        abort_event.set()

        watcher_task.cancel()
        try:
            await watcher_task
        except (asyncio.CancelledError, Exception):
            pass

        results: List[Any] = []
        if not coffee_task.done():
            try:
                results = await asyncio.wait_for(asyncio.shield(coffee_task), timeout=2.0)
            except asyncio.TimeoutError:
                coffee_task.cancel()
                try:
                    await coffee_task
                except asyncio.CancelledError:
                    pass
                results = []
                log(job_id, "STEP_7_CLEANUP", "coffee_task 2s içinde bitmedi, iptal edildi.")
        else:
            results = coffee_task.result() if not coffee_task.cancelled() else []

        # Makine hata kontrolü
        if any(isinstance(p, dict) and p.get("error") == "machine_error_abort" for p in results):
            s     = await monitor.get_state()
            codes = s.get("errors") or []
            desc  = describe_machine_errors(codes) if codes else "İçecek hazırlanırken makine hatası."
            raise Exception(f"Makine hatası: {desc}")

        # Rcp State 22 (onay bekleniyor)
        if is_rcp_confirmation_required(results):
            raise Exception(
                "Makine 'Beverage confirmation' bekliyor (Rcp State 22). "
                "Makine ayarı: System > Digital solutions > CM-Remote > Beverage confirmation"
            )

        log(job_id, "STEP_7_CLEANUP", "✅ coffee_task temizlendi.")

        # ══ DONE: DO sinyallerini temizle ══════════
        total = time.monotonic() - t_start
        log(job_id, "DONE", f"✅ Sipariş tamamlandı — toplam {total:.1f}s")

        await asyncio.to_thread(robot_mgr.set_do, 0, False)
        await asyncio.to_thread(robot_mgr.set_do, 2, False)
        await asyncio.sleep(0.2)
        log(job_id, "DONE", "✅ DO sinyalleri temizlendi.")

        # ══ ADIM 8: Stok düşür + sipariş logu ════
        await _update_stock(job_id, button_number, jobs, jobs_lock, results)

        # Son job güncellemesi (finished_at)
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status"     : "done",
                    "phase"      : "done",
                    "finished_at": time.time(),
                    "result"     : results,
                })

    except TimeoutError as e:
        log(job_id, "TIMEOUT", f"⏰ {e}")
        await _cancel_tasks()
        await cleanup_signals(job_id)
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status"     : "timeout",
                    "phase"      : "aborted",
                    "finished_at": time.time(),
                    "error"      : str(e),
                })

    except Exception as e:
        log(job_id, "ERROR", f"❌ {e}")
        await _cancel_tasks()
        await cleanup_signals(job_id)
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status"     : "error",
                    "phase"      : "aborted",
                    "finished_at": time.time(),
                    "error"      : str(e),
                })


# ─────────────────────────────────────────────
# STOK GÜNCELLEME (ADIM 8)
# ─────────────────────────────────────────────

async def _update_stock(
    job_id       : str,
    button_number: Any,
    jobs         : Dict[str, Any],
    jobs_lock    : asyncio.Lock,
    results      : List[Any],
) -> None:
    """
    getRecipeComposition ile reçete sorgular, stoku düşürür ve sipariş loglar.
    Herhangi bir hata fırlatırsa yoksayılır — stok hatası siparişi başarısız saymaz.
    """
    try:
        log(job_id, "STEP_8_STOCK", "Reçete bilgisi sorgulanıyor (getRecipeComposition)...")
        coffee_g    = 0.0
        milk_ml     = 0.0
        choc_g      = 0.0
        recipe_name = str(button_number)
        raw_recipe  = None

        try:
            headers = {"Authorization": f"Bearer {COFFEE_MACHINE_TOKEN}"}
            async with websockets.connect(
                f"ws://{COFFEE_MACHINE_IP}:{COFFEE_MACHINE_PORT}/",
                additional_headers=headers,
                open_timeout=5,
                close_timeout=3,
            ) as wsc:
                await wsc.send(json.dumps({
                    "function"    : "getRecipeComposition",
                    "RecipeNumber": str(button_number),
                }))
                _raw   = await asyncio.wait_for(wsc.recv(), timeout=6.0)
                _rdata = json.loads(_raw)

            if isinstance(_rdata, list):
                for _item in _rdata:
                    if isinstance(_item, dict):
                        if "Name" in _item:
                            recipe_name = _item.get("Name", recipe_name)
                        if "Parts" in _item:
                            raw_recipe = _item
                            amounts    = stock_service.extract_recipe_amounts(_item["Parts"])
                            coffee_g   = amounts["coffee_g"]
                            milk_ml    = amounts["milk_ml"]
                            choc_g     = amounts["choc_g"]
                            log(job_id, "STEP_8_STOCK",
                                f"Reçete: {recipe_name} → "
                                f"kahve={coffee_g}g milk={milk_ml}ml choc={choc_g}g")

            if raw_recipe is None:
                log(job_id, "STEP_8_STOCK", "⚠️  Reçete parts alınamadı, varsayılan değerler kullanılacak.")

        except Exception as recipe_err:
            log(job_id, "STEP_8_STOCK",
                f"⚠️  getRecipeComposition hatası: {recipe_err} — varsayılan kullanılacak.")

        await stock_service.consume_stock(
            button_number = int(button_number) if str(button_number).isdigit() else 0,
            coffee_g      = coffee_g,
            milk_ml       = milk_ml,
            choc_g        = choc_g,
            cups          = 1,
            job_id        = job_id,
            recipe_name   = recipe_name,
            raw_recipe    = raw_recipe,
        )
        log(job_id, "STEP_8_STOCK", "✅ Stok düşürüldü ve sipariş logu yazıldı.")

    except Exception as stock_err:
        log(job_id, "STEP_8_STOCK", f"⚠️  Stok güncelleme hatası (yoksayıldı): {stock_err}")
