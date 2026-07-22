"""
security.py

Yönetici uçlarını koruyan basit token doğrulaması.

NEDEN GEREKLİ:
  Önceki sürümde /stock/refill, /robot/do/{id}, /robot/program/stop,
  /robot/set_manual gibi uçlar tamamen korumasızdı. Aynı ağdaki
  herhangi bir cihaz robotu durdurabiliyor veya stok kayıtlarını
  sıfırlayabiliyordu.

NASIL KULLANILIR:
  from core.security import require_admin

  @router.put("/stock/refill", dependencies=[Depends(require_admin)])
  async def stock_refill(...):
      ...

İSTEMCİ TARAFI:
  Header:  X-Admin-Token: <.env içindeki ADMIN_TOKEN>

KAPSAM:
  Bu kapalı bir kiosk ağı için tasarlanmış hafif bir korumadır; tam bir
  kimlik doğrulama sistemi değildir. Servis internete açılacaksa
  HTTPS + kullanıcı bazlı oturum yönetimi gerekir.
"""

import secrets

from fastapi import Header, HTTPException, status

from core.config import ADMIN_TOKEN


async def require_admin(x_admin_token: str = Header(default="")) -> None:
    """
    FastAPI bağımlılığı. Token eşleşmezse 401 döner.

    ADMIN_TOKEN boşsa koruma devre dışıdır (geliştirme kolaylığı için).
    Bu durumda config.validate() başlangıçta uyarı basar.
    """
    if not ADMIN_TOKEN:
        return   # koruma kapalı — config.validate() zaten uyardı

    # secrets.compare_digest: zamanlama saldırısına karşı sabit süreli
    # karşılaştırma. Normal == operatörü ilk farklı karakterde döner ve
    # yanıt süresinden token tahmin edilebilir hale gelir.
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya eksik yönetici token'ı (X-Admin-Token başlığı).",
        )


def admin_protection_enabled() -> bool:
    """Durum uçlarında koruma açık mı bilgisini göstermek için."""
    return bool(ADMIN_TOKEN)
