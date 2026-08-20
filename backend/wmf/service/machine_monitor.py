"""
machine_monitor.py

WMF CMRemote4.x API — Kalıcı push dinleyici.

API Referansı: CMRemote4.x 10.05.2022

Abone olunan push kanalları:
────────────────────────────────────────────────────────
1) startPushErrors (API dok. sayfa 26)
   Mevcut hata varsa bağlantıda hemen gelir:
     [{"function":"startPushErrors"},{"returnvalue":0},{"Info":"currentErrors"},{"ErrorCode":68},{"Time":...}]
   Yeni hata:
     [{"function":"startPushErrors"},{"Info":"new Error"},{"ErrorCode":68},{"Time":...}]
   Hata geçti:
     [{"function":"startPushErrors"},{"Info":"gone Error"},{"ErrorCode":68}]

2) startPushCleaningRinsingNotifications (API dok. sayfa 35)
   Temizlik/durulama süresi yaklaştığında push gelir:
     [{"function":"startPushCleaningRinsingNotifications"},
      {"type":"getMilkReplaceState"},
      {"dueInSeconds":2000},
      {"durationInSeconds":25.4}]

   "type" değerleri (API dok.):
     getSystemCleaningState
     getMilkCleaningState
     getFoamerRinsingState
     getMixerRinsingState
     getMilkReplacementState  (eskisi: getMilkReplaceState)
     getMilkMixerWarmRinsingState (eskisi: getMilkMixerWarmRinseState)
     getFfcFilterReplacementState

   NOT: Payload içinde "Cleaning" veya "Rinsing" key'i GELMEZ.
        Bunun yerine "type" key'i gelir. Eski kod bu yüzden
        çalışmıyordu.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set

import websockets


# Temizlik türleri — "type" key'inden gelen değerler (API dok. sayfa 35)
CLEANING_TYPES: Set[str] = {
    "getSystemCleaningState",
    "getMilkCleaningState",
    "startSystemCleaning",        # cleaning sırasında da gelebilir
    "startMilkCleaning",
    "startFollowCleaning",
}

RINSING_TYPES: Set[str] = {
    "getFoamerRinsingState",
    "getMixerRinsingState",
    "getMilkReplacementState",
    "getMilkReplaceState",        # eski ad (destekleniyor)
    "getMilkMixerWarmRinsingState",
    "getMilkMixerWarmRinseState", # eski ad (destekleniyor)
    "getFfcFilterReplacementState",
    "startFoamerRinsing",
    "startMixerRinsing",
    "startWarmRinsing",
    "startMilkReplacement",
    "startMilkMixerWarmRinsing",
}


# ─────────────────────────────────────────────────────────────────
# NON-BLOCKING HATA KODLARI
# ─────────────────────────────────────────────────────────────────
# Bu kodlar makine tarafından "hata" olarak push edilir ama
# içecek hazırlanmasını ENGELLEMEZ (BlockingError değildir).
# has_error = False tutulur, sipariş ekranı pasifleşmez.
# Kaynak: WMF servis dökümantasyonu + saha deneyimi
#
# Kodu buraya ekleyerek yeni non-blocking hataları tanımlayabilirsiniz.
# ─────────────────────────────────────────────────────────────────
NON_BLOCKING_ERROR_CODES: set = {
    # Durulama / temizlik bildirimleri (yakında yapılmalı — engellemez)
    752,   # Milk system rinse due soon
    753,   # Milk system rinse overdue (uyarı, henüz bloklamaz)
    754,   # Milk cleaner due soon
    755,   # Milk cleaner overdue
    760,   # System clean due soon
    761,   # System clean overdue
    764,   # getMilkMixerWarmRinsingState — ılık durulama yakında
    765,   # Foamer rinse due soon
    766,   # Mixer rinse due soon
    # Makine ısınıyor (geçici, sipariş alabilir)
    136,   # Makine ısınıyor
}

class MachineMonitor:
    """
    Kahve makinesine kalıcı bir WebSocket bağlantısı açar; hata ve
    temizlik bildirimlerini dinleyerek dahili durumu günceller.

    Bağlantı koparsa otomatik olarak yeniden bağlanır.
    """

    def __init__(
        self,
        ip: str,
        port: int,
        token: Optional[str] = None,
        *,
        ping_interval   : int   = 30,
        ping_timeout    : int   = 10,
        open_timeout    : int   = 5,
        close_timeout   : int   = 5,
        reconnect_wait_s: float = 3.0,
    ):
        self.ip    = ip
        self.port  = int(port)
        self.token = token
        self.ws_uri = f"ws://{self.ip}:{self.port}/"

        self.ping_interval    = ping_interval
        self.ping_timeout     = ping_timeout
        self.open_timeout     = open_timeout
        self.close_timeout    = close_timeout
        self.reconnect_wait_s = reconnect_wait_s

        self.state: Dict[str, Any] = {
            "online"             : False,
            "has_error"          : False,  # herhangi bir hata var mı (blocking + non-blocking)
            "has_blocking_error" : False,  # sadece sipariş engelleyen hatalar
            "errors"             : [],     # tüm aktif hata kodları [int]
            "error_texts"        : {},     # kod → makinenin verdiği açıklama
            "blocking_errors"    : [],     # sadece blocking hata kodları [int]
            "cleaning"           : None,   # aktif cleaning bildirimi payload'u
            "rinsing"            : None,   # aktif rinsing bildirimi payload'u
            "last_payload"       : None,   # debug — son gelen ham payload
            "last_update"        : None,
        }

        self._lock = asyncio.Lock()
        self._task : Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    # ── Yaşam döngüsü ──────────────────────────────────────────────────

    async def start(self) -> None:
        self._stop.clear()
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="MachineMonitor")
        print("[MachineMonitor] Başlatıldı.")

    async def stop(self) -> None:
        print("[MachineMonitor] Durduruluyor...")
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass   # beklenen — task iptal edildi veya zaman aşımı
            except Exception as e:
                print(f"[MachineMonitor] stop() beklenmeyen hata (yoksayıldı): {e}")
        print("[MachineMonitor] Durduruldu.")

    async def get_state(self) -> Dict[str, Any]:
        async with self._lock:
            return dict(self.state)

    # ── İç yardımcılar ─────────────────────────────────────────────────

    async def _set(self, **kwargs) -> None:
        async with self._lock:
            self.state.update(kwargs)
            self.state["last_update"] = time.time()

    def _auth_headers(self) -> Optional[Dict[str, str]]:
        if not self.token:
            return None
        return {"Authorization": f"Bearer {self.token}"}

    # ── Ana döngü ──────────────────────────────────────────────────────

    async def _run(self) -> None:
        attempt = 0

        while not self._stop.is_set():
            attempt += 1
            print(f"[MachineMonitor] Bağlanmaya çalışılıyor... (deneme #{attempt}) → {self.ws_uri}")

            try:
                async with websockets.connect(
                    self.ws_uri,
                    additional_headers=self._auth_headers(),
                    ping_interval=self.ping_interval,
                    ping_timeout =self.ping_timeout,
                    open_timeout =self.open_timeout,
                    close_timeout=self.close_timeout,
                ) as ws:
                    await self._set(online=True)
                    print(f"[MachineMonitor] ✅ Bağlantı kuruldu (deneme #{attempt}).")
                    attempt = 0  # başarılı bağlantıda sıfırla

                    # Push aboneliklerini başlat
                    await ws.send(json.dumps({"function": "startPushErrors"}))
                    print("[MachineMonitor] 📤 startPushErrors aboneliği gönderildi.")

                    await ws.send(json.dumps({"function": "startPushCleaningRinsingNotifications"}))
                    print("[MachineMonitor] 📤 startPushCleaningRinsingNotifications aboneliği gönderildi.")

                    while not self._stop.is_set():
                        raw = await ws.recv()

                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            payload = {"raw": raw}

                        print(f"[MachineMonitor] 📩 Payload alındı: {payload}")
                        await self._set(last_payload=payload)
                        await self._handle_payload(payload)

            except asyncio.CancelledError:
                print("[MachineMonitor] İptal sinyali alındı — döngü sonlandırılıyor.")
                try:
                    async with self._lock:
                        self.state["online"] = False
                        self.state["last_update"] = time.time()
                except Exception:
                    pass
                return

            except websockets.exceptions.WebSocketException as e:
                print(f"[MachineMonitor] ⚠️  WS hatası: {e}  → {self.reconnect_wait_s}s sonra yeniden denenecek.")
                await self._set(online=False)
                await asyncio.sleep(self.reconnect_wait_s)

            except OSError as e:
                print(f"[MachineMonitor] ⚠️  Ağ hatası: {e}  → {self.reconnect_wait_s}s sonra yeniden denenecek.")
                await self._set(online=False)
                await asyncio.sleep(self.reconnect_wait_s)

            except Exception as e:
                print(f"[MachineMonitor] ❌ Beklenmeyen hata: {e}  → {self.reconnect_wait_s}s sonra yeniden denenecek.")
                await self._set(online=False)
                await asyncio.sleep(self.reconnect_wait_s)

    # ── Payload işleme ──────────────────────────────────────────────────

    async def _handle_payload(self, payload: Any) -> None:
        """
        Gelen payload'u işler.

        ── startPushErrors ────────────────────────────────────────────
        Bağlantıda mevcut hata varsa:
          [{"function":"startPushErrors"},{"returnvalue":0},
           {"Info":"currentErrors"},{"ErrorCode":68},{"Time":...}]

        Yeni hata:
          [{"function":"startPushErrors"},{"Info":"new Error"},
           {"ErrorCode":68},{"Time":...}]

        Hata geçti:
          [{"function":"startPushErrors"},{"Info":"gone Error"},
           {"ErrorCode":68}]

        ── startPushCleaningRinsingNotifications ──────────────────────
        API dok. sayfa 35 — GERÇEK payload formatı:
          [{"function":"startPushCleaningRinsingNotifications"},
           {"type":"getMilkReplaceState"},
           {"dueInSeconds":2000},
           {"durationInSeconds":25.4}]

        NOT: Payload içinde "Cleaning" veya "Rinsing" key'i GELMEZ.
             "type" key'i, hangi temizlik/durulama türü olduğunu belirtir.
        """
        if not isinstance(payload, list):
            # Bazı firmware sürümleri root-object döndürebilir
            print(f"[MachineMonitor] ℹ️  Liste olmayan payload yoksayıldı: {type(payload)}")
            return

        # Payload içindeki tüm key-value'ları düz sözlüğe çıkar
        func           = None
        info           = None
        error_entries  = []     # [(kod, makinenin verdiği metin)] — SIRAYLA
        notif_type     = None   # "type" key'i — cleaning/rinsing türü
        due_seconds    = None   # "dueInSeconds"
        duration_secs  = None   # "durationInSeconds"

        # DÜZELTİLEN HATA: burada tek bir error_code değişkeni vardı ve
        # her "ErrorCode" onun üzerine yazıyordu. currentErrors paketi
        # birden fazla hata taşıdığında (sahada olağan) yalnızca SONUNCUSU
        # kaydediliyor, diğerleri sessizce düşüyordu. Örnek gerçek payload:
        #   ErrorCode 687, 184, 747, 672  →  yalnızca 672 görünüyordu.
        # Artık hepsi toplanıp tek tek işleniyor.
        #
        # "Error Text" makinenin kendi açıklaması; kodun hemen ardından
        # gelir. Kod→metin tablomuzda karşılığı olmayan kodlarda bile
        # kullanıcıya anlamlı bir mesaj gösterebilmek için saklanır.
        for item in payload:
            if not isinstance(item, dict):
                continue

            if "function" in item:
                func = item["function"]

            # startPushErrors alanları
            if "Info" in item:
                info = item["Info"]
            if "ErrorCode" in item:
                error_entries.append([item["ErrorCode"], ""])
            if "Error Text" in item and error_entries:
                text = str(item["Error Text"] or "").strip()
                if text and not error_entries[-1][1]:
                    error_entries[-1][1] = text

            # startPushCleaningRinsingNotifications alanları (API dok. sayfa 35)
            if "type" in item:
                notif_type = item["type"]
            if "dueInSeconds" in item:
                due_seconds = item["dueInSeconds"]
            if "durationInSeconds" in item:
                duration_secs = item["durationInSeconds"]

        # ── startPushErrors işleme ──────────────────────────────────
        if func == "startPushErrors":
            if not error_entries:
                # returnvalue paketi — yalnızca abone onayı
                await self._handle_push_error(info, None, "")
            for code, text in error_entries:
                await self._handle_push_error(info, code, text)

        # ── startPushCleaningRinsingNotifications işleme ────────────
        elif func == "startPushCleaningRinsingNotifications":
            await self._handle_cleaning_notification(notif_type, due_seconds, duration_secs, payload)

    # ── startPushErrors yardımcısı ──────────────────────────────────────

    async def _handle_push_error(self, info: Any, code: Any, text: str = "") -> None:
        """
        Hata ekleme / kaldırma mantığı.
        API dok. sayfa 26.

        `text` makinenin kendi açıklamasıdır ("Süt boş, lütfen
        tamamlayın."). Kod→metin tablomuzda karşılığı olmayan kodlarda
        kullanıcıya bunu göstermek "Makine hatası (kod: 747)" demekten
        çok daha faydalı.
        """
        if code is None:
            # returnvalue paketi — sadece abone onayı, hata bilgisi yok
            return

        try:
            code_int = int(code)
        except Exception:
            code_int = code

        async with self._lock:
            errors: List[Any] = list(self.state.get("errors") or [])

            if info == "new Error":
                if code_int not in errors:
                    errors.append(code_int)
                print(f"[MachineMonitor] 🔴 Yeni hata → ErrorCode={code_int} | aktif={errors}")

            elif info == "gone Error":
                errors = [e for e in errors if e != code_int]
                print(f"[MachineMonitor] 🟢 Hata geçti → ErrorCode={code_int} | kalan={errors}")

            elif info == "currentErrors":
                # Bağlantı anında mevcut hatalar bildirilir
                if code_int not in errors:
                    errors.append(code_int)
                print(f"[MachineMonitor] 🟡 Mevcut hata → ErrorCode={code_int} | aktif={errors}")

            else:
                # Bilinmeyen Info — güvenli olarak ekle
                if code_int not in errors:
                    errors.append(code_int)
                print(f"[MachineMonitor] ⚠️  Bilinmeyen Info='{info}', hata eklendi → ErrorCode={code_int}")

            texts = dict(self.state.get("error_texts") or {})
            if text:
                texts[code_int] = text
            texts = {k: v for k, v in texts.items() if k in errors}

            blocking = [e for e in errors if e not in NON_BLOCKING_ERROR_CODES]
            self.state["errors"]             = errors
            self.state["error_texts"]        = texts
            self.state["blocking_errors"]    = blocking
            self.state["has_error"]          = len(errors) > 0
            self.state["has_blocking_error"] = len(blocking) > 0
            self.state["last_update"]        = time.time()

            if errors != blocking:
                non_block = [e for e in errors if e in NON_BLOCKING_ERROR_CODES]
                print(f"[MachineMonitor] ℹ️  Non-blocking hata(lar) yoksayıldı: {non_block}")

    # ── startPushCleaningRinsingNotifications yardımcısı ────────────────

    async def _handle_cleaning_notification(
        self,
        notif_type: Optional[str],
        due_seconds: Any,
        duration_secs: Any,
        raw_payload: Any,
    ) -> None:
        """
        API dok. sayfa 35 — gerçek payload formatını işler.

        Payload örneği:
          {"function":"startPushCleaningRinsingNotifications"},
          {"type":"getMilkReplaceState"},
          {"dueInSeconds":2000},
          {"durationInSeconds":25.4}

        "type" değerine göre cleaning veya rinsing state'ini günceller.
        dueInSeconds == -1 → zamanlanmamış (otomatik tetiklemez)
        dueInSeconds == 0  → süresi geçmiş, hemen yapılmalı
        """
        if notif_type is None:
            # returnvalue paketi — sadece abone onayı
            print("[MachineMonitor] ℹ️  Cleaning/Rinsing abonelik onayı alındı.")
            return

        notification = {
            "type"            : notif_type,
            "dueInSeconds"    : due_seconds,
            "durationInSeconds": duration_secs,
            "timestamp"       : time.time(),
        }

        is_cleaning = notif_type in CLEANING_TYPES
        is_rinsing  = notif_type in RINSING_TYPES

        # Hem cleaning hem rinsing dışında kalan bilinmeyen türler
        if not is_cleaning and not is_rinsing:
            # API'de olmayan yeni bir tür olabilir — logla ama kaydet
            print(f"[MachineMonitor] ℹ️  Bilinmeyen bildirim türü: type='{notif_type}' → cleaning olarak kaydediliyor.")
            is_cleaning = True

        if is_cleaning:
            await self._set(cleaning=notification)
            due_label = (
                "zamanlanmamış" if due_seconds == -1
                else f"{due_seconds}s sonra"
                if isinstance(due_seconds, (int, float)) and due_seconds >= 0
                else str(due_seconds)
            )
            print(
                f"[MachineMonitor] 🧹 Cleaning bildirimi → "
                f"type={notif_type} | due={due_label} | "
                f"duration={duration_secs}s"
            )

        if is_rinsing:
            await self._set(rinsing=notification)
            due_label = (
                "zamanlanmamış" if due_seconds == -1
                else f"{due_seconds}s sonra"
                if isinstance(due_seconds, (int, float)) and due_seconds >= 0
                else str(due_seconds)
            )
            print(
                f"[MachineMonitor] 💧 Rinsing bildirimi → "
                f"type={notif_type} | due={due_label} | "
                f"duration={duration_secs}s"
            )
