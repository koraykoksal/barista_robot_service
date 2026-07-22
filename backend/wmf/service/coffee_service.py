"""
coffee_service.py

WMF CMRemote4.x API — WebSocket iletişim katmanı.

API Referansı: CMRemote4.x 10.05.2022

Önemli API notları:
────────────────────────────────────────────────────────
• startBeverage / checkBeverage komutlarından ÖNCE ve SONRA
  1000ms beklenmesi zorunludur. Aksi halde makine tanımsız
  davranış gösterebilir.  (API dok. sayfa 10, 12)

• Rcp State değerleri (startBeverage):
    99  → İçecek başladı, iptal edilebilir
   -99  → İçecek başladı, iptal EDİLEMEZ
     9  → İçecek bitti, makine hazır
    -9  → İçecek bitti, makine henüz hazır değil (ısınıyor vs.)
    22  → Onay bekleniyor (machine setting: Beverage confirmation)

• returnvalue tam listesi (ECMRemoteStartBeverageError):
     0  Success
     1  Offline
     2  NotReady
     3  NotInitialized
     4  BlockingError
     5  StartNotSuccess
     6  OtherBeverageRunning
     7  ParameterError
     8  NoBeverageRunning
     9  NotSuccess
    10  FunctionBusy
    11  FunctionNotAvailable
    12  TokenInvalid
    13  RecipeNumberDoesNotExist
    14  MainPageNotActive
"""

import asyncio
import json
import time
from typing import Any, Callable, Awaitable, Dict, List, Optional

import websockets
from fastapi import HTTPException

from core.ws_utils import extract_returnvalue, extract_rcp_state, ws_send_once


# API dokümantasyonunun tam returnvalue tablosu (ECMRemoteStartBeverageError)
RETURNVALUE_MAP: Dict[int, str] = {
    0:  "Success",
    1:  "Offline",
    2:  "NotReady",
    3:  "NotInitialized",
    4:  "BlockingError",
    5:  "StartNotSuccess",
    6:  "OtherBeverageRunning",
    7:  "ParameterError",
    8:  "NoBeverageRunning",
    9:  "NotSuccess",
    10: "FunctionBusy",
    11: "FunctionNotAvailable",
    12: "TokenInvalid",
    13: "RecipeNumberDoesNotExist",
    14: "MainPageNotActive",
}

# Rcp State açıklamaları (API dok. sayfa 11)
RCP_STATE_LABELS: Dict[int, str] = {
    99:  "Başladı — iptal edilebilir",
    -99: "Başladı — iptal EDİLEMEZ",
    9:   "Bitti — makine hazır",
    -9:  "Bitti — makine henüz hazır değil (ısınıyor)",
    22:  "Onay bekleniyor (Beverage confirmation ayarı aktif)",
}


class CoffeeService:

    def __init__(self):
        self.ws_ip    = "192.168.1.111"
        self.ws_port  = 25000
        self.ws_token = "0123456789abcdef0123456789abcdef"
        self.ws_uri   = f"ws://{self.ws_ip}:{self.ws_port}/"

    def _auth_headers(self) -> Dict[str, str]:
        if self.ws_token:
            return {"Authorization": f"Bearer {self.ws_token}"}
        return {}

    # ──────────────────────────────────────────────
    # BAĞLANTI TESTİ
    # ──────────────────────────────────────────────

    async def connect_test(self) -> Dict[str, Any]:
        """Yalnızca bağlan-kapat testi; mesaj göndermez."""
        try:
            async with websockets.connect(
                self.ws_uri,
                additional_headers=self._auth_headers(),
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
                open_timeout=5,
            ):
                print(f"[CoffeeService] ✅ connect_test başarılı → {self.ws_uri}")
                return {"ok": True, "ws_uri": self.ws_uri}

        except Exception as e:
            print(f"[CoffeeService] ❌ connect_test başarısız → {e}")
            return {"ok": False, "ws_uri": self.ws_uri, "error": str(e)}

    # ──────────────────────────────────────────────
    # KAHVE BAŞLAT + BİTİŞ BEKLE
    # ──────────────────────────────────────────────

    async def send_and_wait_rcp_finished(
        self,
        message: Dict[str, Any],
        overall_timeout: float = 120.0,
        recv_timeout: float = 20.0,
        max_silent_rounds: int = 6,
        on_state: Optional[Callable[[int], Awaitable[None]]] = None,
        abort_event: Optional[asyncio.Event] = None,
    ) -> List[Any]:
        """
        Kahve makinesine `message` gönderir, Rcp State 9 veya -9 gelene kadar
        WebSocket mesajlarını dinler.

        API UYARISI: startBeverage komutundan önce ve sonra 1000ms beklenmesi
        zorunludur — bu fonksiyon içinde uygulanmaktadır.

        Parametreler
        ────────────
        overall_timeout   : Toplam maksimum süre (saniye).
        recv_timeout      : Tek bir ws.recv() için maksimum bekleme (saniye).
        max_silent_rounds : Bu kadar tur üst üste mesaj gelmezse TimeoutError.
                            0 = sınırsız bekleme (dikkatli kullan).
        on_state          : Rcp State değiştiğinde çağrılacak async callback.

        Dönüş
        ─────
        Makine kayıtlı tüm payload'ların listesi.
        Rcp State 22 durumunda: {"rcp_state": 22, "error": "confirmation_required"}
        içeren bir payload eklenir ve liste döndürülür.
        """
        print(f"[CoffeeService] send_and_wait_rcp_finished başlıyor → {self.ws_uri}")
        print(f"[CoffeeService] Mesaj: {json.dumps(message)}")

        results: List[Any] = []
        loop         = asyncio.get_running_loop()
        end_at       = loop.time() + overall_timeout
        silent_count = 0
        t_start      = time.monotonic()

        async with websockets.connect(
            self.ws_uri,
            additional_headers=self._auth_headers(),
            ping_interval=30,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            print("[CoffeeService] ✅ WS bağlantısı kuruldu.")

            # API zorunluluğu: startBeverage öncesi 1000ms bekleme
            await asyncio.sleep(1.0)
            await ws.send(json.dumps(message))
            print("[CoffeeService] 📤 Mesaj gönderildi.")
            # API zorunluluğu: startBeverage sonrası 1000ms bekleme
            await asyncio.sleep(1.0)

            msg_count = 0

            while True:
                remain = end_at - loop.time()
                if remain <= 0:
                    raise asyncio.TimeoutError(
                        f"overall_timeout={overall_timeout}s doldu, Rcp State 9/-9 gelmedi."
                    )

                # ── Dışarıdan iptal sinyali kontrol et ────────────
                if abort_event is not None and abort_event.is_set():
                    elapsed = time.monotonic() - t_start
                    print(
                        f"[CoffeeService] 🛑 abort_event set — makine hatası nedeniyle "
                        f"döngü durduruluyor (+{elapsed:.1f}s)"
                    )
                    results.append({
                        "rcp_state": None,
                        "error"    : "machine_error_abort",
                        "message"  : "Makine hatası: içecek hazırlanırken hata oluştu.",
                    })
                    break

                try:
                    raw = await asyncio.wait_for(
                        ws.recv(),
                        timeout=min(recv_timeout, remain),
                    )
                    silent_count = 0
                    msg_count   += 1
                    elapsed      = time.monotonic() - t_start
                    print(f"[CoffeeService] 📩 [{msg_count}] (+{elapsed:.1f}s) raw: {raw}")

                except asyncio.TimeoutError:
                    silent_count += 1
                    print(
                        f"[CoffeeService] ⏳ Mesaj bekleniyor... "
                        f"(sessiz tur {silent_count}"
                        + (f"/{max_silent_rounds})" if max_silent_rounds > 0 else ")")
                    )

                    if max_silent_rounds > 0 and silent_count >= max_silent_rounds:
                        raise asyncio.TimeoutError(
                            f"Kahve makinesi {max_silent_rounds} tur × {recv_timeout}s"
                            f" = {max_silent_rounds * recv_timeout:.0f}s sessiz kaldı, 9/-9 gelmedi."
                        )
                    continue

                # JSON parse
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"raw": raw}

                results.append(payload)

                # Rcp State kontrolü
                rcp_state = extract_rcp_state(payload)

                if rcp_state is not None:
                    label = RCP_STATE_LABELS.get(rcp_state, f"Bilinmeyen state ({rcp_state})")
                    print(f"[CoffeeService] 🔎 Rcp State = {rcp_state} → {label}")

                    if on_state:
                        await on_state(rcp_state)

                    if rcp_state == 99:
                        print("[CoffeeService] ☕ 99 → İçecek hazırlanıyor (iptal edilebilir)...")

                    elif rcp_state == -99:
                        print("[CoffeeService] ☕ -99 → İçecek hazırlanıyor (iptal EDİLEMEZ)...")

                    elif rcp_state == 22:
                        # API dok. sayfa 11:
                        # "Beverage start requires confirmation"
                        # Machine setting: System/Digital solutions/CM-Remote/Beverage confirmation
                        elapsed = time.monotonic() - t_start
                        print(
                            f"[CoffeeService] ⚠️  Rcp State=22 → Makine onay bekliyor! "
                            f"(+{elapsed:.1f}s)"
                        )
                        print(
                            "[CoffeeService]    Makine ayarı: System > Digital solutions > "
                            "CM-Remote > Beverage confirmation"
                        )
                        # Onay state'ini sonuç listesine ekle ve döngüyü sonlandır
                        results.append({
                            "rcp_state": 22,
                            "error": "confirmation_required",
                            "message": "Beverage confirmation bekleniyor. Makine ayarını kontrol edin.",
                        })
                        break

                    elif rcp_state in (9, -9):
                        elapsed = time.monotonic() - t_start
                        print(
                            f"[CoffeeService] ✅ Rcp State={rcp_state} → Akış tamamlandı "
                            f"(toplam {elapsed:.1f}s, {msg_count} mesaj)"
                        )
                        break

                else:
                    print("[CoffeeService] ℹ️  Bu pakette Rcp State yok.")

        return results

    # ──────────────────────────────────────────────
    # IÇECEK KONTROLÜ (checkBeverage)
    # ──────────────────────────────────────────────

    async def check_beverage(
        self,
        check_message: Dict[str, Any],
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        checkBeverage mesajını makineye gönderir, returnvalue döner.
        Bağlantı/timeout hatalarında otomatik retry yapar.

        API UYARISI: checkBeverage komutundan önce ve sonra 1000ms beklenmesi
        zorunludur — bu fonksiyon içinde uygulanmaktadır.
        """
        last_error = None

        for attempt in range(1, retries + 1):
            print(f"[CoffeeService] check_beverage attempt {attempt}/{retries}...")
            try:
                # API zorunluluğu: checkBeverage öncesi 1000ms
                await asyncio.sleep(1.0)

                payload = await ws_send_once(
                    ws_uri  = self.ws_uri,
                    message = check_message,
                    token   = self.ws_token,
                    timeout = 10.0,
                )
                print(f"[CoffeeService] check_beverage ham yanıt: {payload}")

                # API zorunluluğu: checkBeverage sonrası 1000ms
                await asyncio.sleep(1.0)

                code = extract_returnvalue(payload)
                print(f"[CoffeeService] check_beverage returnvalue: {code}")

                status_label = RETURNVALUE_MAP.get(code, "Unknown") if code is not None else "Unknown"

                result = {
                    "ok"         : code == 0,
                    "returnvalue": code,
                    "status"     : status_label,
                    "sent"       : check_message,
                    "raw"        : payload,
                    "attempt"    : attempt,
                }

                print(
                    f"[CoffeeService] ✅ check_beverage sonuç: "
                    f"ok={result['ok']}, status={status_label}, code={code}"
                )
                return result

            except (asyncio.TimeoutError, OSError, websockets.exceptions.WebSocketException) as e:
                last_error = e
                print(f"[CoffeeService] ⚠️  check_beverage WS hatası (attempt {attempt}): {e}")
                if attempt < retries:
                    await asyncio.sleep(retry_delay)

            except Exception as e:
                print(f"[CoffeeService] ❌ check_beverage beklenmeyen hata: {e}")
                raise

        raise HTTPException(
            status_code=503,
            detail=(
                f"Kahve makinesine bağlanılamadı / yanıt alınamadı. "
                f"retries={retries}, son_hata={last_error}"
            ),
        )
