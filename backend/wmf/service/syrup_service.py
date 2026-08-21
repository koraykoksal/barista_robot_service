"""
syrup_service.py

LogoSurup Şurup Dispenser TCP iletişim katmanı.
Protokol: TCP port 5000, CMD/RSP/EVT satır bazlı, UTF-8, LF satır sonu.

CLI → TCP protokol karşılıkları:
  --list-motors          → bağlan + EVT:IO:PRESENCE oku
  --watch-presence       → kalıcı bağlantı + EVT:IO:* push dinle
  --daemon               → kalıcı bağlantı + CMD:DISP bekle
  --motor N --ml X       → CMD:DISP:CH=0N:QTY=X:UNIT=ML
  --ch N --ml X          → CMD:DISP:CH=0N:QTY=X:UNIT=ML (aynı)

API referansı: LogoSurup Müşteri API Kılavuzu v2.0
"""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

# ─────────────────────────────────────────────
# HATA KODLARI (API dok. v2.0)
# ─────────────────────────────────────────────
SYRUP_ERROR_CODES: Dict[str, str] = {
    "E301": "Rol ayarlanmamış — CMD:AUTH:ROLE=REMOTE gönderin veya 3 sn bekleyin",
    "E302": "Bu komut REMOTE rolünde kullanılamaz — yalnızca REMOTE komutlarını kullanın",
    "E401": "Geçersiz DISP komutu formatı — CMD:DISP:CH=01:QTY=5:UNIT=ML biçimini kontrol edin",
    "E404": "Kanal kalibre edilmemiş — cihaz sağlayıcısından kalibrasyon isteyin",
    "E405": "Kanal mekanik olarak bağlı değil — EVT:IO:PRESENCE ile kontrol edin",
    "E406": "Miktar çok küçük — mL miktarını artırın",
    "E407": "Miktar çok büyük — mL miktarını azaltın",
    "E408": "Cihaz komutu işleyemeden zaman aşımına uğradı — komutu tekrarlayın",
    "E409": "Kanalda dozaj sürüyor — COMPLETE/ABORT satırını bekleyin",
    "E501": "İşlem sürüyor (temizlik/dolum) — bitmesini bekleyin",
    "E502": "Uygun kanal yok — süreler girili, pompalar takılı ve kalibre mi kontrol edin",
    "E503": "Dozaj sürerken işlem başlatılamaz — bitmesini bekleyin",
    "E505": "Yanlış aşamada onay — CMD:SYS:CLEAN:STATUS ile durumu okuyun",
    "E506": "Temizlik yarıda kalmış — hatlarda deterjan olabilir, dozaj kilitli (bölüm 6)",
}

SYRUP_ERROR_HTTP: Dict[str, int] = {
    "E301": 503,
    "E302": 400,
    "E401": 422,
    "E404": 404,
    "E405": 503,
    "E406": 422,
    "E407": 422,
    "E408": 504,
    "E409": 409,
    "E501": 409,
    "E502": 422,
    "E503": 409,
    "E505": 409,
    "E506": 423,   # 423 Locked — gıda güvenliği kilidi
}


def parse_err_line(line: str) -> Dict[str, Any]:
    """RSP:ERR:CODE=Exxx:MSG=... satırını parse eder."""
    result: Dict[str, Any] = {
        "raw"        : line,
        "error_code" : "",
        "error_msg"  : "",
        "description": "Bilinmeyen syrup hatası",
        "http_status": 500,
    }
    for token in line.split(":"):
        if token.startswith("CODE="):
            result["error_code"] = token[5:].strip()
        elif token.startswith("MSG="):
            result["error_msg"] = token[4:].strip()
    if result["error_code"]:
        result["description"] = SYRUP_ERROR_CODES.get(
            result["error_code"],
            f"Bilinmeyen hata kodu: {result['error_code']}"
        )
        result["http_status"] = SYRUP_ERROR_HTTP.get(result["error_code"], 500)
    return result


def _event_channel(line: str):
    """
    EVT satirindaki CH= alanini int olarak dondurur; yoksa None.
    "EVT:DISP:COMPLETE:CH=01" → 1
    """
    for token in line.split(":"):
        if token.startswith("CH="):
            try:
                return int(token[3:].lstrip("0") or "0")
            except ValueError:
                return None
    return None


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class SyrupAbortError(Exception):
    """
    Dozaj yarıda kesildi — cihaz EVT:DISP:ABORT gönderdi.

    Genellikle pompanın mekanik ayrılmasından (REASON=DISCONNECTED)
    olur. requested ve dispensed alanları telafi hesabı için taşınır:
    reçete requested_ml istedi ama yalnızca dispensed_ml akıtılabildi.
    """
    def __init__(self, channel, reason, dispensed_ml, requested_ml, raw):
        self.channel      = channel
        self.reason       = reason
        self.dispensed_ml = dispensed_ml
        self.requested_ml = requested_ml
        self.raw          = raw
        super().__init__(
            f"Dozaj yarıda kesildi (kanal {channel}, sebep={reason}): "
            f"{dispensed_ml:.3f}/{requested_ml:.3f} mL akıtıldı."
        )


class SyrupDeviceError(Exception):
    """Cihazdan RSP:ERR yanıtı geldiğinde fırlatılır."""
    def __init__(self, parsed: Dict[str, Any]):
        self.parsed = parsed
        super().__init__(
            f"Syrup {parsed['error_code']}: {parsed['description']}"
            + (f" (cihaz: {parsed['error_msg']})" if parsed["error_msg"] else "")
        )


# ─────────────────────────────────────────────
# EVT:IO:PRESENCE parse yardımcısı
# ─────────────────────────────────────────────
def parse_presence(line: str) -> Dict[str, bool]:
    """
    EVT:IO:PRESENCE:CH01=1,CH02=0,...
    → { "1": True, "2": False, ..., "8": False }
    """
    channels: Dict[str, bool] = {}
    if "EVT:IO:PRESENCE:" not in line:
        return channels
    presence_part = line.split("EVT:IO:PRESENCE:")[-1]
    for token in presence_part.split(","):
        token = token.strip()
        if "=" in token:
            ch_raw, val = token.split("=", 1)
            ch_num = ch_raw.strip().upper().replace("CH", "").lstrip("0") or "0"
            channels[ch_num] = (val.strip() == "1")
    return channels


def parse_io_state(line: str) -> Optional[Dict[str, Any]]:
    """
    EVT:IO:CH=01:STATE=1
    → { "channel": 1, "state": True }
    """
    if "EVT:IO:CH=" not in line:
        return None
    ch    = None
    state = None
    for token in line.split(":"):
        if token.startswith("CH="):
            try:
                ch = int(token[3:].lstrip("0") or "0")
            except ValueError:
                pass
        elif token.startswith("STATE="):
            state = token[6:].strip() == "1"
    if ch is not None and state is not None:
        return {"channel": ch, "state": state}
    return None


# ─────────────────────────────────────────────
# SyrupService
# ─────────────────────────────────────────────
class SyrupService:
    """
    LogoSurup TCP iletişimi.

    Stateless işlemler (her seferinde bağlan/kapat):
      ping()            → --ping
      list_motors()     → --list-motors
      dispense()        → --motor N --ml X  /  --ch N --ml X

    Kalıcı bağlantı (generator):
      watch_presence()  → --watch-presence
    """

    def __init__(self, host: str, port: int = 5000, timeout: float = 15.0):
        self.host    = host
        self.port    = port
        self.timeout = timeout

    # ─────────────────────────────────────────
    # DÜŞÜK SEVİYE
    # ─────────────────────────────────────────

    async def _open(self) -> tuple:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            return r, w
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Syrup cihazına bağlanılamadı ({self.host}:{self.port}) — "
                f"timeout={self.timeout}s"
            )
        except ConnectionRefusedError:
            raise ConnectionRefusedError(
                f"Syrup bağlantı reddedildi ({self.host}:{self.port})"
            )
        except OSError as e:
            raise OSError(f"Syrup TCP hatası ({self.host}:{self.port}): {e}")

    async def _send(self, w: asyncio.StreamWriter, cmd: str) -> None:
        w.write((cmd + "\n").encode("utf-8"))
        await w.drain()

    async def _readline(self, r: asyncio.StreamReader, timeout: float) -> str:
        raw = await asyncio.wait_for(r.readline(), timeout=timeout)
        return raw.decode("utf-8").strip()

    async def _close(self, w: asyncio.StreamWriter) -> None:
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass

    async def _auth(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> str:
        """AUTH gönderir, yanıtı okur ve döner."""
        await self._send(w, "CMD:AUTH:ROLE=REMOTE")
        try:
            return await self._readline(r, 2.0)
        except asyncio.TimeoutError:
            return ""

    async def _collect_welcome(
        self, r: asyncio.StreamReader, duration: float = 1.5
    ) -> List[str]:
        """Bağlantı sonrası cihazın gönderdiği welcome satırlarını toplar."""
        lines: List[str] = []
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            remain = deadline - time.monotonic()
            try:
                line = await asyncio.wait_for(r.readline(), timeout=min(remain, 0.4))
                text = line.decode("utf-8").strip()
                if text:
                    print(f"[SyrupService] << {text}")
                    lines.append(text)
            except asyncio.TimeoutError:
                continue
        return lines

    def _check_err(self, line: str) -> None:
        """RSP:ERR ise SyrupDeviceError fırlatır."""
        if line.startswith("RSP:ERR"):
            parsed = parse_err_line(line)
            print(
                f"[SyrupService] ❌ RSP:ERR → "
                f"code={parsed['error_code']} "
                f"msg={parsed['error_msg']} "
                f"desc={parsed['description']}"
            )
            raise SyrupDeviceError(parsed)

    # ─────────────────────────────────────────
    # CMD 1 — PING  (--ping)
    # ─────────────────────────────────────────

    async def ping(self) -> Dict[str, Any]:
        """
        CMD:SYS:PING gönderir, RSP:SYS:PONG bekler.

        CLI karşılığı: python dispense_client.py --host IP ping
        """
        t0 = time.monotonic()
        try:
            r, w = await self._open()
            try:
                await self._collect_welcome(r, 0.5)
                await self._auth(r, w)
                await self._send(w, "CMD:SYS:PING")

                # RSP:SYS:PONG satırını bul — arada başka satırlar gelebilir
                pong_received = False
                deadline      = time.monotonic() + self.timeout
                last_line     = ""
                while time.monotonic() < deadline:
                    remain = deadline - time.monotonic()
                    try:
                        line     = await self._readline(r, min(remain, 2.0))
                        last_line = line
                        print(f"[SyrupService] PING << {line}")
                        self._check_err(line)
                        if line == "RSP:SYS:PONG":
                            pong_received = True
                            break
                    except asyncio.TimeoutError:
                        break

                latency = (time.monotonic() - t0) * 1000
                return {
                    "ok"        : pong_received,
                    "pong"      : pong_received,
                    "host"      : self.host,
                    "port"      : self.port,
                    "latency_ms": round(latency, 1),
                    "response"  : last_line,
                    **({}  if pong_received else
                       {"error": f"RSP:SYS:PONG beklendi, gelen: '{last_line}'"}),
                }
            finally:
                await self._close(w)
        except SyrupDeviceError as e:
            return {"ok": False, "pong": False, "host": self.host, "port": self.port,
                    "error": str(e), "error_detail": e.parsed}
        except (TimeoutError, ConnectionRefusedError, OSError) as e:
            return {"ok": False, "pong": False, "host": self.host, "port": self.port, "error": str(e)}
        except Exception as e:
            return {"ok": False, "pong": False, "host": self.host, "port": self.port, "error": str(e)}

    # ─────────────────────────────────────────
    # CMD 2 — LIST MOTORS  (--list-motors)
    # ─────────────────────────────────────────

    async def list_motors(self) -> Dict[str, Any]:
        """
        Bağlanır, EVT:IO:PRESENCE satırını okur ve döner.
        8 kanalın fiziksel takılı olup olmadığını gösterir.

        CLI karşılığı: python dispense_client.py --host IP --list-motors
        Protokol: EVT:IO:PRESENCE:CH01=1,CH02=0,...
        """
        try:
            r, w = await self._open()
            try:
                welcome  = await self._collect_welcome(r, 2.0)
                channels: Dict[str, bool] = {}
                raw_presence = ""

                # Welcome içinde PRESENCE var mı?
                for line in welcome:
                    if "EVT:IO:PRESENCE" in line:
                        channels     = parse_presence(line)
                        raw_presence = line
                        break

                # Yoksa AUTH + bekle
                if not channels:
                    await self._auth(r, w)
                    deadline = time.monotonic() + 3.0
                    while time.monotonic() < deadline:
                        try:
                            line = await asyncio.wait_for(r.readline(), timeout=0.5)
                            text = line.decode("utf-8").strip()
                            print(f"[SyrupService] << {text}")
                            if "EVT:IO:PRESENCE" in text:
                                channels     = parse_presence(text)
                                raw_presence = text
                                break
                        except asyncio.TimeoutError:
                            continue

                # Motor listesi oluştur
                motors = []
                for ch in range(1, 9):
                    motors.append({
                        "motor"    : ch,
                        "channel"  : f"CH{ch:02d}",
                        "connected": channels.get(str(ch), False),
                    })

                presence_ok = bool(channels)  # EVT:IO:PRESENCE parse edildiyse True
                return {
                    "ok"          : presence_ok,
                    "presence"    : presence_ok,   # EVT:IO:PRESENCE alındıysa True
                    "host"        : self.host,
                    "port"        : self.port,
                    "motors"      : motors,
                    "channels"    : channels,
                    "raw"         : raw_presence,
                    **({}  if presence_ok else
                       {"warning": "EVT:IO:PRESENCE satırı alınamadı — cihaz hazır olmayabilir"}),
                }
            finally:
                await self._close(w)

        except (TimeoutError, ConnectionRefusedError, OSError) as e:
            return {"ok": False, "host": self.host, "port": self.port,
                    "motors": [], "channels": {}, "error": str(e)}
        except Exception as e:
            return {"ok": False, "host": self.host, "port": self.port,
                    "motors": [], "channels": {}, "error": str(e)}

    # ─────────────────────────────────────────
    # CMD 3 — DISPENSE  (--motor N --ml X  /  --ch N --ml X)
    # ─────────────────────────────────────────

    async def dispense(
        self,
        channel : int,
        qty_ml  : float,
        timeout : Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Belirtilen kanaldan belirtilen mL şurup akıtır.

        CLI karşılığı:
          python dispense_client.py --host IP --motor 1 --ml 5
          python dispense_client.py --host IP --ch 1 --ml 5

        Protokol:
          → CMD:DISP:CH=01:QTY=5:UNIT=ML
          ← RSP:DISP:ACCEPT:CH=01:QTY=5.000:UNIT=ML:DUR_MS=700:DIR=F
          ← EVT:DISP:COMPLETE:CH=01
        """
        if not 1 <= channel <= 8:
            raise ValueError(f"Geçersiz kanal: {channel}. 1–8 arası olmalı.")
        if qty_ml <= 0:
            raise ValueError(f"Geçersiz miktar: {qty_ml}. Pozitif olmalı.")

        t_timeout = timeout or self.timeout
        ch_str    = f"{channel:02d}"
        qty_str   = f"{qty_ml:.3f}" if qty_ml != int(qty_ml) else str(int(qty_ml))
        cmd       = f"CMD:DISP:CH={ch_str}:QTY={qty_str}:UNIT=ML"

        print(f"[SyrupService] DISPENSE → {cmd}")
        t0 = time.monotonic()

        r, w = await self._open()
        try:
            await self._collect_welcome(r, 0.5)
            auth_resp = await self._auth(r, w)
            print(f"[SyrupService] AUTH: {auth_resp}")

            await self._send(w, cmd)

            accept_raw   = None
            complete_raw = None
            duration_ms  = None
            direction    = None
            deadline     = time.monotonic() + t_timeout

            while time.monotonic() < deadline:
                remain = deadline - time.monotonic()
                try:
                    line = await self._readline(r, min(remain, 2.0))
                    print(f"[SyrupService] << {line}")
                    self._check_err(line)

                    if line.startswith("RSP:DISP:ACCEPT"):
                        accept_raw = line
                        for token in line.split(":"):
                            if token.startswith("DUR_MS="):
                                try:    duration_ms = int(token[7:])
                                except: pass
                            elif token.startswith("DIR="):
                                direction = token[4:]

                    elif line.startswith("EVT:DISP:COMPLETE"):
                        # Olayin BU kanala ait oldugunu dogrula.
                        # Coklu surup siparislerinde kanallar arka arkaya
                        # akitiliyor; onceki kanaldan gecikmis bir COMPLETE
                        # satiri bu dozaji "tamamlandi" sanmamiza yol acardi
                        # ve surup eksik kalirdi. Kanal bilgisi yoksa
                        # (eski firmware) eskisi gibi kabul edilir.
                        evt_ch = _event_channel(line)
                        if evt_ch is not None and evt_ch != channel:
                            print(f"[SyrupService] ⚠️  CH{evt_ch} icin COMPLETE geldi, "
                                  f"CH{channel} bekleniyor — yoksayildi.")
                            continue
                        complete_raw = line
                        break

                    elif line.startswith("EVT:DISP:ABORT"):
                        # Dozaj yarıda kesildi — COMPLETE artık GELMEYECEK.
                        # Kılavuz: COMPLETE ve ABORT'un ikisi de
                        # sonlandırıcıdır; yalnızca COMPLETE beklemek
                        # sonsuz bekleme üretir.
                        evt_ch = _event_channel(line)
                        if evt_ch is not None and evt_ch != channel:
                            print(f"[SyrupService] ⚠️  CH{evt_ch} icin ABORT geldi, "
                                  f"CH{channel} bekleniyor — yoksayildi.")
                            continue
                        fields = {}
                        for token in line.split(":"):
                            if "=" in token:
                                k, _, v = token.partition("=")
                                fields[k] = v
                        raise SyrupAbortError(
                            channel      = channel,
                            reason       = fields.get("REASON", "UNKNOWN"),
                            dispensed_ml = _to_float(fields.get("QTY"), 0.0),
                            requested_ml = _to_float(fields.get("REQ"), qty_ml),
                            raw          = line,
                        )

                except asyncio.TimeoutError:
                    continue

            if complete_raw is None:
                elapsed = time.monotonic() - t0
                raise TimeoutError(
                    f"EVT:DISP:COMPLETE sinyali {elapsed:.1f}s içinde gelmedi "
                    f"(accept={accept_raw})"
                )

            elapsed   = time.monotonic() - t0
            completed = complete_raw is not None and complete_raw.startswith("EVT:DISP:COMPLETE")
            accepted  = accept_raw  is not None and accept_raw.startswith("RSP:DISP:ACCEPT")
            print(f"[SyrupService] ✅ CH={ch_str} QTY={qty_ml}mL tamamlandı ({elapsed:.1f}s)")

            return {
                "ok"          : completed,          # EVT:DISP:COMPLETE alındıysa True
                "accepted"    : accepted,            # RSP:DISP:ACCEPT alındıysa True
                "completed"   : completed,           # EVT:DISP:COMPLETE alındıysa True
                "channel"     : channel,
                "qty_ml"      : qty_ml,
                "duration_ms" : duration_ms,
                "direction"   : direction,
                "elapsed_s"   : round(elapsed, 2),
                "accept_raw"  : accept_raw,
                "complete_raw": complete_raw,
            }

        except (SyrupAbortError, SyrupDeviceError):
            raise
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise TimeoutError(str(e))
        except Exception:
            raise
        finally:
            await self._close(w)

    # ─────────────────────────────────────────
    # CMD 4 — WATCH PRESENCE  (--watch-presence)
    # ─────────────────────────────────────────

    async def watch_presence(
        self,
        stop_event: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Kalıcı TCP bağlantısı — EVT:IO:* push olaylarını dinler.
        Her olay dict olarak yield edilir.

        CLI karşılığı: python -u dispense_client.py --host IP --watch-presence

        Protokol:
          ← EVT:IO:PRESENCE:CH01=1,CH02=0,...  (başlangıç + değişimde)
          ← EVT:IO:CH=01:STATE=1               (tek kanal değişimi)

        stop_event set edildiğinde generator durur.
        Bağlantı koparsa otomatik yeniden bağlanır.
        """
        if stop_event is None:
            stop_event = asyncio.Event()

        reconnect_delay = 2.0

        while not stop_event.is_set():
            print(f"[SyrupService] watch_presence → {self.host}:{self.port} bağlanıyor...")
            try:
                r, w = await self._open()
                try:
                    # Welcome + AUTH
                    welcome = await self._collect_welcome(r, 1.5)
                    await self._auth(r, w)

                    # Welcome içindeki PRESENCE'ı yield et
                    for line in welcome:
                        if "EVT:IO:PRESENCE" in line:
                            channels = parse_presence(line)
                            yield {
                                "event"   : "presence",
                                "channels": channels,
                                "motors"  : [
                                    {"motor": int(k), "connected": v}
                                    for k, v in sorted(channels.items(), key=lambda x: int(x[0]))
                                ],
                                "raw"     : line,
                            }

                    # Push akışını dinle
                    print("[SyrupService] watch_presence → dinleniyor...")
                    while not stop_event.is_set():
                        try:
                            line = await asyncio.wait_for(r.readline(), timeout=1.0)
                            text = line.decode("utf-8").strip()
                            if not text:
                                continue
                            print(f"[SyrupService] << {text}")

                            if "EVT:IO:PRESENCE" in text:
                                channels = parse_presence(text)
                                yield {
                                    "event"   : "presence",
                                    "channels": channels,
                                    "motors"  : [
                                        {"motor": int(k), "connected": v}
                                        for k, v in sorted(
                                            channels.items(), key=lambda x: int(x[0])
                                        )
                                    ],
                                    "raw"     : text,
                                }

                            elif "EVT:IO:CH=" in text:
                                state = parse_io_state(text)
                                if state:
                                    yield {
                                        "event"  : "channel_state",
                                        "channel": state["channel"],
                                        "state"  : state["state"],
                                        "raw"    : text,
                                    }

                            elif text.startswith("RSP:ERR"):
                                parsed = parse_err_line(text)
                                yield {
                                    "event"      : "error",
                                    "error_code" : parsed["error_code"],
                                    "description": parsed["description"],
                                    "raw"        : text,
                                }

                        except asyncio.TimeoutError:
                            continue
                finally:
                    await self._close(w)

            except (TimeoutError, ConnectionRefusedError, OSError) as e:
                yield {
                    "event": "connection_error",
                    "error": str(e),
                    "reconnect_in": reconnect_delay,
                }
                if not stop_event.is_set():
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 30.0)
                    continue

            reconnect_delay = 2.0  # başarılı bağlantı sonrası sıfırla

    # ─────────────────────────────────────────
    # CMD 5 — PRIME / RETRACT  (hortum doldur/boşalt)
    # ─────────────────────────────────────────

    async def _run_sys_flow(self, command: str, label: str,
                            overall_timeout: float = 120.0) -> Dict[str, Any]:
        """
        PRIME ve RETRACT ortak akışı (kılavuz 4.2).

        → CMD:SYS:PRIME
        ← RSP:SYS:PRIME:ACCEPT:CH=n:GROUP=g   (n = seçilen kanal sayısı)
        ← EVT:SYS:PRIME:CH=01:DONE            (her kanal bitince)
        ← EVT:SYS:PRIME:COMPLETE              (işlem bitti)

        RETRACT aynı akışı RETRACT adıyla üretir. COMPLETE veya ABORT
        gelene kadar (ya da zaman aşımına dek) olaylar toplanır.
        """
        t0 = time.monotonic()
        r, w = await self._open()
        try:
            await self._collect_welcome(r, 0.5)
            await self._auth(r, w)
            await self._send(w, command)

            accepted = False
            channel_count = None
            done_channels = []
            deadline = time.monotonic() + overall_timeout

            while time.monotonic() < deadline:
                remain = deadline - time.monotonic()
                try:
                    line = await self._readline(r, timeout=min(remain, 10.0))
                except asyncio.TimeoutError:
                    continue
                if not line:
                    continue

                self._check_err(line)   # RSP:ERR → SyrupDeviceError

                if line.startswith(f"RSP:SYS:{label}:ACCEPT"):
                    accepted = True
                    for token in line.split(":"):
                        if token.startswith("CH="):
                            channel_count = _to_float(token[3:], None)
                    print(f"[SyrupService] {label} kabul edildi (kanal sayısı={channel_count})")

                elif line.startswith(f"EVT:SYS:{label}:") and ":DONE" in line:
                    for token in line.split(":"):
                        if token.startswith("CH="):
                            done_channels.append(token[3:])

                elif line.startswith(f"EVT:SYS:{label}:COMPLETE"):
                    return {
                        "ok": True, "operation": label.lower(),
                        "channel_count": channel_count,
                        "done_channels": done_channels,
                        "elapsed_s": round(time.monotonic() - t0, 2),
                    }

                elif line.startswith(f"EVT:SYS:{label}:ABORT"):
                    reason = ""
                    for token in line.split(":"):
                        if token.startswith("REASON="):
                            reason = token[7:]
                    return {
                        "ok": False, "operation": label.lower(), "aborted": True,
                        "reason": reason, "done_channels": done_channels,
                        "elapsed_s": round(time.monotonic() - t0, 2),
                    }

            return {"ok": False, "operation": label.lower(),
                    "error": "timeout", "accepted": accepted,
                    "done_channels": done_channels}
        finally:
            await self._close(w)

    async def prime(self) -> Dict[str, Any]:
        """Vardiya başı — hortum uçlarına şurup getirir (CMD:SYS:PRIME)."""
        return await self._run_sys_flow("CMD:SYS:PRIME", "PRIME")

    async def retract(self) -> Dict[str, Any]:
        """Vardiya sonu — hortumdaki şurubu kaba geri çeker (CMD:SYS:RETRACT)."""
        return await self._run_sys_flow("CMD:SYS:RETRACT", "RETRACT")

    # ─────────────────────────────────────────
    # CMD 6 — CLEAN  (hortum temizliği, çok adımlı)
    # ─────────────────────────────────────────

    async def clean_status(self) -> Dict[str, Any]:
        """
        CMD:SYS:CLEAN:STATUS → mevcut temizlik durumu.
        ← RSP:SYS:CLEAN:STATE=<durum>:REMAIN=<sn>
        """
        r, w = await self._open()
        try:
            await self._collect_welcome(r, 0.5)
            await self._auth(r, w)
            await self._send(w, "CMD:SYS:CLEAN:STATUS")
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                try:
                    line = await self._readline(r, timeout=self.timeout)
                except asyncio.TimeoutError:
                    break
                if not line:
                    continue
                self._check_err(line)
                if line.startswith("RSP:SYS:CLEAN:STATE") or "CLEAN:STATE" in line:
                    fields = {}
                    for token in line.split(":"):
                        if "=" in token:
                            k, _, v = token.partition("=")
                            fields[k] = v
                    return {"ok": True, "state": fields.get("STATE"),
                            "remain_s": _to_float(fields.get("REMAIN"), None), "raw": line}
            return {"ok": False, "error": "no_status_response"}
        finally:
            await self._close(w)

    async def clean_lastresult(self) -> Dict[str, Any]:
        """
        CMD:SYS:CLEAN:LASTRESULT → son temizlik sonucu (dozaj kilidi kontrolü).
        ← RSP:SYS:CLEAN:LASTRESULT:STATE=OK
        ← RSP:SYS:CLEAN:LASTRESULT:STATE=INCOMPLETE:PHASE=WASH:BLOCKED=1
        """
        r, w = await self._open()
        try:
            await self._collect_welcome(r, 0.5)
            await self._auth(r, w)
            await self._send(w, "CMD:SYS:CLEAN:LASTRESULT")
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                try:
                    line = await self._readline(r, timeout=self.timeout)
                except asyncio.TimeoutError:
                    break
                if not line:
                    continue
                self._check_err(line)
                if "CLEAN:LASTRESULT" in line:
                    fields = {}
                    for token in line.split(":"):
                        if "=" in token:
                            k, _, v = token.partition("=")
                            fields[k] = v
                    blocked = fields.get("BLOCKED") == "1"
                    return {"ok": True, "state": fields.get("STATE"),
                            "phase": fields.get("PHASE"), "blocked": blocked, "raw": line}
            return {"ok": False, "error": "no_response"}
        finally:
            await self._close(w)

    async def clean_start(self) -> Dict[str, Any]:
        """
        Temizliği başlatır (CMD:SYS:CLEAN:START) ve ilk bekleme aşamasına
        (WAIT_SOAP) kadar ilerler.

        Temizlik operatör müdahalesi gerektirir (kılavuz 4.3): deterjanlı
        suya daldırma → ACK_SOAP → yıkama → temiz suya daldırma →
        ACK_WATER → durulama. Bu uç yalnızca START gönderip WAIT_SOAP'a
        kadar olan durumu döndürür; sonraki adımlar ack_soap / ack_water
        ile ayrı çağrılır.
        """
        return await self._clean_command("CMD:SYS:CLEAN:START",
                                          wait_for=("WAIT_SOAP", "WAIT_WATER", "COMPLETE"))

    async def clean_ack_soap(self) -> Dict[str, Any]:
        """Deterjanlı su hazır onayı (CMD:SYS:CLEAN:ACK_SOAP)."""
        return await self._clean_command("CMD:SYS:CLEAN:ACK_SOAP",
                                          wait_for=("WAIT_WATER", "COMPLETE", "PHASE=WASH"))

    async def clean_ack_water(self) -> Dict[str, Any]:
        """Temiz su hazır onayı (CMD:SYS:CLEAN:ACK_WATER)."""
        return await self._clean_command("CMD:SYS:CLEAN:ACK_WATER",
                                          wait_for=("COMPLETE", "PHASE=RINSE"))

    async def clean_abort(self) -> Dict[str, Any]:
        """Temizliği iptal eder, motorları durdurur (CMD:SYS:CLEAN:ABORT)."""
        return await self._clean_command("CMD:SYS:CLEAN:ABORT",
                                          wait_for=("ABORT", "COMPLETE"))

    async def _clean_command(self, command: str, wait_for: tuple,
                             timeout: float = 60.0) -> Dict[str, Any]:
        """
        Bir CLEAN komutu gönderir ve wait_for içindeki işaretlerden biri
        gelene kadar olayları toplar. Temizlik adımları arasında cihaz
        operatör müdahalesi beklediği için her adım ayrı istek olarak
        çağrılır (uzun süreli tek bağlantı yerine).
        """
        t0 = time.monotonic()
        r, w = await self._open()
        try:
            await self._collect_welcome(r, 0.5)
            await self._auth(r, w)
            await self._send(w, command)

            events = []
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                remain = deadline - time.monotonic()
                try:
                    line = await self._readline(r, timeout=min(remain, 10.0))
                except asyncio.TimeoutError:
                    continue
                if not line:
                    continue
                self._check_err(line)
                events.append(line)

                # PHASE / WAIT / COMPLETE / ABORT işaretlerini kontrol et
                if any(marker in line for marker in wait_for):
                    phase = None
                    for token in line.split(":"):
                        if token.startswith("PHASE="):
                            phase = token[6:]
                        elif token.startswith("WAIT_"):
                            phase = token
                    complete = "COMPLETE" in line
                    aborted = "ABORT" in line
                    return {
                        "ok": not aborted,
                        "command": command.split(":")[-1],
                        "phase": phase,
                        "complete": complete,
                        "aborted": aborted,
                        "events": events,
                        "elapsed_s": round(time.monotonic() - t0, 2),
                    }

            return {"ok": False, "command": command.split(":")[-1],
                    "error": "timeout", "events": events}
        finally:
            await self._close(w)
