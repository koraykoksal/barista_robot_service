"""
service/order_service.py

Sipariş akışının tamamı. Dışarıya açık fonksiyonlar:

    run_order_flow(job_id, message, button_number, jobs, jobs_lock, ...)
    plan_syrups(button_number, channels)   — şurup kapısı (route da kullanır)

──────────────────────────────────────────────────────────────────
SİPARİŞ TİPLERİ
──────────────────────────────────────────────────────────────────
Tek bir akış, iki bayrağa göre dallanır: `ice` ve `syrups`.

  Tip 1  Standart          buz yok, şurup yok
  Tip 2  Şuruplu           buz yok, şurup var
  Tip 3  Buzlu             buz var, şurup yok
  Tip 4  Buzlu + şuruplu   ikisi de var   (önce buz, sonra şurup)

──────────────────────────────────────────────────────────────────
SİNYALLER
──────────────────────────────────────────────────────────────────
  UYGULAMA YAZAR (DO)                 ROBOT YAZAR (DI)
  ────────────────────                ─────────────────
  DO0  bardağı al, başla              DI9  buzu aldım
  DO7  şurup bitti, makineye yerleştir DI8 şurup istasyonundayım
  DO2  içecek hazır, teslim et        DI1  makineye yerleştirdim
                                      DI3  teslim ettim

  SysVar1  1 → şurup istasyonuna uğra   (config: ROBOT_SYSVAR_SYRUP)
  SysVar2  1 → buz istasyonuna uğra     (config: ROBOT_SYSVAR_ICE)
  SysVar3  0 → yalnızca buz             (config: ROBOT_SYSVAR_ICE_TYPE)
           1 → buz + su
           Robot buz haznesinden ne alacağını kendi bilemez; yalnızca
           SysVar2=1 iken anlamlıdır.

SysVar'lar DO0'DAN ÖNCE yazılır, ardından ROBOT_SYSVAR_SETTLE (varsayılan
0,5 sn) beklenir. Robot bardağı almadan önce rotanın tamamını bilmelidir;
SysVar ve DO ayrı XML-RPC çağrılarıyla gittiği için DO0'ı erken gören
robot SysVar'ın eski değerini okuyup yanlış istasyona gidebilir.

Pin ve SysVar numaraları core/config.py'den gelir, koda gömülü değildir.

──────────────────────────────────────────────────────────────────
AKIŞ
──────────────────────────────────────────────────────────────────
  PRE   makine durumu
  0     robot bağlantısı
  0.1   robot otomatik modda mı
  0.5   TÜM çıkış sinyallerini ve SysVar'ları sıfırla
  0.6   DI1 / DI3 / DI8 / DI9 LOW mu doğrula
  0.7   şurup planı + stok kapısı  (engel varsa robot HİÇ hareket etmez)
  ────────────────────────────────────────────────
  1     SysVar buz / buz tipi / şurup → rotayı bildir, sonra 0,5 sn bekle
  2     DO0 = 1                     → bardağı al
  3     [buzlu]  DI9 bekle          ← buz alındı (pasif kontrol)
  4     [şuruplu] DI8 bekle         ← şurup istasyonunda
        [şuruplu] kanalları sırayla akıt
        [şuruplu] DO7 = 1           → makineye yerleştir
  5     DI1 bekle                   ← yerleştirildi
  6     startBeverage               → kahve makinesi (arka planda)
  7     TIMER                       → brew_seconds
  8     DO2 = 1                     → teslim et
  9     DI3 bekle                   ← teslim edildi → status=done
  10    coffee_task kapat, sinyalleri temizle
  11    stok düş + log yaz

DİKKAT — getRecipeComposition:
  startBeverage/checkBeverage ButtonNumber ister, getRecipeComposition
  RecipeNumber. İkisi yalnızca Espresso'da aynıdır. catalog.recipe_number()
  bu eşlemeyi yapar.
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
    ICE_TYPE_ICE,
    ICE_TYPE_ICE_WATER,
    ICE_WAIT_TIMEOUT,
    ROBOT_DI_AT_SYRUP,
    ROBOT_DI_CUP_PLACED,
    ROBOT_DI_DELIVERED,
    ROBOT_DI_ICE_TAKEN,
    ROBOT_DO_DELIVER,
    ROBOT_DO_PLACE_CUP,
    ROBOT_DO_TAKE_CUP,
    ROBOT_MODE_POLL_INTERVAL,
    ROBOT_MODE_SWITCH_TIMEOUT,
    ROBOT_SYSVAR_ICE,
    ROBOT_SYSVAR_ICE_TYPE,
    ROBOT_SYSVAR_SETTLE,
    ROBOT_SYSVAR_SYRUP,
    SYRUP_WAIT_TIMEOUT,
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
# SİPARİŞ TİPİ
# ═════════════════════════════════════════════

def order_type_label(ice: bool, has_syrup: bool) -> str:
    """Log ve teşhis için okunabilir tip adı."""
    if ice and has_syrup:
        return "Tip 4 — buzlu + şuruplu"
    if ice:
        return "Tip 3 — buzlu"
    if has_syrup:
        return "Tip 2 — şuruplu"
    return "Tip 1 — standart"


async def plan_syrups(button_number: Any, channels: Optional[List[Any]]) -> Dict[str, Any]:
    """
    Siparişin şurup planını çıkarır ve stok kapısını uygular.

    Kaynak sırası:
      1. Arayüzün seçtiği kanallar (yeni yol — müşteri şurubu seçer)
      2. Kanal gelmemişse içeceğin sabit tarifi (/syrup/recipes ucu)

    İkinci yol geriye uyumluluk içindir: tarif tanımlı bir kurulumda
    arayüz güncellenmese de şuruplu akış çalışmaya devam eder.

    Dönen sözlük stock_service.resolve_syrup_selection ile aynı biçimdedir:
      { ok, items: [{channel, name, dose_ml}], total_ml, blocked }
    """
    if channels:
        return await stock_service.resolve_syrup_selection(channels)

    recipe = get_syrup_recipe(button_number)
    if not recipe:
        return {"ok": True, "items": [], "total_ml": 0.0, "blocked": None}

    channel = recipe.get("channel")
    # Rota tarifi "ml" anahtarıyla kaydeder; eski kayıtlar "qty_ml" taşıyor.
    need_ml = recipe.get("ml", recipe.get("qty_ml"))
    if not channel or not need_ml:
        return {"ok": True, "items": [], "total_ml": 0.0, "blocked": None}

    avail = await stock_service.check_syrup_available(channel, float(need_ml))
    name = avail.get("name") or f"Kanal {channel}"
    if not avail["ok"]:
        return {"ok": False, "items": [], "total_ml": 0.0, "blocked": {
            "channel": channel, "name": name, "reason": avail.get("reason"),
            "remaining_ml": avail.get("remaining_ml"), "need_ml": float(need_ml),
            "message": f"{name} şurubu yetersiz — bu içecek geçici olarak verilemiyor.",
        }}

    item = {"channel": int(channel), "name": name, "dose_ml": float(need_ml)}
    return {"ok": True, "items": [item], "total_ml": item["dose_ml"], "blocked": None}


# ═════════════════════════════════════════════
# SİNYAL TEMİZLEME
# ═════════════════════════════════════════════

async def cleanup_signals(job_id: str = "") -> None:
    """
    Hata / timeout sonrası tüm çıkış sinyallerini ve SysVar'ları sıfırlar.

    Bu adım atlanırsa robot bir sonraki siparişte "zaten bardak al"
    sinyalini yüksek görür, ya da geçen siparişten kalan şurup/buz
    bayrağıyla yanlış istasyona uğrar.
    """
    log(job_id, "CLEANUP", "Çıkış sinyalleri ve SysVar'lar sıfırlanıyor...")

    for label, do_idx in (("DO_TAKE_CUP",  ROBOT_DO_TAKE_CUP),
                          ("DO_PLACE_CUP", ROBOT_DO_PLACE_CUP),
                          ("DO_DELIVER",   ROBOT_DO_DELIVER)):
        try:
            await asyncio.to_thread(robot_mgr.set_do, do_idx, False)
            log(job_id, "CLEANUP", f"  DO{do_idx} ({label}) → LOW ✅")
        except Exception as e:
            log(job_id, "CLEANUP", f"  DO{do_idx} ({label}) → LOW HATA: {e}")

    for label, var_id in (("SYSVAR_SYRUP",    ROBOT_SYSVAR_SYRUP),
                          ("SYSVAR_ICE",      ROBOT_SYSVAR_ICE),
                          ("SYSVAR_ICE_TYPE", ROBOT_SYSVAR_ICE_TYPE)):
        try:
            await asyncio.to_thread(robot_mgr.set_sysvar, var_id, 0)
            log(job_id, "CLEANUP", f"  SysVar{var_id} ({label}) → 0 ✅")
        except Exception as e:
            log(job_id, "CLEANUP", f"  SysVar{var_id} ({label}) → 0 HATA: {e}")


# ═════════════════════════════════════════════
# ANA AKIŞ
# ═════════════════════════════════════════════

async def run_order_flow(
    job_id       : str,
    message      : Dict[str, Any],
    button_number: Any,
    jobs         : Dict[str, Any],
    jobs_lock    : asyncio.Lock,
    ice            : Optional[bool] = None,
    ice_water      : Optional[bool] = None,
    syrup_channels : Optional[List[Any]] = None,
) -> None:
    """
    Sipariş akışını baştan sona yürütür.
    Sonuç (done / error / timeout) jobs[job_id] içine yazılır.

    ice:
        True/False açıkça verilirse o geçerlidir. None ise içeceğin
        katalogdaki `temperature` alanına bakılır. Arayüzün gönderdiği
        değer önceliklidir çünkü katalogda olmayan içecekler de olabilir.

    ice_water:
        Buz istasyonunda su da alınsın mı (SysVar3). None ise katalogdaki
        `ice_water` alanına bakılır. `ice` False iken anlamsızdır.

    syrup_channels:
        Müşterinin seçtiği şurup kanalları [1..8]. Boşsa içeceğin sabit
        tarifi denenir (bkz. plan_syrups).
    """

    coffee_task : Optional[asyncio.Task] = None
    watcher_task: Optional[asyncio.Task] = None
    t_start     = time.monotonic()
    abort_event = asyncio.Event()

    use_ice   = catalog.is_iced(button_number) if ice is None else bool(ice)
    ice_water = (catalog.is_ice_water(button_number)
                 if ice_water is None else bool(ice_water))

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

    async def _wait_di(di_id: int, label: str, timeout: float) -> float:
        """DI sinyalini bekler; gelmezse TimeoutError fırlatır. Geçen süreyi döner."""
        t_wait = time.monotonic()
        ok = await asyncio.to_thread(robot_mgr.wait_di_true, di_id, timeout, 0.1)
        elapsed = time.monotonic() - t_wait
        if not ok:
            raise TimeoutError(f"DI{di_id} ({label}) timeout — {elapsed:.1f}s beklendi")
        return elapsed

    async def _set_do(do_id: int, value: bool, label: str) -> None:
        """DO yazar; SDK hata kodu dönerse akışı durdurur."""
        err = await asyncio.to_thread(robot_mgr.set_do, do_id, value)
        if err != 0:
            raise Exception(f"DO{do_id} ({label}) = {'HIGH' if value else 'LOW'} "
                            f"yazılamadı, err={err}")

    async def _set_sysvar(var_id: int, value: int, label: str) -> None:
        """SysVar yazar; SDK hata kodu dönerse akışı durdurur."""
        err = await asyncio.to_thread(robot_mgr.set_sysvar, var_id, value)
        if err != 0:
            raise Exception(f"SysVar{var_id} ({label}) = {value} yazılamadı, err={err}. "
                            f"Robot programındaki değişken indeksi ile "
                            f"core/config.py ayarı uyuşuyor mu?")

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

        # ══ ADIM 0.5: Sinyalleri sıfırla ═════
        log(job_id, "STEP_0_5_RESET", "Çıkışlar ve SysVar'lar sıfırlanıyor...")
        await cleanup_signals(job_id)
        await asyncio.sleep(0.2)
        log(job_id, "STEP_0_5_RESET", "✅ Sıfırlandı.")

        # ══ ADIM 0.6: DI temiz mi ════════════
        # Sipariş tipine göre yalnızca kullanılacak girişler beklenir;
        # buz istasyonu olmayan bir kurulumda DI9 hiç bağlı olmayabilir.
        di_to_check = [(ROBOT_DI_CUP_PLACED, "yerleştirildi"),
                       (ROBOT_DI_DELIVERED,  "teslim edildi")]
        if use_ice:
            di_to_check.append((ROBOT_DI_ICE_TAKEN, "buz alındı"))

        log(job_id, "STEP_0_6_DI", "Giriş sinyalleri LOW bekleniyor...")
        for di_id, label in di_to_check:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if await asyncio.to_thread(robot_mgr.read_di_status, di_id) == 0:
                    break
                log(job_id, "STEP_0_6_DI", f"⏳ DI{di_id} ({label}) hâlâ HIGH...")
                await asyncio.sleep(0.1)
            else:
                log(job_id, "STEP_0_6_DI",
                    f"⚠️  DI{di_id} ({label}) 5s içinde LOW olmadı, devam.")
        log(job_id, "STEP_0_6_DI", "✅ Giriş sinyalleri temiz.")

        # ══ ADIM 0.7: Şurup planı + stok kapısı ══
        # Robot HAREKET ETMEDEN önce çözülür. Kanal yetersizse bardak
        # boşuna alınmaz ve dozaj yarıda kesilmez (EVT:DISP:ABORT).
        plan = await plan_syrups(button_number, syrup_channels)
        if not plan["ok"]:
            blocked = plan["blocked"] or {}
            raise Exception(blocked.get("message", "Şurup stoğu yetersiz."))

        syrup_items = plan["items"]
        has_syrup   = bool(syrup_items)

        # Demleme süresi bilinmiyorsa AKIŞ HİÇ BAŞLAMAMALI.
        #
        # catalog.brew_seconds() katalogda olmayan butonlar için 0 döner.
        # Eski davranış "timer yok — devam" deyip geçiyordu: startBeverage
        # gönderildikten hemen sonra DO2 yazılıyor, robot içecek hazır
        # olmadan bardağı alıp teslim ediyordu. Sessiz ve tehlikeli.
        #
        # Kontrol burada, robot HAREKET ETMEDEN yapılır; bardak boşuna
        # alınmaz. Yeni bir buton eklerken core/catalog.py'ye kaydını
        # (recipe, brew_seconds, malzemeler) girmek zorunludur.
        if catalog.brew_seconds(button_number) <= 0:
            raise Exception(
                f"Buton {button_number} core/catalog.py içinde tanımlı değil "
                f"(demleme süresi bilinmiyor). Bu içecek hazırlanamaz: süre "
                f"olmadan robot bardağı içecek hazır olmadan alır. "
                f"Katalog kaydını ekleyin."
            )

        log(job_id, "STEP_0_7_PLAN",
            f"{order_type_label(use_ice, has_syrup)} | "
            f"buz={'buz + su' if (use_ice and ice_water) else 'buz' if use_ice else 'yok'} | "
            f"şurup={[(i['name'], i['dose_ml']) for i in syrup_items] or 'yok'}")

        # ══ ADIM 1: Rotayı bildir (SysVar) ═══
        # DO0'DAN ÖNCE — robot bardağı almadan önce nereye uğrayacağını
        # ve buz haznesinden ne alacağını bilmeli.
        await _update("set_sysvars")
        if use_ice:
            ice_type = ICE_TYPE_ICE_WATER if ice_water else ICE_TYPE_ICE
            log(job_id, "STEP_1_SYSVAR", f"SysVar{ROBOT_SYSVAR_ICE} → 1 (buz istasyonuna uğra)")
            await _set_sysvar(ROBOT_SYSVAR_ICE, 1, "buz")
            log(job_id, "STEP_1_SYSVAR",
                f"SysVar{ROBOT_SYSVAR_ICE_TYPE} → {ice_type} "
                f"({'buz + su' if ice_water else 'yalnızca buz'})")
            await _set_sysvar(ROBOT_SYSVAR_ICE_TYPE, ice_type, "buz tipi")
        if has_syrup:
            log(job_id, "STEP_1_SYSVAR", f"SysVar{ROBOT_SYSVAR_SYRUP} → 1 (şurup istasyonuna uğra)")
            await _set_sysvar(ROBOT_SYSVAR_SYRUP, 1, "şurup")
        if not use_ice and not has_syrup:
            log(job_id, "STEP_1_SYSVAR", "Ara istasyon yok — SysVar'lar 0 kalıyor.")

        # SysVar'lar denetleyicide otursun diye DO yazmadan önce beklenir.
        # SysVar ve DO ayrı XML-RPC çağrılarıyla gider; robot DO0'ı erken
        # görürse SysVar'ın eski değerini okuyup yanlış istasyona gidebilir.
        log(job_id, "STEP_1_SYSVAR",
            f"SysVar'ların oturması için {ROBOT_SYSVAR_SETTLE:.2f}s bekleniyor...")
        await asyncio.sleep(ROBOT_SYSVAR_SETTLE)

        # ══ ADIM 2: DO0=True (bardak al) ═════
        await _update("set_do0_true")
        log(job_id, "STEP_2_DO0", f"DO{ROBOT_DO_TAKE_CUP} → HIGH (bardağı al)...")
        await _set_do(ROBOT_DO_TAKE_CUP, True, "bardağı al")
        await asyncio.sleep(0.15)
        log(job_id, "STEP_2_DO0", "✅ DO0 → HIGH")

        # ══ ADIM 3: BUZ (Tip 3 / Tip 4) ══════
        # Buz makinesini robot kendi rölesiyle tetikler; uygulama
        # yalnızca "buzu aldım" onayını bekler — pasif kontrol.
        if use_ice:
            await _update("wait_di9_ice", "waiting")
            log(job_id, "STEP_3_ICE",
                f"DI{ROBOT_DI_ICE_TAKEN} bekleniyor (buz alındı, timeout={ICE_WAIT_TIMEOUT}s)...")
            elapsed = await _wait_di(ROBOT_DI_ICE_TAKEN, "buz alındı", ICE_WAIT_TIMEOUT)
            log(job_id, "STEP_3_ICE", f"✅ DI{ROBOT_DI_ICE_TAKEN} HIGH ({elapsed:.1f}s) — buz alındı")
        else:
            log(job_id, "STEP_3_ICE", "Buzsuz sipariş — buz istasyonu atlandı.")

        # ══ ADIM 4: ŞURUP (Tip 2 / Tip 4) ════
        if has_syrup:
            await _update("wait_di8_syrup", "waiting")
            log(job_id, "STEP_4_SYRUP",
                f"DI{ROBOT_DI_AT_SYRUP} bekleniyor (şurup istasyonunda, "
                f"timeout={SYRUP_WAIT_TIMEOUT}s)...")
            elapsed = await _wait_di(ROBOT_DI_AT_SYRUP, "şurup istasyonunda", SYRUP_WAIT_TIMEOUT)
            log(job_id, "STEP_4_SYRUP",
                f"✅ DI{ROBOT_DI_AT_SYRUP} HIGH ({elapsed:.1f}s) — bardak şurup istasyonunda")

            await _update("syrup_dispense")
            await _dispense_all(job_id, syrup_items)

            log(job_id, "STEP_4_SYRUP",
                f"DO{ROBOT_DO_PLACE_CUP} → HIGH (şurup bitti, makineye yerleştir)...")
            await _update("set_do7_true")
            await _set_do(ROBOT_DO_PLACE_CUP, True, "makineye yerleştir")
            await asyncio.sleep(0.15)
            log(job_id, "STEP_4_SYRUP", f"✅ DO{ROBOT_DO_PLACE_CUP} → HIGH")
        else:
            log(job_id, "STEP_4_SYRUP", "Şurupsuz sipariş — şurup istasyonu atlandı.")

        # ══ ADIM 5: DI1=True bekle ═══════════
        await _update("wait_di1_robot_ready", "waiting")
        log(job_id, "STEP_5_DI1",
            f"DI{ROBOT_DI_CUP_PLACED} bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        elapsed = await _wait_di(ROBOT_DI_CUP_PLACED, "makineye yerleştirildi", DI_WAIT_TIMEOUT)
        log(job_id, "STEP_5_DI1",
            f"✅ DI{ROBOT_DI_CUP_PLACED} HIGH ({elapsed:.1f}s) — bardak makinede")

        # ══ ADIM 6: startBeverage ════════════
        await _update("coffee_task_start")
        log(job_id, "STEP_6_COFFEE", "startBeverage gönderiliyor (arka planda)...")

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
        log(job_id, "STEP_6_COFFEE", "☕ coffee_task + watcher_task başlatıldı.")

        # ══ ADIM 7: TIMER ════════════════════
        delay = catalog.brew_seconds(button_number)
        if delay > 0:
            log(job_id, "STEP_7_TIMER", f"Btn {button_number} → {delay}s timer başladı...")
            await _update(f"timer_{delay}s", "waiting")
            await asyncio.sleep(delay)
            log(job_id, "STEP_7_TIMER", f"✅ Timer bitti ({delay}s).")
        else:
            log(job_id, "STEP_7_TIMER", f"Btn {button_number} için timer yok — devam.")

        if abort_event.is_set():
            state    = await monitor.get_state()
            blocking = [c for c in (state.get("errors") or []) if c not in NON_BLOCKING_ERROR_CODES]
            detail   = describe_machine_errors(blocking) if blocking else "İçecek hazırlanırken makine hatası."
            raise Exception(f"Makine hatası (timer sırasında): {detail}")

        # ══ ADIM 8: DO2=True (teslim et) ═════
        await _update("set_do2_true")
        log(job_id, "STEP_8_DO2", f"DO{ROBOT_DO_DELIVER} → HIGH (içecek hazır, teslim et)...")
        await _set_do(ROBOT_DO_DELIVER, True, "teslim et")
        await asyncio.sleep(0.20)
        log(job_id, "STEP_8_DO2", f"✅ DO{ROBOT_DO_DELIVER} → HIGH")

        # ══ ADIM 9: DI3=True bekle ═══════════
        await _update("wait_di3_robot_done", "waiting")
        log(job_id, "STEP_9_DI3",
            f"DI{ROBOT_DI_DELIVERED} bekleniyor (timeout={DI_WAIT_TIMEOUT}s)...")
        elapsed = await _wait_di(ROBOT_DI_DELIVERED, "teslim edildi", DI_WAIT_TIMEOUT)
        log(job_id, "STEP_9_DI3",
            f"✅ DI{ROBOT_DI_DELIVERED} HIGH ({elapsed:.1f}s) — robot teslim etti")

        # Frontend'i HEMEN bilgilendir — stok yazımı beklenmez
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id]["phase"]  = "robot_delivered"
                jobs[job_id]["status"] = "done"
        log(job_id, "STEP_9_DI3", "✅ phase=robot_delivered, status=done")

        # ══ ADIM 10: coffee_task kapat ═══════
        await _update("finalizing", "done")
        log(job_id, "STEP_10_CLEANUP", "coffee_task kapatılıyor...")
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
                log(job_id, "STEP_10_CLEANUP", "coffee_task 2s içinde bitmedi, iptal edildi.")
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

        log(job_id, "STEP_10_CLEANUP", "✅ coffee_task temizlendi.")

        # ══ Sinyalleri temizle ═══════════════
        log(job_id, "DONE", f"✅ Sipariş tamamlandı — toplam {time.monotonic() - t_start:.1f}s")
        await cleanup_signals(job_id)
        await asyncio.sleep(0.2)

        # ══ ADIM 11: Stok ════════════════════
        await _update_stock(job_id, button_number, results)

        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status"     : "done",
                    "phase"      : "done",
                    "finished_at": time.time(),
                    "result"     : results,
                })

    except asyncio.CancelledError:
        # Sunucu kapanıyor / --reload yeniden başlatıyor.
        #
        # DÜZELTİLEN HATA: CancelledError bir BaseException'dır, yani
        # aşağıdaki "except Exception" onu YAKALAMAZ. Sonuç: sipariş
        # ortasında yeniden başlatma olduğunda cleanup_signals hiç
        # çalışmıyor ve DO sinyalleri robotta ASILI KALIYORDU. Örneğin
        # DO2 (teslim et) HIGH kalırsa robot bir sonraki siparişte
        # bayat sinyali görür ve akış baştan bozulur.
        log(job_id, "CANCELLED", "⚠️  Sipariş iptal edildi (kapanış veya yeniden "
                                 "yükleme) — sinyaller temizleniyor.")
        await _cancel_tasks()
        try:
            # Kapanışta kısa bir pencere var; temizlik gecikirse
            # sinyalleri asılı bırakmaktansa vazgeçilir.
            await asyncio.wait_for(cleanup_signals(job_id), timeout=4.0)
        except Exception as e:
            log(job_id, "CANCELLED", f"⚠️  Sinyal temizliği tamamlanamadı: {e}")
        async with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update({
                    "status": "error", "phase": "aborted",
                    "finished_at": time.time(),
                    "error": "Sipariş sunucu yeniden başlatıldığı için yarıda kesildi.",
                })
        raise

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
# ADIM 4 — ŞURUP DOZAJI
# ═════════════════════════════════════════════

async def _dispense_all(job_id: str, items: List[Dict[str, Any]]) -> None:
    """
    Seçilen kanalları SIRAYLA akıtır.

    Bardak şurup istasyonunda beklerken her kanal tek tek çalıştırılır;
    cihaz aynı anda yalnızca bir kanaldan akıtabilir (E409 "kanalda dozaj
    sürüyor"). Bir kanal başarısız olursa akış durur — eksik reçeteli
    içecek müşteriye verilmez.

    Stok düşümü her kanaldan SONRA yapılır: yarıda kesilen dozajda
    (EVT:DISP:ABORT) gerçekten akan miktar kaydedilir.
    """
    total = len(items)
    for idx, item in enumerate(items, start=1):
        channel = item["channel"]
        dose    = float(item["dose_ml"])
        name    = item["name"]

        log(job_id, "STEP_4_SYRUP",
            f"[{idx}/{total}] {name} → kanal {channel}, {dose:.1f} mL akıtılıyor...")
        try:
            result = await syrup.dispense(channel, dose)
            log(job_id, "STEP_4_SYRUP",
                f"[{idx}/{total}] ✅ {name} tamam ({result.get('elapsed_s', '?')}s)")
            try:
                await stock_service.consume_syrup(channel, dose, job_id)
            except Exception as e:
                # Stok yazılamadı ama şurup fiziksel olarak aktı; siparişi
                # bunun için durdurmak anlamsız. Loglanır, sürer.
                log(job_id, "STEP_4_SYRUP", f"⚠️  {name} stok düşümü yazılamadı: {e}")

        except SyrupAbortError as e:
            # Dozaj yarıda kesildi (genelde pompa mekanik ayrılması).
            # Akıtılabilen kadarını yine de stoktan düş.
            try:
                await stock_service.consume_syrup(channel, float(e.dispensed_ml), job_id)
            except Exception:
                pass
            log(job_id, "STEP_4_SYRUP",
                f"❌ {name} yarıda kesildi: {e.dispensed_ml:.1f}/{e.requested_ml:.1f} mL "
                f"(sebep={e.reason})")
            raise Exception(
                f"Şurup dozajı yarıda kesildi ({name}, kanal {channel}, {e.reason}): "
                f"{e.requested_ml:.0f} mL istendi, {e.dispensed_ml:.0f} mL akıtıldı. "
                f"İçecek eksik kaldı."
            )
        except TimeoutError as e:
            raise TimeoutError(f"Şurup zaman aşımı ({name}, kanal {channel}): {e}")
        except Exception as e:
            raise Exception(f"Şurup hatası ({name}, kanal {channel}): {e}")


# ═════════════════════════════════════════════
# ADIM 11 — STOK GÜNCELLEME
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
            log(job_id, "STEP_11_STOCK",
                f"⚠️  Btn={button_number} katalogda yok — varsayılan miktarlar kullanılacak.")
        else:
            log(job_id, "STEP_11_STOCK",
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
                            log(job_id, "STEP_11_STOCK",
                                f"Reçete: {recipe_name} → kahve={coffee_g}g "
                                f"süt={milk_ml}ml çikolata={choc_g}g")

                if raw_recipe is None:
                    log(job_id, "STEP_11_STOCK", "⚠️  Reçete içeriği alınamadı, varsayılan kullanılacak.")

            except Exception as e:
                log(job_id, "STEP_11_STOCK", f"⚠️  getRecipeComposition hatası: {e} — varsayılan kullanılacak.")

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
        log(job_id, "STEP_11_STOCK", "✅ Stok düşüldü ve sipariş logu yazıldı.")

    except Exception as e:
        log(job_id, "STEP_11_STOCK", f"⚠️  Stok güncelleme hatası (yoksayıldı): {e}")
