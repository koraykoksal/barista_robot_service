"""
service/sync_service.py

SQLite → MongoDB aktarımı.

ÇALIŞMA BİÇİMİ:
  Arka planda bir görev belirli aralıklarla (SYNC_INTERVAL) kuyruğu
  yoklar. MongoDB'ye ulaşılabiliyorsa bekleyen işlemler sırayla
  aktarılır ve kuyruktan silinir. Ulaşılamıyorsa kuyruk bekler —
  hiçbir kayıt kaybolmaz, kiosk çalışmaya devam eder.

TEKRAR GÜVENLİĞİ:
  Kuyruk kayıtları fark değil, işlem sonrası MUTLAK stok durumunu
  taşır. Aynı kayıt iki kez aktarılsa bile sonuç değişmez. Log
  kayıtları da op_id'leri _id olarak kullanır; upsert ile mükerrer
  satır oluşmaz.

  Bu tasarımın sonucu: aktarım yarıda kalıp yeniden denendiğinde stok
  bozulmaz. Fark tabanlı ($inc) bir kuyrukta aynı kaydın iki kez
  uygulanması stoğu kalıcı olarak yanlışlar.

YÖN:
  Aktarım tek yönlüdür — SQLite'tan MongoDB'ye. Kiosk kendi stoğunun
  tek yazarıdır; ters yönde yazma olsaydı çakışma çözümü gerekirdi.
  MongoDB yalnızca AÇILIŞTA ve yerel kayıt hiç yokken okunur
  (bkz. bootstrap).
"""

import asyncio
from typing import Any, Dict, Optional

from core import sqlite_store
from core.applog import get_logger
from core.config import MONGO_ENABLED, SYNC_BATCH, SYNC_INTERVAL
from core.database import (
    col_order_logs,
    col_refill_logs,
    col_stock,
    col_syrup_stock,
    col_thresholds,
    ping as mongo_ping,
)

log = get_logger(__name__)


class SyncService:
    """Kuyruğu MongoDB'ye boşaltan arka plan görevi."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._online: bool = False
        self._last_ok: Optional[str] = None
        self._last_error: Optional[str] = None
        self._synced_total: int = 0

    # ── Yaşam döngüsü ─────────────────────────

    async def start(self) -> None:
        if not MONGO_ENABLED:
            log.warning("MONGO_ENABLED=false — senkronizasyon başlatılmadı, "
                        "kayıtlar yalnızca SQLite'ta tutulacak.")
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="mongo-sync")
        log.info("Senkronizasyon görevi başlatıldı (her %.0f sn, tur başına en çok %d kayıt).",
                 SYNC_INTERVAL, SYNC_BATCH)

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            # Kapanmadan önce son bir tur dene — kuyrukta bekleyen varsa
            # servis kapanırken aktarılsın.
            try:
                await asyncio.wait_for(self.drain_once(), timeout=8.0)
            except Exception as e:
                log.warning("Kapanış senkronizasyonu tamamlanamadı: %s", e)
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Senkronizasyon görevi durduruldu.")

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.drain_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Senkronizasyon turunda beklenmeyen hata: %s", e, exc_info=True)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=SYNC_INTERVAL)
            except asyncio.TimeoutError:
                pass

    # ── Aktarım ───────────────────────────────

    async def drain_once(self) -> Dict[str, Any]:
        """
        Kuyrukta bekleyenleri MongoDB'ye aktarır.
        Bağlantı yoksa sessizce çıkar; kuyruk bekler.
        """
        pending = await asyncio.to_thread(sqlite_store.outbox_pending, SYNC_BATCH)
        if not pending:
            # Kuyruk boşken de bağlantı durumunu tazele — arayüz
            # "bulut erişilebilir mi" bilgisini gösterebilsin.
            await self._refresh_online()
            return {"synced": 0, "pending": 0, "online": self._online}

        if not await self._refresh_online():
            log.debug("MongoDB erişilemiyor — %d kayıt kuyrukta bekliyor.", len(pending))
            return {"synced": 0, "pending": len(pending), "online": False}

        done: list = []
        for item in pending:
            try:
                await self._apply(item["kind"], item["payload"])
                done.append(item["op_id"])
            except Exception as e:
                # Sıra önemli: bu kayıt geçmeden sonrakine geçilmez,
                # yoksa daha eski bir stok durumu daha yenisinin
                # üzerine yazılabilir.
                await asyncio.to_thread(sqlite_store.outbox_failed, item["op_id"], str(e))
                self._last_error = str(e)
                log.warning("Kayıt aktarılamadı (op_id=%s, deneme=%d): %s",
                            item["op_id"][:8], item["attempts"] + 1, e)
                break

        if done:
            await asyncio.to_thread(sqlite_store.outbox_done, done)
            self._synced_total += len(done)
            log.info("%d kayıt MongoDB'ye aktarıldı (toplam %d).", len(done), self._synced_total)

        remaining = await asyncio.to_thread(sqlite_store.outbox_count)
        return {"synced": len(done), "pending": remaining, "online": self._online}

    async def _apply(self, kind: str, payload: Dict[str, Any]) -> None:
        """Tek bir kuyruk kaydını MongoDB'ye uygular."""
        if kind == "consume":
            await col_stock().update_one(
                {"_id": "current"},
                {"$set": {**payload["stock"], "updated_at": payload["log"]["ordered_at"]}},
                upsert=True,
            )
            doc = dict(payload["log"])
            op_id = doc.pop("op_id")
            await col_order_logs().update_one({"_id": op_id}, {"$set": doc}, upsert=True)

        elif kind == "refill":
            await col_stock().update_one(
                {"_id": "current"},
                {"$set": {**payload["stock"], "updated_at": payload["log"]["refilled_at"]}},
                upsert=True,
            )
            doc = dict(payload["log"])
            op_id = doc.pop("op_id")
            await col_refill_logs().update_one({"_id": op_id}, {"$set": doc}, upsert=True)

        elif kind == "thresholds":
            await col_thresholds().update_one(
                {"_id": "current"}, {"$set": payload["thresholds"]}, upsert=True
            )

        elif kind in ("syrup_consume", "syrup_refill"):
            syrup = payload.get("syrup")
            if syrup:
                ch = syrup["channel"]
                await col_syrup_stock().update_one(
                    {"_id": ch},
                    {"$set": {k: syrup[k] for k in ("name", "ml", "threshold",
                                                    "capacity", "dose_ml")
                              if k in syrup}},
                    upsert=True,
                )

        else:
            raise ValueError(f"Bilinmeyen kuyruk kaydı türü: {kind}")

    # ── Durum ─────────────────────────────────

    async def _refresh_online(self) -> bool:
        was = self._online
        try:
            await mongo_ping()
            self._online = True
            self._last_ok = _iso_now()
            self._last_error = None
        except Exception as e:
            self._online = False
            self._last_error = str(e)

        if was != self._online:
            if self._online:
                log.info("☁️  MongoDB bağlantısı geri geldi.")
            else:
                log.warning("☁️  MongoDB erişilemiyor — kayıtlar yerelde birikiyor. (%s)",
                            self._last_error)
        return self._online

    async def status(self) -> Dict[str, Any]:
        pending = await asyncio.to_thread(sqlite_store.outbox_count)
        return {
            "mongo_enabled": MONGO_ENABLED,
            "mongo_online" : self._online,
            "pending"      : pending,
            "synced_total" : self._synced_total,
            "last_ok"      : self._last_ok,
            "last_error"   : self._last_error,
            "interval_s"   : SYNC_INTERVAL,
            "sqlite_path"  : str(sqlite_store.db_path()),
        }


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════
# AÇILIŞ — YEREL KAYIT YOKSA BULUTTAN TOHUMLA
# ══════════════════════════════════════════════

async def bootstrap() -> Dict[str, Any]:
    """
    SQLite'ı hazırlar.

    Yerel veritabanı HİÇ YOKSA (ilk kurulum) MongoDB'den son bilinen
    stok ve eşik değerleri okunup başlangıç olarak kullanılır.

    Yerel kayıt VARSA buluttan okuma yapılmaz. Bu bilinçli: kiosk
    çevrimdışıyken yapılan işlemler buluttaki eski değerle ezilmemeli.
    """
    seed_stock = seed_thresholds = None
    source = "varsayılan"

    fresh = not sqlite_store.db_path().exists()

    if fresh and MONGO_ENABLED:
        try:
            await mongo_ping()
            doc = await col_stock().find_one({"_id": "current"})
            th  = await col_thresholds().find_one({"_id": "current"})
            if doc:
                seed_stock = {k: doc[k] for k in ("coffee_g", "milk_ml", "choc_g", "cups") if k in doc}
                source = "MongoDB"
            if th:
                seed_thresholds = {k: th[k] for k in ("coffee_g", "milk_ml", "choc_g", "cups") if k in th}
            log.info("İlk kurulum: başlangıç değerleri MongoDB'den alındı.")
        except Exception as e:
            log.warning("İlk kurulumda MongoDB okunamadı, varsayılanlar kullanılacak: %s", e)

    # Şurup kanal adlarını channel_config'den tohumla — SQLite'ta
    # ad boş kalmasın.
    try:
        from service.syrup_recipes import channel_config
        seed_syrup = {ch: {"name": cfg.get("name")} for ch, cfg in channel_config.items()}
    except Exception:
        seed_syrup = None

    await asyncio.to_thread(sqlite_store.init, seed_stock, seed_thresholds, seed_syrup)

    pending = await asyncio.to_thread(sqlite_store.outbox_count)
    if pending:
        log.warning("Kuyrukta %d aktarılmamış kayıt var (önceki oturumdan).", pending)

    return {"fresh": fresh, "source": source, "pending": pending}


# Tekil örnek
sync = SyncService()
