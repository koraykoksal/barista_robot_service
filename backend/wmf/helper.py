import asyncio
import json
from typing import Any, Dict, Optional

import websockets


# ──────────────────────────────────────────────
# returnvalue çıkarıcı
# ──────────────────────────────────────────────

def extract_returnvalue(payload: Any) -> Optional[int]:
    """
    Kahve makinesi yanıtından 'returnvalue' değerini çıkarır.

    Beklenen format örneği:
        [ {"function": "checkBeverage"}, {"returnvalue": 0} ]
    """
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and "returnvalue" in item:
                try:
                    return int(item["returnvalue"])
                except (ValueError, TypeError):
                    return None
    elif isinstance(payload, dict):
        if "returnvalue" in payload:
            try:
                return int(payload["returnvalue"])
            except (ValueError, TypeError):
                return None
    return None


# ──────────────────────────────────────────────
# Rcp State çıkarıcı
# ──────────────────────────────────────────────

# Kabul edilen key varyantları (hepsi küçük harfe normalize edilerek karşılaştırılır)
_RCP_STATE_KEYS = {"rcp state", "rcp_state", "rcpstate"}


def extract_rcp_state(payload: Any) -> Optional[int]:
    """
    Payload içinde Rcp State değerini bulur.

    • list / dict / iç içe yapılarda çalışır.
    • Key karşılaştırması büyük/küçük harf ve boşluk duyarsızdır.
    • int veya string gelse de normalize eder.

    Beklenen format örnekleri:
        [ {"function": "startBeverage"}, {"Rcp State": 99} ]
        {"Rcp State": 9}
        {"data": [{"Rcp_State": -9}]}
    """

    def _normalize_key(k: Any) -> str:
        return str(k).strip().lower().replace("-", " ").replace("_", " ")

    def _to_int(v: Any) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    if isinstance(payload, dict):
        for k, v in payload.items():
            if _normalize_key(k) in _RCP_STATE_KEYS:
                result = _to_int(v)
                if result is not None:
                    return result

        # İç içe dict/list varsa tara
        for v in payload.values():
            result = extract_rcp_state(v)
            if result is not None:
                return result

    elif isinstance(payload, list):
        for item in payload:
            result = extract_rcp_state(item)
            if result is not None:
                return result

    return None


# ──────────────────────────────────────────────
# Tek mesaj gönder / tek cevap al
# ──────────────────────────────────────────────

async def ws_send_once(
    ws_uri  : str,
    message : Dict[str, Any],
    token   : Optional[str] = None,
    timeout : float = 10.0,
) -> Any:
    """
    WebSocket'e tek bir mesaj gönderir, tek bir yanıt alır ve döner.

    Dönen değer: JSON parse edilmiş nesne ya da {"raw": <ham string>}.
    """
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(
        ws_uri,
        additional_headers=headers if headers else None,
        ping_interval=30,
        ping_timeout=10,
        close_timeout=5,
    ) as ws:
        await ws.send(json.dumps(message))
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}


# ──────────────────────────────────────────────
# startBeverage mesajı oluşturucu
# ──────────────────────────────────────────────

def build_start_message(btn_nbr: str) -> Dict[str, Any]:
    """
    Standart bir startBeverage mesajı döner.
    `btn_nbr`: kahve makinesindeki buton numarası (string veya int kabul).
    """
    return {
        "function"       : "startBeverage",
        "a_iBtnNbr"      : str(btn_nbr),
        "a_iBarista"     : "1",
        "a_iDecaf"       : "0",
        "a_iSML"         : "1",
        "a_iMilktype"    : "-1",
        "a_iSirupType"   : "0",
        "a_iSirupSML"    : "1",
        "a_iBeanPortioner": "0",
        "a_iCupSizeAdj"  : "100",
    }


# ──────────────────────────────────────────────
# Rcp State bitiş kontrolü
# ──────────────────────────────────────────────

def has_rcp_finished(results: Any) -> bool:
    """
    send_and_wait_rcp_finished çıktısında akışın tamamlandığını kontrol eder.

    Tamamlanma durumları (API dok. sayfa 11):
      9   → İçecek bitti, makine hazır
     -9   → İçecek bitti, makine henüz hazır değil
     22   → Onay bekleniyor (Beverage confirmation) — akış durdu

    `results`: CoffeeService.send_and_wait_rcp_finished'den dönen liste.
    """
    for payload in results or []:
        # Normal bitiş: Rcp State 9 / -9
        rcp_state = extract_rcp_state(payload)
        if rcp_state in (9, -9):
            return True

        # Onay bekleme durumu: {"rcp_state": 22, "error": "confirmation_required"}
        if isinstance(payload, dict) and payload.get("error") == "confirmation_required":
            return True

    return False


def is_rcp_confirmation_required(results: Any) -> bool:
    """
    Makine 'Beverage confirmation' bekliyorsa True döner.
    (Rcp State 22 — API dok. sayfa 11)
    """
    for payload in results or []:
        if isinstance(payload, dict) and payload.get("error") == "confirmation_required":
            return True
    return False
