"""
machine_info_service.py

WMF CMRemote4.x API — Makine bilgi sorgulama servisi.

Sorgulanan fonksiyonlar:
  getDiagnosticData                → Sıcaklık, basınç, RAM, Flash
  getServiceStatistics             → Bakım sayaçları, öğütücü, temizlik, kireç
  getPortionerInfo                 → Öğütücü tipleri
  getSystemCleaningState           → Sistem temizliği zamanlaması
  getMilkCleaningState             → Süt temizliği zamanlaması
  getFoamerRinsingState            → Köpürtücü durulama zamanlaması
  getMixerRinsingState             → Mikser durulama zamanlaması
  getMilkReplacementState          → Süt değişimi zamanlaması
  getMilkMixerWarmRinsingState     → Süt mikseri ılık durulama zamanlaması
  getFfcFilterReplacementState     → FFC filtre değişimi zamanlaması
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import websockets


# ─────────────────────────────────────────────────────────────
# YARDIMCI — tek mesaj gönder / yanıt al
# ─────────────────────────────────────────────────────────────

async def _ws_query(
    ws_uri  : str,
    token   : Optional[str],
    function: str,
    timeout : float = 8.0,
) -> Optional[List[Any]]:
    """
    Makineye tek bir sorgu gönderir, yanıt listesini döner.
    Hata durumunda None döner (exception fırlatmaz).
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    msg     = json.dumps({"function": function})

    try:
        async with websockets.connect(
            ws_uri,
            additional_headers=headers,
            ping_interval=10,
            ping_timeout=5,
            open_timeout=5,
            close_timeout=3,
        ) as ws:
            await ws.send(msg)
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            payload = json.loads(raw)
            return payload if isinstance(payload, list) else [payload]
    except Exception as e:
        print(f"[MachineInfo] ⚠️  {function} sorgusu başarısız: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# YARDIMCI — payload'dan değer çıkar
# ─────────────────────────────────────────────────────────────

def _get(payload: Optional[List[Any]], key: str, default: Any = None) -> Any:
    """Payload listesi içinde belirli bir key'i arar."""
    if not payload:
        return default
    for item in payload:
        if isinstance(item, dict) and key in item:
            return item[key]
    return default


def _returnvalue(payload: Optional[List[Any]]) -> Optional[int]:
    v = _get(payload, "returnvalue")
    return int(v) if v is not None else None


# ─────────────────────────────────────────────────────────────
# YARDIMCI — süre formatla
# ─────────────────────────────────────────────────────────────

def _format_due(seconds: Any) -> str:
    """
    dueInSeconds → okunabilir metin.
    -1 → zamanlanmamış
     0 → şimdi yapılmalı (gecikmiş)
    >0 → X saat Y dakika sonra
    """
    if seconds is None:
        return "Bilinmiyor"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return str(seconds)

    if s == -1:
        return "Zamanlanmamış"
    if s <= 0:
        return "⚠️ Şimdi yapılmalı (gecikmiş)"
    if s < 60:
        return f"{s} saniye sonra"
    if s < 3600:
        return f"{s // 60} dakika sonra"
    h = s // 3600
    m = (s % 3600) // 60
    if m == 0:
        return f"{h} saat sonra"
    return f"{h} saat {m} dakika sonra"


def _format_duration(seconds: Any) -> str:
    """durationInSeconds → okunabilir metin."""
    if seconds is None:
        return "Bilinmiyor"
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)

    if s < 0:
        return "Bilinmiyor"
    if s < 60:
        return f"{s:.0f} saniye"
    m = s / 60
    return f"{m:.1f} dakika"


def _urgency(seconds: Any) -> str:
    """dueInSeconds → aciliyet seviyesi."""
    if seconds is None:
        return "unknown"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "unknown"

    if s == -1:
        return "ok"          # zamanlanmamış — sorun yok
    if s <= 0:
        return "critical"    # gecikmiş
    if s <= 300:             # 5 dakika
        return "warning"
    if s <= 3600:            # 1 saat
        return "attention"
    return "ok"


# ─────────────────────────────────────────────────────────────
# ANA SERVİS
# ─────────────────────────────────────────────────────────────

class MachineInfoService:

    def __init__(self, ws_uri: str, token: Optional[str] = None):
        self.ws_uri = ws_uri
        self.token  = token

    async def _q(self, function: str, timeout: float = 8.0) -> Optional[List[Any]]:
        return await _ws_query(self.ws_uri, self.token, function, timeout)

    # ── getDiagnosticData ─────────────────────────────────────

    async def get_diagnostic(self) -> Dict[str, Any]:
        """
        Makine tanısal verileri: sıcaklık, basınç, RAM, Flash.
        API dok. 4.19
        """
        payload = await self._q("getDiagnosticData")
        rv      = _returnvalue(payload)

        if rv != 0 or payload is None:
            return {"ok": False, "error": f"returnvalue={rv}"}

        temp_water  = _get(payload, "iTempWaterBoiler")
        temp_steam  = _get(payload, "iTempSteamBoiler")
        pressure    = _get(payload, "iPressureSteamBoiler")
        ram         = _get(payload, "iRam")
        flash       = _get(payload, "iFlash")

        result: Dict[str, Any] = {"ok": True, "items": []}

        if temp_water is not None:
            result["items"].append({
                "key"     : "su_kazani_sicakligi",
                "label"   : "Su Kazanı Sıcaklığı",
                "value"   : temp_water,
                "unit"    : "°C",
                "display" : f"{temp_water} °C",
                "status"  : "ok",
            })
        if temp_steam is not None:
            result["items"].append({
                "key"     : "buhar_kazani_sicakligi",
                "label"   : "Buhar Kazanı Sıcaklığı",
                "value"   : temp_steam,
                "unit"    : "°C",
                "display" : f"{temp_steam} °C",
                "status"  : "ok",
            })
        if pressure is not None:
            result["items"].append({
                "key"     : "buhar_kazani_basinci",
                "label"   : "Buhar Kazanı Basıncı",
                "value"   : pressure,
                "unit"    : "mbar",
                "display" : f"{pressure} mbar",
                "status"  : "ok",
            })
        if ram is not None:
            status = "warning" if int(ram) > 80 else "ok"
            result["items"].append({
                "key"     : "ram_kullanimi",
                "label"   : "RAM Kullanımı",
                "value"   : ram,
                "unit"    : "%",
                "display" : f"%{ram}",
                "status"  : status,
            })
        if flash is not None:
            status = "warning" if int(flash) > 85 else "ok"
            result["items"].append({
                "key"     : "flash_kullanimi",
                "label"   : "Flash Kullanımı",
                "value"   : flash,
                "unit"    : "%",
                "display" : f"%{flash}",
                "status"  : status,
            })

        result["raw"] = payload
        print(f"[MachineInfo] getDiagnosticData → {len(result['items'])} alan")
        return result

    # ── getServiceStatistics ──────────────────────────────────

    async def get_service_stats(self) -> Dict[str, Any]:
        """
        Bakım sayaçları: öğütücü, demleme, temizlik, kireç, su.
        API dok. 4.47
        """
        payload = await self._q("getServiceStatistics")
        rv      = _returnvalue(payload)

        if rv != 0 or payload is None:
            return {"ok": False, "error": f"returnvalue={rv}"}

        g = lambda k: _get(payload, k)

        # Öğütücü sayaçları (ScoopGrinder = öğütme sayısı)
        grinders = []
        for i in range(1, 5):
            val = g(f"ScoopGrinder{i}")
            if val is not None and int(val) >= 0:
                grinders.append({
                    "portioner": i,
                    "label"    : f"Öğütücü {i} toplam öğütme",
                    "value"    : int(val),
                    "display"  : f"{int(val):,} öğütme",
                    "status"   : "ok",
                })

        # Demleme sayaçları
        since_maint = g("BrewingsSinceMaintainance1")
        since_drive = g("BrewingsSinceDriveExchange")

        maintenance_items = []
        if since_maint is not None and int(since_maint) >= 0:
            # Eşik: 3000 demleme → uyarı (makineye göre değişir)
            status = "warning" if int(since_maint) > 3000 else "ok"
            maintenance_items.append({
                "key"    : "son_bakimdan_demleme",
                "label"  : "Son Bakımdan Sonra Demleme",
                "value"  : int(since_maint),
                "display": f"{int(since_maint):,} demleme",
                "status" : status,
                "note"   : "3.000 üzerinde bakım önerilir" if status == "warning" else "",
            })
        if since_drive is not None and int(since_drive) >= 0:
            status = "warning" if int(since_drive) > 5000 else "ok"
            maintenance_items.append({
                "key"    : "son_motor_degisiminden_demleme",
                "label"  : "Son Motor Değişiminden Demleme",
                "value"  : int(since_drive),
                "display": f"{int(since_drive):,} demleme",
                "status" : status,
            })

        # Temizlik sayaçları
        n_clean    = g("NumberOfCleanings")
        n_clean_do = g("NumberOfCleaningsToDo")
        n_desc     = g("NumberOfDescalings")

        cleaning_items = []
        if n_clean is not None:
            cleaning_items.append({
                "key"    : "toplam_temizlik",
                "label"  : "Toplam Sistem Temizliği",
                "value"  : int(n_clean),
                "display": f"{int(n_clean)} kez",
                "status" : "ok",
            })
        if n_clean_do is not None:
            status = "warning" if int(n_clean_do) > 0 else "ok"
            cleaning_items.append({
                "key"    : "bekleyen_temizlik",
                "label"  : "Bekleyen Temizlik",
                "value"  : int(n_clean_do),
                "display": f"{int(n_clean_do)} temizlik bekleniyor" if int(n_clean_do) > 0 else "Temizlik beklemiyor",
                "status" : status,
            })
        if n_desc is not None:
            cleaning_items.append({
                "key"    : "kires_giderme",
                "label"  : "Toplam Kireç Giderme",
                "value"  : int(n_desc),
                "display": f"{int(n_desc)} kez",
                "status" : "ok",
            })

        # Su tüketimi
        water_total = g("TotalWaterBoilerSupply")
        water_desc  = g("TotalWaterBoilerSupplySinceDescaling")

        water_items = []
        if water_total is not None:
            water_items.append({
                "key"    : "toplam_su",
                "label"  : "Toplam Su Tüketimi",
                "value"  : water_total,
                "display": f"{water_total} litre",
                "status" : "ok",
            })
        if water_desc is not None:
            # Eşik: son kireç gidermeden 100 litre üzeri → uyarı
            status = "warning" if float(water_desc) > 100 else "ok"
            water_items.append({
                "key"    : "son_kirec_gidermeden_su",
                "label"  : "Son Kireç Gidermeden Sonra Su",
                "value"  : water_desc,
                "display": f"{water_desc} litre",
                "status" : status,
                "note"   : "100 litre üzerinde kireç giderme önerilir" if status == "warning" else "",
            })

        result = {
            "ok"              : True,
            "grinders"        : grinders,
            "maintenance"     : maintenance_items,
            "cleaning"        : cleaning_items,
            "water"           : water_items,
            "raw"             : payload,
        }

        print(f"[MachineInfo] getServiceStatistics → "
              f"{len(grinders)} öğütücü, "
              f"{len(maintenance_items)} bakım, "
              f"{len(cleaning_items)} temizlik, "
              f"{len(water_items)} su kalemi")
        return result

    # ── getPortionerInfo ──────────────────────────────────────

    async def get_portioner_info(self) -> Dict[str, Any]:
        """
        Öğütücü tip ve konum bilgileri.
        API dok. 4.38
        """
        payload = await self._q("getPortionerInfo")
        rv      = _returnvalue(payload)

        if rv != 0 or payload is None:
            return {"ok": False, "error": f"returnvalue={rv}"}

        portioners = []
        for i in range(1, 5):
            name = _get(payload, f"portioner{i}")
            if name:
                portioners.append({
                    "number" : i,
                    "label"  : f"Öğütücü {i}",
                    "name"   : name,
                    "display": f"Öğütücü {i}: {name}",
                })

        print(f"[MachineInfo] getPortionerInfo → {len(portioners)} öğütücü")
        return {"ok": True, "portioners": portioners, "raw": payload}

    # ── Temizlik/Durulama Zamanlamaları ───────────────────────

    async def _get_cleaning_state(
        self,
        function: str,
        label   : str,
        key     : str,
    ) -> Dict[str, Any]:
        """Tek bir cleaning/rinsing state sorgusunu çalıştırır ve formatlar."""
        payload = await self._q(function)
        rv      = _returnvalue(payload)

        if payload is None:
            return {
                "key"     : key,
                "label"   : label,
                "ok"      : False,
                "error"   : "Bağlantı hatası",
                "urgency" : "unknown",
            }

        if rv == 11:  # FunctionNotAvailable — bu makine tipi için geçerli değil
            return {
                "key"       : key,
                "label"     : label,
                "ok"        : True,
                "available" : False,
                "display"   : "Bu makine için geçerli değil",
                "urgency"   : "ok",
            }

        due      = _get(payload, "dueInSeconds")
        duration = _get(payload, "durationInSeconds")
        due_disp = _get(payload, "dueInDispensings")  # getFfcFilterReplacementState

        item = {
            "key"          : key,
            "label"        : label,
            "ok"           : True,
            "available"    : True,
            "due_seconds"  : due,
            "due_display"  : _format_due(due),
            "duration_secs": duration,
            "duration_disp": _format_duration(duration),
            "urgency"      : _urgency(due),
        }

        if due_disp is not None:
            item["due_dispensings"] = due_disp
            item["due_disp_display"] = f"{due_disp} içecek sonra"

        return item

    async def get_all_cleaning_states(self) -> Dict[str, Any]:
        """
        Tüm temizlik/durulama/filtre zamanlamalarını tek seferde sorgular.
        API dok. 4.30 – 4.37
        """
        tasks = [
            self._get_cleaning_state("getSystemCleaningState",       "Sistem Temizliği",              "system_cleaning"),
            self._get_cleaning_state("getMilkCleaningState",          "Süt Temizliği",                 "milk_cleaning"),
            self._get_cleaning_state("getFoamerRinsingState",         "Köpürtücü Durulama",            "foamer_rinsing"),
            self._get_cleaning_state("getMixerRinsingState",          "Mikser Durulama",               "mixer_rinsing"),
            self._get_cleaning_state("getMilkReplacementState",       "Süt Değişimi Durulama",         "milk_replacement"),
            self._get_cleaning_state("getMilkMixerWarmRinsingState",  "Süt Mikseri Ilık Durulama",     "milk_mixer_warm"),
            self._get_cleaning_state("getFfcFilterReplacementState",  "FFC Filtre Değişimi",           "ffc_filter"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Genel aciliyet değerlendirmesi
        urgencies = [r.get("urgency", "ok") for r in results]
        if "critical" in urgencies:
            overall = "critical"
        elif "warning" in urgencies:
            overall = "warning"
        elif "attention" in urgencies:
            overall = "attention"
        else:
            overall = "ok"

        critical_items  = [r["label"] for r in results if r.get("urgency") == "critical"]
        warning_items   = [r["label"] for r in results if r.get("urgency") == "warning"]
        attention_items = [r["label"] for r in results if r.get("urgency") == "attention"]

        summary_parts = []
        if critical_items:
            summary_parts.append(f"⛔ Gecikmiş: {', '.join(critical_items)}")
        if warning_items:
            summary_parts.append(f"⚠️ Yakında gerekli: {', '.join(warning_items)}")
        if attention_items:
            summary_parts.append(f"🔔 Dikkat: {', '.join(attention_items)}")
        if not summary_parts:
            summary_parts.append("✅ Tüm temizlik ve durulama programları zamanında")

        print(f"[MachineInfo] get_all_cleaning_states → overall={overall}")
        return {
            "ok"        : True,
            "overall"   : overall,
            "summary"   : " | ".join(summary_parts),
            "items"     : list(results),
        }

    # ── Hepsini Birden ────────────────────────────────────────

    async def get_full_machine_info(self) -> Dict[str, Any]:
        """
        getDiagnosticData + getServiceStatistics + getPortionerInfo +
        tüm cleaning state'leri paralel sorgular ve birleştirir.
        """
        print("[MachineInfo] Tam makine bilgisi sorgulanıyor...")
        t_start = time.monotonic()

        diag, stats, portioners, cleaning = await asyncio.gather(
            self.get_diagnostic(),
            self.get_service_stats(),
            self.get_portioner_info(),
            self.get_all_cleaning_states(),
            return_exceptions=False,
        )

        elapsed = time.monotonic() - t_start
        print(f"[MachineInfo] Tüm sorgular tamamlandı ({elapsed:.2f}s)")

        return {
            "ok"         : True,
            "queried_at" : time.time(),
            "elapsed_s"  : round(elapsed, 2),
            "diagnostic" : diag,
            "service"    : stats,
            "portioners" : portioners,
            "cleaning"   : cleaning,
        }
