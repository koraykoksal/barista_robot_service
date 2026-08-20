"""
core/machine_errors.py

Kahve makinesi hata kodlarını ve durum sözlüğünü yorumlar.

order_utils.py'den ayrıldı. Buradaki fonksiyonlar saf — hiçbir servise,
bağlantıya veya global duruma dokunmaz; yalnızca verilen veriyi yorumlar.
Bu sayede test edilebilir ve core katmanında kalabilir.
"""

from typing import Any, Dict, List, Optional

from core.config import MACHINE_ERROR_MESSAGES


class MachineNotReady(Exception):
    """
    Makine sipariş almaya uygun değil.

    Önceden düz Exception fırlatılıyordu; çağıran taraf gerçek bir
    hata mı yoksa "makine meşgul" mü olduğunu ayırt edemiyordu.
    """


# ─────────────────────────────────────────────
# HATA KODU → METİN
# ─────────────────────────────────────────────

def describe_machine_errors(error_codes: List[Any]) -> str:
    """
    Hata kodu listesini okunabilir Türkçe metne çevirir.

    Bilinmeyen kod gelirse kodu metne gömer — böylece sahada
    yeni bir hata koduyla karşılaşıldığında en azından numarası görünür.
    """
    if not error_codes:
        return "Bilinmeyen makine hatası"

    parts = []
    for code in error_codes:
        try:
            parts.append(MACHINE_ERROR_MESSAGES.get(int(code), f"Makine hatası (kod: {code})"))
        except (TypeError, ValueError):
            parts.append(f"Makine hatası (kod: {code})")

    # Aynı mesaj birden fazla koddan gelebiliyor (ör. 75 ve 76 posa çekmecesi)
    unique = list(dict.fromkeys(parts))
    return " | ".join(unique)


def describe_with_texts(error_codes: List[Any],
                       error_texts: Optional[Dict[Any, str]] = None) -> str:
    """
    Hata kodlarını açıklamaya çevirir; makinenin KENDİ metnini önceler.

    MACHINE_ERROR_MESSAGES elle tutulan bir tablodur ve sahada
    karşılaşılan her kodu içermez (ör. 672, 687, 747). Makine bu kodlarla
    birlikte "Error Text" alanında kendi açıklamasını da gönderiyor;
    varsa onu kullanmak "Makine hatası (kod: 747)" demekten iyidir.

    Sıralama: makine metni → yerel tablo → "kod: N".
    """
    if not error_codes:
        return "Bilinmeyen makine hatası"

    texts = error_texts or {}
    parts = []
    for code in error_codes:
        try:
            key = int(code)
        except (TypeError, ValueError):
            key = code

        machine_text = str(texts.get(key) or texts.get(str(key)) or "").strip()
        if machine_text:
            # Makine bazen metnin başına kod numarası ve satır sonu
            # koyuyor; ekranda tek satır dursun diye boşluklar sadeleştirilir.
            parts.append(" ".join(machine_text.split()))
        else:
            parts.append(MACHINE_ERROR_MESSAGES.get(key, f"Makine hatası (kod: {code})"))

    return " | ".join(dict.fromkeys(parts))


# ─────────────────────────────────────────────
# DURUM KONTROLÜ
# ─────────────────────────────────────────────

def check_monitor_state(state: Dict[str, Any], context: str = "") -> None:
    """
    MachineMonitor'ın tuttuğu anlık durumu kontrol eder.
    Sipariş akışı BAŞLAMADAN önce çağrılır.

    Makine uygun değilse MachineNotReady fırlatır.

    Engelleyici olmayan hatalar (NON_BLOCKING_ERROR_CODES) yalnızca
    loglanır — bunlar için siparişi reddetmek gereksiz.
    """
    prefix = f"[{context}] " if context else ""

    if not state.get("online", False):
        raise MachineNotReady(f"{prefix}Kahve makinesi çevrimdışı.")

    if state.get("has_blocking_error") and state.get("blocking_errors"):
        detail = describe_machine_errors(state["blocking_errors"])
        raise MachineNotReady(f"{prefix}Makine hazır değil: {detail}")

    if state.get("has_error") and state.get("errors"):
        blocking = set(state.get("blocking_errors", []))
        non_blocking = [e for e in state.get("errors", []) if e not in blocking]
        if non_blocking:
            print(f"[check_monitor_state] ℹ️  Engelleyici olmayan hatalar (yoksayıldı): {non_blocking}")

    if state.get("cleaning"):
        notif = state["cleaning"]
        kind = notif.get("type", "sistem temizliği") if isinstance(notif, dict) else "sistem temizliği"
        raise MachineNotReady(f"{prefix}Makine temizlik modunda: {kind}")

    if state.get("rinsing"):
        notif = state["rinsing"]
        kind = notif.get("type", "durulama") if isinstance(notif, dict) else "durulama"
        raise MachineNotReady(f"{prefix}Makine durulama modunda: {kind}")
