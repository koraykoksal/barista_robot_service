"""
service/order_service.py

Sipariş akışının tamamı. Dışarıya açık tek fonksiyon:

    run_order_flow(job_id, message, button_number, jobs, jobs_lock)

AKIŞ:
  PRE    → makine durumu kontrolü
  0      → robot bağlantısı
  0.1    → robot otomatik modda mı
  0.5    → DO0 + DO2 LOW (sıfırla)
  0.6    → DI1 + DI3 LOW doğrula
  ────────────────────────────────
  1  → DO0=True          bardak al
  2  → DI1=True bekle    robot bardağı aldı
  2.5→ syrup             tarif varsa şurup akıt
  3  → startBeverage     kahve başlat (arka planda)
  4  → TIMER             içecek hazırlanıyor
  5  → DO2=True          içecek hazır
  6  → DI3=True bekle    robot teslim etti → status=done
  7  → coffee_task kapat
  8  → stok düş + log yaz

YAPISAL DEĞİŞİKLİKLER:
  • "from routers.syrup import get_syrup_recipe" kaldırıldı — bir servis
    artık rota dosyasından veri okumuyor. Tarifler service/syrup_recipes.py'de.
  • cleanup_signals order_utils.py'den buraya taşındı; robot_mgr'a bağımlı
    olduğu için core katmanında duramazdı.
  • Bekleme süresi config.BREW_TIMERS yerine catalog.brew_seconds()'tan.

DÜZELTİLEN HATA — getRecipeComposition:
  Önceki sürüm reçete sorgusuna ButtonNumber gönderiyordu:

      {"function": "getRecipeComposition", "RecipeNumber": str(button_number)}

  Oysa ikisi farklı (Americano btn=2 → recipe=5, Latte btn=3 → recipe=91).
  Espresso dışındaki her içecekte yanlış/boş reçete dönüyor, stok da
  sessizce varsayılan 9 g / 150 ml ile düşülüyordu.
  Artık catalog.recipe_number() ile doğru numara gönderiliyor.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import websockets

from core import catalog
from core.config import (
    COFFEE_MACHINE_IP,
    COFFEE_MACHINE_PORT,
    COFFEE_MACHINE_TOKEN,
    COFFEE_OVERALL_TIMEOUT,
    COFFEE_RECV_TIMEOUT,
    COFFEE_SILENT_ROUNDS,
    DI_WAIT_TIMEOUT,
    ROBOT_MODE_POLL_INTERVAL,
    ROBOT_MODE_SWITCH_TIMEOUT,
)
from core.applog import log
from core.machine_errors import check_monitor_state, describe_machine_errors
from core.ws_utils import is_rcp_confirmation_required
from service import stock_service
from service.machine_monitor import NON_BLOCKING_ERROR_CODES
from service.registry import coffee, monitor, robot_mgr, syrup
from service.syrup_recipes import get_syrup_recipe
from service.syrup_service import SyrupAbortError


# ═════════════════════════════════════════════
# SİNYAL TEMİZLEME
# ═════════════════════════════════════════════

async def cleanup_signals(job_id: str = "") -> None:
    """
    Hata / timeout sonrası DO0 ve DO2 sinyallerini LOW'a çeker.

    Bu adım atlanırsa robot bir sonraki siparişte "zaten bardak al"
    sinyalini yüksek görür ve akış baştan bozulur.
    """
    log(job_id, "CLEANUP", "DO0 ve DO2 → False yapılıyor...")
    for do_idx in (0, 2):
        try:
            await asyncio.to_thread(robot_mgr.set_do, do_idx, False)
            log(job_id, "CLEANUP", f"  DO{do_idx} → False ✅")
        except Exception as e:
            log(job_id, "CLEANUP", f"  DO{do_idx} → False HATA: {e}")


# ═════════════════════════════════════════════
# ANA AKIŞ
# ═════════════════════════════════════════════

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
    t_start     = time.monotonic()
    abort_event = asyncio.Event()

    async def _update(phase: str, status: str = "running") -> None:
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase"]  = phase
                jobs[job_id]["status"] = status

    async def on_rcp_state(state: int) -> None:
        log(job_id, "RCP_STATE", f"Rcp State → {state}")
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["rcp_state"] = state

    async def watch_machine_errors() -> None:
        """
        startBeverage sırasında makine durumunu izler.
        Yalnızca ENGELLEYİCİ hatalar akışı durdurur; NON_BLOCKING_ERROR_CODES
        (ör. 764) yalnızca loglanır.
        """
        known_blocking: set = set()
        while not abort_event.is_set():
            try:
                state        = await monitor.get_state()
                cur_errors   = set(state.get("errors") or [])
                cur_blocking = cur_errors - NON_BLOCKING_ERROR_CODES
                new_blocking = cur_blocking - known_blocking

                if new_blocking:
                    detail = describe_machine_errors(list(new_blocking))
                    log(job_id, "MACHINE_WATCHER",
                        f"🛑 Yeni engelleyici hata: {new_blocking} → {detail}")
                    async with jobs_lock:
                        if job_id in jobs:
                            jobs[job_id]["machine_errors"]     = list(cur_blocking)
                            jobs[job_id]["machine_error_desc"] = detail
                    abort_event.set()
                    return

                non_blocking = cur_errors & NON_BLOCKING_ERROR_CODES
                if non_blocking:
                    log(job_id, "MACHINE_WATCHER",
                        f"ℹ️  Engelleyici olmayan hatalar (yoksayıldı): {non_blocking}")
                known_blocking = cur_blocking
            except Exception:
                pass
            await asyncio.sleep(0.5)

    async def _cancel_tasks() -> None:
        abort_event.set()
        for task in (watcher_task, coffee_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    try:
        # ══ PRE: Makine durumu ═══════════════
        log(job_id, "STEP_PRE_CHECK", "Makine durumu kontrol ediliyor...")
        check_monitor_state(await monitor.get_state(), job_id[:8])
        log(job_id, "STEP_PRE_CHECK", "✅ Makine durumu temiz.")

        # ══ ADIM 0: Robot bağlantısı ═════════
        log(job_id, "STEP_0_ROBOT", "Robot bağlantısı kontrol ediliyor...")
        await asyncio.to_thread(robot_mgr._ensure_connected)
        log(job_id, "STEP_0_ROBOT", "✅ Robot bağlı.")

        # ══ ADIM 0.1: Robot modu ═════════════
        log(job_id, "STEP_0_1_ROBOT_MODE", "Robot modu kontrol ediliyor...")
        robot_status = await asyncio.to_thread(robot_mgr.get_robot_status)

        if not robot_status["connected"]:
            raise Exception("Robot bağlı değil — sipariş başlatılamaz.")

        if robot_status["robot_mode"] != 0:
            log(job_id, "STEP_0_1_ROBOT_MODE",
                f"⚠️  Robot manuel modda ({robot_status['mode_label']}) — "
                "otomatik moda geçiş deneniyor...")
            switched = await asyncio.to_thread(
                robot_mgr.set_auto_mode_and_wait,
                ROBOT_MODE_SWITCH_TIMEOUT,
                ROBOT_MODE_POLL_INTERVAL,
            )
            if not switched:
                raise Exception(
                    f"Robot otomatik moda geçemedi ({ROBOT_MODE_SWITCH_TIMEOUT}s). "
                    "Robotu manuel olarak otomatik moda alın."
                )
            log(job_id, "STEP_0_1_ROBOT_MODE", "✅ Robot otomatik moda geçirildi.")
        else:
            log(job_id, "STEP_0_1_ROBOT_MODE",
                f"✅ Robot zaten otomatik modda (state={robot_status['state_label']}).")

        # ══ ADIM 0.5: DO sıfırla ═════════════
        log(job_id, "STEP_0_5_RESET", "DO0 ve DO2 sıfırlanıyor (LOW)...")
        await asyncio.to_thread(robot_mgr.set_do, 0, False)
        await asyncio.to_thread(robot_mgr.set_do, 2, False)
        await asyncio.sleep(0.2)
        log(job_id, "STEP_0_5_RESET", "✅ DO sinyalleri sıfırlandı.")

        # ══ ADIM 0.6: DI temiz mi ════════════
        log(job_id, "STEP_0_6_DI", "DI1 ve DI3 LOW bekleniyor...")
        for di_id, label in ((1, "DI1"), (3, "DI3")):
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if await asyncio.to_thread(robot_mgr.read_di_status, di_id) == 0:
                    break
                log(job_id, "STEP_0_6_DI", f"⏳ {label} hâlâ HIGH...")
                await asyncio.sleep(0.1)
            else:
                log(job_id, "STEP_0_6_DI", f"⚠️  {label} 5s içinde LOW olmadı, devam.")
        log(job_id, "STEP_0_6_DI", "✅ DI sinyalleri temiz.")

        # ══ ADIM 1: DO0=True (bardak al) ═════
        await _update("set_do0_true")
        log(job_id, "STEP_1_DO0", "DO0 → True (bardak al)...")
        err = await asyncio.to_thread(robot_mgr.set_do, 0, True)
        await asyncio.sleep(0.15)
        if err != 0:
            raise Exception(f"DO0=True başarısız, err={err}")
        log(job_id, "STEP_1_DO0", f"✅ DO0 → True (err={err})")

        # ══ ADIM 2: DI1=True bekle ═══════════
        await _update("wait_di1_robot_ready", "waiting")
        log(job_id, "STEP_2_DI1", f"DI1=True bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        t_wait = time.monotonic()
        ok = await asyncio.to_thread(robot_mgr.wait_di_true, 1, DI_WAIT_TIMEOUT, 0.1)
        elapsed = time.monotonic() - t_wait
        if not ok:
            raise TimeoutError(f"DI1=True timeout ({elapsed:.1f}s geçti)")
        log(job_id, "STEP_2_DI1", f"✅ DI1=True ({elapsed:.1f}s) — robot bardağı aldı")

        # ══ ADIM 2.5: SYRUP ══════════════════
        recipe = get_syrup_recipe(button_number)
        if recipe:
            await _update("syrup_dispense")
            channel = recipe.get("channel")
            # DÜZELTİLEN HATA: rota tarifi "ml" anahtarıyla kaydediyor
            # (route/syrup.py → syrup_recipe_set), ancak önceki sürüm
            # burada recipe["qty_ml"] okuyordu. Tanımlı bir şurup tarifi
            # olan HER sipariş bu satırda KeyError ile çöküyordu.
            # İki anahtarı da kabul ediyoruz.
            qty_ml = recipe.get("ml", recipe.get("qty_ml"))

            if not channel or not qty_ml:
                log(job_id, "STEP_2_5_SYRUP",
                    f"⚠️  Tarif eksik ({recipe!r}) — şurup atlandı.")
            else:
                log(job_id, "STEP_2_5_SYRUP", f"Şurup tarifi → kanal={channel} miktar={qty_ml}mL")
                try:
                    result = await syrup.dispense(channel, qty_ml)
                    log(job_id, "STEP_2_5_SYRUP", f"✅ Şurup tamam ({result.get('elapsed_s', '?')}s)")
                    # Başarılı dozajdan sonra kanaldan düş. Stok kapısı
                    # bu noktaya yeterli şurupla gelinmesini sağlar; buradaki
                    # düşüm gerçekleşeni kaydeder.
                    try:
                        await stock_service.consume_syrup(channel, float(qty_ml), job_id)
                    except Exception as e:
                        log(job_id, "STEP_2_5_SYRUP", f"⚠️  Şurup stok düşümü yazılamadı: {e}")
                except SyrupAbortError as e:
                    # Dozaj yarıda kesildi (genelde pompa ayrılması).
                    # Reçete eksik kaldı — sipariş bu noktada durdurulur.
                    # Akıtılabilen kadarını yine de stoktan düş.
                    try:
                        await stock_service.consume_syrup(channel, float(e.dispensed_ml), job_id)
                    except Exception:
                        pass
                    log(job_id, "STEP_2_5_SYRUP",
                        f"❌ Şurup yarıda kesildi: {e.dispensed_ml:.1f}/{e.requested_ml:.1f}mL "
                        f"(sebep={e.reason})")
                    raise Exception(
                        f"Şurup dozajı yarıda kesildi (kanal {channel}, {e.reason}): "
                        f"reçete {e.requested_ml:.0f}mL istedi, {e.dispensed_ml:.0f}mL akıtıldı. "
                        f"İçecek eksik kaldı."
                    )
                except TimeoutError as e:
                    raise TimeoutError(f"Syrup timeout: {e}")
                except Exception as e:
                    raise Exception(f"Syrup hata: {e}")
        else:
            log(job_id, "STEP_2_5_SYRUP", f"Btn={button_number} için şurup tarifi yok — atlandı.")

        # ══ ADIM 3: startBeverage ════════════
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

        # ══ ADIM 4: TIMER ════════════════════
        delay = catalog.brew_seconds(button_number)
        if delay > 0:
            log(job_id, "STEP_4_TIMER", f"Btn {button_number} → {delay}s timer başladı...")
            await _update(f"timer_{delay}s", "waiting")
            await asyncio.sleep(delay)
            log(job_id, "STEP_4_TIMER", f"✅ Timer bitti ({delay}s).")
        else:
            log(job_id, "STEP_4_TIMER", f"Btn {button_number} için timer yok — devam.")

        if abort_event.is_set():
            state    = await monitor.get_state()
            blocking = [c for c in (state.get("errors") or []) if c not in NON_BLOCKING_ERROR_CODES]
            detail   = describe_machine_errors(blocking) if blocking else "İçecek hazırlanırken makine hatası."
            raise Exception(f"Makine hatası (timer sırasında): {detail}")

        # ══ ADIM 5: DO2=True ═════════════════
        await _update("set_do2_true")
        log(job_id, "STEP_5_DO2", "DO2 → True (içecek hazır)...")
        err2 = await asyncio.to_thread(robot_mgr.set_do, 2, True)
        await asyncio.sleep(0.20)
        if err2 != 0:
            raise Exception(f"DO2=True başarısız, err={err2}")
        log(job_id, "STEP_5_DO2", f"✅ DO2 → True (err={err2})")

        # ══ ADIM 6: DI3=True bekle ═══════════
        await _update("wait_di3_robot_done", "waiting")
        log(job_id, "STEP_6_DI3", f"DI3=True bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        t_wait = time.monotonic()
        ok3 = await asyncio.to_thread(robot_mgr.wait_di_true, 3, DI_WAIT_TIMEOUT, 0.1)
        elapsed = time.monotonic() - t_wait
        if not ok3:
            raise TimeoutError(f"DI3=True timeout ({elapsed:.1f}s — teslim sinyali gelmedi)")
        log(job_id, "STEP_6_DI3", f"✅ DI3=True ({elapsed:.1f}s) — robot teslim etti")

        # Frontend'i HEMEN bilgilendir — stok yazımı beklenmez
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase"]  = "robot_delivered"
                jobs[job_id]["status"] = "done"
        log(job_id, "STEP_6_DI3", "✅ phase=robot_delivered, status=done")

        # ══ ADIM 7: coffee_task kapat ════════
        await _update("finalizing", "done")
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
                log(job_id, "STEP_7_CLEANUP", "coffee_task 2s içinde bitmedi, iptal edildi.")
        elif not coffee_task.cancelled():
            results = coffee_task.result()

        if any(isinstance(p, dict) and p.get("error") == "machine_error_abort" for p in results):
            codes  = (await monitor.get_state()).get("errors") or []
            detail = describe_machine_errors(codes) if codes else "İçecek hazırlanırken makine hatası."
            raise Exception(f"Makine hatası: {detail}")

        if is_rcp_confirmation_required(results):
            raise Exception(
                "Makine 'Beverage confirmation' bekliyor (Rcp State 22). "
                "Makine ayarı: System > Digital solutions > CM-Remote > Beverage confirmation"
            )

        log(job_id, "STEP_7_CLEANUP", "✅ coffee_task temizlendi.")

        # ══ DO sinyallerini temizle ══════════
        log(job_id, "DONE", f"✅ Sipariş tamamlandı — toplam {time.monotonic() - t_start:.1f}s")
        await asyncio.to_thread(robot_mgr.set_do, 0, False)
        await asyncio.to_thread(robot_mgr.set_do, 2, False)
        await asyncio.sleep(0.2)
        log(job_id, "DONE", "✅ DO sinyalleri temizlendi.")

        # ══ ADIM 8: Stok ═════════════════════
        await _update_stock(job_id, button_number, results)

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
                    "status": "timeout", "phase": "aborted",
                    "finished_at": time.time(), "error": str(e),
                })

    except Exception as e:
        log(job_id, "ERROR", f"❌ {e}")
        await _cancel_tasks()
        await cleanup_signals(job_id)
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status": "error", "phase": "aborted",
                    "finished_at": time.time(), "error": str(e),
                })


# ═════════════════════════════════════════════
# ADIM 8 — STOK GÜNCELLEME
# ═════════════════════════════════════════════

async def _update_stock(job_id: str, button_number: Any, results: List[Any]) -> None:
    """
    Makineden gerçek reçeteyi sorgular, stoğu düşürür ve siparişi loglar.

    Buradaki hatalar YUTULUR — sipariş fiziksel olarak tamamlanmıştır,
    stok kaydı tutulamadı diye müşteriye hata göstermenin anlamı yok.
    Ancak loglanır; sürekli tekrarlıyorsa fark edilir.
    """
    try:
        coffee_g = milk_ml = choc_g = 0.0
        raw_recipe = None
        recipe_name = catalog.name(button_number)

        # ButtonNumber DEĞİL, RecipeNumber gönderilir — bkz. modül başlığı
        recipe_no = catalog.recipe_number(button_number)

        if recipe_no is None:
            log(job_id, "STEP_8_STOCK",
                f"⚠️  Btn={button_number} katalogda yok — varsayılan miktarlar kullanılacak.")
        else:
            log(job_id, "STEP_8_STOCK",
                f"Reçete sorgulanıyor → btn={button_number} recipe={recipe_no}")
            try:
                headers = {"Authorization": f"Bearer {COFFEE_MACHINE_TOKEN}"}
                async with websockets.connect(
                    f"ws://{COFFEE_MACHINE_IP}:{COFFEE_MACHINE_PORT}/",
                    additional_headers=headers,
                    open_timeout=5,
                    close_timeout=3,
                ) as ws:
                    await ws.send(json.dumps({
                        "function"    : "getRecipeComposition",
                        "RecipeNumber": str(recipe_no),
                    }))
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=6.0))

                if isinstance(payload, list):
                    for item in payload:
                        if not isinstance(item, dict):
                            continue
                        if "Name" in item:
                            recipe_name = item.get("Name", recipe_name)
                        if "Parts" in item:
                            raw_recipe = item
                            amounts  = stock_service.extract_recipe_amounts(item["Parts"])
                            coffee_g = amounts["coffee_g"]
                            milk_ml  = amounts["milk_ml"]
                            choc_g   = amounts["choc_g"]
                            log(job_id, "STEP_8_STOCK",
                                f"Reçete: {recipe_name} → kahve={coffee_g}g "
                                f"süt={milk_ml}ml çikolata={choc_g}g")

                if raw_recipe is None:
                    log(job_id, "STEP_8_STOCK", "⚠️  Reçete içeriği alınamadı, varsayılan kullanılacak.")

            except Exception as e:
                log(job_id, "STEP_8_STOCK", f"⚠️  getRecipeComposition hatası: {e} — varsayılan kullanılacak.")

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
        log(job_id, "STEP_8_STOCK", "✅ Stok düşüldü ve sipariş logu yazıldı.")

    except Exception as e:
        log(job_id, "STEP_8_STOCK", f"⚠️  Stok güncelleme hatası (yoksayıldı): {e}")
