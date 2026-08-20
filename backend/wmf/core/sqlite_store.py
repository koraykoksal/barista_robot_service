"""
core/sqlite_store.py

Yerel veri deposu — SQLite.

ROLÜ:
  Kiosk'un operasyonel kaydı. Tüm stok yazmaları ÖNCE buraya gider ve
  senkron olarak tamamlanır. Böylece internet kopsa, Atlas yavaşlasa
  veya DNS çözülmese bile sipariş akışı stok adımında takılmaz.

  MongoDB'ye aktarım `outbox` tablosu üzerinden asenkron yapılır
  (bkz. service/sync_service.py).

NEDEN OUTBOX:
  Her yazma işlemi, sonucu MongoDB'ye taşıyacak bir kayıt bırakır.
  Bağlantı yokken kuyruk birikir, bağlantı gelince sırayla boşalır.
  Hiçbir işlem kaybolmaz.

NEDEN KUYRUKTA MUTLAK DEĞER TAŞINIYOR:
  Kuyruk kaydı "9 g düş" gibi bir FARK değil, işlem sonrası oluşan
  TAM stok durumunu taşır. Bunun sebebi tekrar güvenliği: aktarım
  yarıda kalıp yeniden denendiğinde fark iki kez uygulanırsa stok
  bozulur, mutlak değer ise kaç kez yazılırsa yazılsın aynı sonucu
  verir. SQLite tek yazar olduğu için de çakışma oluşmaz.

EŞZAMANLILIK:
  WAL kipi açık; okuma ve yazma birbirini kilitlemez.
  Tüm çağrılar senkron; asenkron kod bunları asyncio.to_thread ile
  çağırmalıdır (stock_service bunu yapar).
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.applog import get_logger
from core.config import APP_ROOT, SQLITE_PATH, SYRUP_DEFAULT_DOSE_ML

log = get_logger(__name__)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    p = Path(SQLITE_PATH)
    return p if p.is_absolute() else APP_ROOT / p


# ══════════════════════════════════════════════
# ŞEMA
# ══════════════════════════════════════════════

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock (
    id          TEXT PRIMARY KEY,
    coffee_g    REAL    NOT NULL DEFAULT 0,
    milk_ml     REAL    NOT NULL DEFAULT 0,
    choc_g      REAL    NOT NULL DEFAULT 0,
    cups        INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS thresholds (
    id          TEXT PRIMARY KEY,
    coffee_g    REAL    NOT NULL DEFAULT 0,
    milk_ml     REAL    NOT NULL DEFAULT 0,
    choc_g      REAL    NOT NULL DEFAULT 0,
    cups        INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS order_logs (
    op_id         TEXT PRIMARY KEY,
    job_id        TEXT,
    button_number INTEGER,
    recipe_name   TEXT,
    coffee_g      REAL,
    milk_ml       REAL,
    choc_g        REAL,
    cups          INTEGER,
    raw_recipe    TEXT,
    ordered_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_order_logs_at ON order_logs(ordered_at DESC);

CREATE TABLE IF NOT EXISTS refill_logs (
    op_id       TEXT PRIMARY KEY,
    payload     TEXT,
    note        TEXT,
    refilled_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_refill_logs_at ON refill_logs(refilled_at DESC);

-- MongoDB'ye aktarılmayı bekleyen işlemler
CREATE TABLE IF NOT EXISTS outbox (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    op_id      TEXT UNIQUE NOT NULL,
    kind       TEXT NOT NULL,          -- consume | refill | thresholds
    payload    TEXT NOT NULL,          -- JSON
    created_at TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_seq ON outbox(seq);

-- Şurup kanalları — her kanal ayrı bir şurup, ml cinsinden.
-- Ana malzemelerden (coffee/milk/choc/cups) ayrı tutulur çünkü
-- kanal bazlı ve tarifler de kanala bağlı.
-- dose_ml: bu kanaldan bir siparişte akıtılacak miktar. Sipariş bazlı
-- değil kanal bazlı: müşteri "vanilya" seçer, kaç mL akacağını personel
-- /stock sayfasından belirler.
CREATE TABLE IF NOT EXISTS syrup_stock (
    channel     INTEGER PRIMARY KEY,   -- 1..8
    name        TEXT,
    ml          REAL    NOT NULL DEFAULT 0,
    threshold   REAL    NOT NULL DEFAULT 50,
    capacity    REAL    NOT NULL DEFAULT 1000,   -- şişe hacmi (dolum tavanı)
    dose_ml     REAL    NOT NULL DEFAULT 8,      -- sipariş başına akıtılan
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


DEFAULT_STOCK = {"coffee_g": 700.0, "milk_ml": 5000.0, "choc_g": 500.0, "cups": 70}
DEFAULT_THRESHOLDS = {"coffee_g": 50.0, "milk_ml": 350.0, "choc_g": 50.0, "cups": 2}

# Şurup kanalları başlangıç değerleri. name/threshold/capacity ml.
# channel_config ile hizalı; init'te üzerine yazılabilir.
DEFAULT_SYRUP = {
    1: {"name": "Vanilya",        "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
    2: {"name": "Karamel",        "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
    3: {"name": "Çikolata",       "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
    4: {"name": "Beyaz Çikolata", "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
    5: {"name": "Fındık",         "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
    6: {"name": "Çilek",          "ml": 1000.0, "threshold": 50.0, "capacity": 1000.0},
}

# Şurup kanalı satırlarında okunan/yazılan alanlar — tek yerde tutulur ki
# yeni bir sütun eklendiğinde beş ayrı SELECT'i güncellemek gerekmesin.
_SYRUP_COLUMNS = "channel, name, ml, threshold, capacity, dose_ml, updated_at"


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10.0)
        _conn.row_factory = sqlite3.Row
        # WAL: okuma ve yazma birbirini kilitlemez.
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        log.info("SQLite açıldı → %s", path)
    return _conn


def init(seed_stock: Optional[Dict] = None, seed_thresholds: Optional[Dict] = None,
         seed_syrup: Optional[Dict] = None) -> None:
    """
    Şemayı kurar ve boşsa varsayılan satırları yazar.

    seed_stock / seed_thresholds verilirse (MongoDB'den okunan değerler)
    yerel kayıt YOKKEN onlar kullanılır. Yerel kayıt varsa dokunulmaz —
    çevrimdışı yapılan işlemler buluttaki eski değerle ezilmez.
    """
    with _lock:
        conn = connect()
        conn.executescript(_SCHEMA)

        row = conn.execute("SELECT 1 FROM stock WHERE id='current'").fetchone()
        if row is None:
            values = {**DEFAULT_STOCK, **(seed_stock or {})}
            conn.execute(
                "INSERT INTO stock (id, coffee_g, milk_ml, choc_g, cups, updated_at) "
                "VALUES ('current', ?, ?, ?, ?, ?)",
                (values["coffee_g"], values["milk_ml"], values["choc_g"],
                 int(values["cups"]), _now_iso()),
            )
            log.info("SQLite stok satırı oluşturuldu (%s): %s",
                     "MongoDB'den" if seed_stock else "varsayılan", values)

        row = conn.execute("SELECT 1 FROM thresholds WHERE id='current'").fetchone()
        if row is None:
            values = {**DEFAULT_THRESHOLDS, **(seed_thresholds or {})}
            conn.execute(
                "INSERT INTO thresholds (id, coffee_g, milk_ml, choc_g, cups, updated_at) "
                "VALUES ('current', ?, ?, ?, ?, ?)",
                (values["coffee_g"], values["milk_ml"], values["choc_g"],
                 int(values["cups"]), _now_iso()),
            )
            log.info("SQLite eşik satırı oluşturuldu: %s", values)

        _migrate(conn)

        # Şurup kanalları — yoksa varsayılandan oluştur.
        # seed_syrup verilirse (kanal adları channel_config'den) adlar
        # ondan alınır.
        existing = {r["channel"] for r in conn.execute("SELECT channel FROM syrup_stock").fetchall()}
        seed_syrup = seed_syrup or {}
        for ch, defaults in DEFAULT_SYRUP.items():
            if ch in existing:
                continue
            name = seed_syrup.get(ch, {}).get("name", defaults["name"])
            conn.execute(
                "INSERT INTO syrup_stock "
                "(channel, name, ml, threshold, capacity, dose_ml, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ch, name, defaults["ml"], defaults["threshold"], defaults["capacity"],
                 float(SYRUP_DEFAULT_DOSE_ML), _now_iso()),
            )
        conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Şema geçişleri.

    CREATE TABLE IF NOT EXISTS mevcut bir tabloyu DEĞİŞTİRMEZ — sahada
    zaten kiosk.db bulunan kurulumlarda yeni sütun kendiliğinden gelmez.
    Eksik sütunlar burada tek tek eklenir; işlem tekrar çalıştırılabilir.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(syrup_stock)").fetchall()}
    if "dose_ml" not in cols:
        conn.execute(
            f"ALTER TABLE syrup_stock ADD COLUMN dose_ml REAL NOT NULL "
            f"DEFAULT {float(SYRUP_DEFAULT_DOSE_ML)}"
        )
        log.info("SQLite geçişi: syrup_stock.dose_ml sütunu eklendi "
                 "(varsayılan %.1f mL).", float(SYRUP_DEFAULT_DOSE_ML))


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
            log.info("SQLite kapatıldı.")


# ══════════════════════════════════════════════
# OKUMA
# ══════════════════════════════════════════════

def get_stock() -> Dict[str, Any]:
    with _lock:
        row = connect().execute(
            "SELECT coffee_g, milk_ml, choc_g, cups, updated_at FROM stock WHERE id='current'"
        ).fetchone()
    return dict(row) if row else {**DEFAULT_STOCK, "updated_at": None}


def get_thresholds() -> Dict[str, Any]:
    with _lock:
        row = connect().execute(
            "SELECT coffee_g, milk_ml, choc_g, cups, updated_at FROM thresholds WHERE id='current'"
        ).fetchone()
    return dict(row) if row else {**DEFAULT_THRESHOLDS, "updated_at": None}


def get_syrup_stock() -> List[Dict[str, Any]]:
    """Tüm şurup kanalları — stok durumu ekranı ve kapı kontrolü için."""
    with _lock:
        rows = connect().execute(
            f"SELECT {_SYRUP_COLUMNS} FROM syrup_stock ORDER BY channel"
        ).fetchall()
    return [dict(r) for r in rows]


def get_syrup_channel(channel: int) -> Optional[Dict[str, Any]]:
    with _lock:
        row = connect().execute(
            f"SELECT {_SYRUP_COLUMNS} FROM syrup_stock WHERE channel = ?", (int(channel),)
        ).fetchone()
    return dict(row) if row else None


def get_order_logs(limit: int = 50) -> List[Dict[str, Any]]:
    with _lock:
        rows = connect().execute(
            "SELECT * FROM order_logs ORDER BY ordered_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("raw_recipe"):
            try:
                d["raw_recipe"] = json.loads(d["raw_recipe"])
            except (ValueError, TypeError):
                pass
        out.append(d)
    return out


def get_refill_logs(limit: int = 20) -> List[Dict[str, Any]]:
    with _lock:
        rows = connect().execute(
            "SELECT * FROM refill_logs ORDER BY refilled_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["refilled"] = json.loads(d.pop("payload") or "{}")
        except (ValueError, TypeError):
            d["refilled"] = {}
        out.append(d)
    return out


# ══════════════════════════════════════════════
# YAZMA
# ══════════════════════════════════════════════

def _queue(conn: sqlite3.Connection, op_id: str, kind: str, payload: Dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO outbox (op_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
        (op_id, kind, json.dumps(payload, ensure_ascii=False, default=str), _now_iso()),
    )


def consume(
    button_number: int,
    coffee_g: float,
    milk_ml: float,
    choc_g: float,
    cups: int,
    job_id: str = "",
    recipe_name: str = "",
    raw_recipe: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Stoktan düşer, sipariş logunu yazar ve kuyruğa ekler — hepsi tek
    işlemde (transaction).

    Negatife düşme MAX(0, ...) ile engellenir. Önceki sürüm koşulsuz
    $inc kullanıyordu ve stok eksiye inebiliyordu.
    """
    op_id = str(uuid.uuid4())
    now = _now_iso()

    with _lock:
        conn = connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                """UPDATE stock SET
                       coffee_g   = MAX(0, coffee_g - ?),
                       milk_ml    = MAX(0, milk_ml  - ?),
                       choc_g     = MAX(0, choc_g   - ?),
                       cups       = MAX(0, cups     - ?),
                       updated_at = ?
                   WHERE id='current'""",
                (coffee_g, milk_ml, choc_g, int(cups), now),
            )
            conn.execute(
                """INSERT INTO order_logs
                       (op_id, job_id, button_number, recipe_name,
                        coffee_g, milk_ml, choc_g, cups, raw_recipe, ordered_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (op_id, job_id, int(button_number), recipe_name,
                 coffee_g, milk_ml, choc_g, int(cups),
                 json.dumps(raw_recipe, ensure_ascii=False, default=str) if raw_recipe else None,
                 now),
            )
            row = conn.execute(
                "SELECT coffee_g, milk_ml, choc_g, cups FROM stock WHERE id='current'"
            ).fetchone()
            remaining = dict(row)

            _queue(conn, op_id, "consume", {
                "op_id": op_id,
                "stock": remaining,          # işlem SONRASI mutlak durum
                "log": {
                    "op_id": op_id, "job_id": job_id,
                    "button_number": int(button_number), "recipe_name": recipe_name,
                    "coffee_g": coffee_g, "milk_ml": milk_ml, "choc_g": choc_g,
                    "cups": int(cups), "raw_recipe": raw_recipe, "ordered_at": now,
                },
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    log.info("Stok düşüldü [%s] btn=%s kahve=%.1fg süt=%.0fml çik=%.1fg bardak=%d → kalan %s",
             job_id[:8] or "-", button_number, coffee_g, milk_ml, choc_g, cups, remaining)
    return {"op_id": op_id, "consumed": {
        "coffee_g": coffee_g, "milk_ml": milk_ml, "choc_g": choc_g, "cups": int(cups)
    }, "remaining": remaining}


def consume_syrup(channel: int, ml: float, job_id: str = "") -> Dict[str, Any]:
    """
    Bir şurup kanalından ml düşer ve kuyruğa ekler.
    Negatife düşmez (MAX(0, ...)).
    """
    op_id = str(uuid.uuid4())
    now = _now_iso()
    ch = int(channel)

    with _lock:
        conn = connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE syrup_stock SET ml = MAX(0, ml - ?), updated_at = ? WHERE channel = ?",
                (float(ml), now, ch),
            )
            row = conn.execute(
                f"SELECT {_SYRUP_COLUMNS} FROM syrup_stock WHERE channel = ?", (ch,)
            ).fetchone()
            remaining = dict(row) if row else None

            _queue(conn, op_id, "syrup_consume", {
                "op_id": op_id, "channel": ch, "ml": float(ml),
                "job_id": job_id,
                "syrup": remaining, "at": now,
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    log.info("Şurup düşüldü [%s] kanal=%d -%.1fml → kalan %.1fml",
             job_id[:8] or "-", ch, ml, remaining["ml"] if remaining else 0)
    return {"op_id": op_id, "channel": ch, "consumed_ml": float(ml), "remaining": remaining}


def refill_syrup(channel: int, ml: Optional[float] = None,
                 threshold: Optional[float] = None,
                 capacity: Optional[float] = None,
                 name: Optional[str] = None,
                 dose_ml: Optional[float] = None) -> Dict[str, Any]:
    """
    Şurup kanalını günceller. ml YENİDEN YAZILIR (eklenmez).
    Verilmeyen alanlara dokunulmaz.
    """
    op_id = str(uuid.uuid4())
    now = _now_iso()
    ch = int(channel)

    fields, params = [], []
    for key, val in (("ml", ml), ("threshold", threshold),
                     ("capacity", capacity), ("dose_ml", dose_ml), ("name", name)):
        if val is None:
            continue
        if key != "name":
            val = float(val)
            if val < 0:
                raise ValueError(f"{key} negatif olamaz.")
        fields.append(f"{key} = ?")
        params.append(val)

    if not fields:
        raise ValueError("En az bir alan belirtilmeli.")

    with _lock:
        conn = connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                f"UPDATE syrup_stock SET {', '.join(fields)}, updated_at = ? WHERE channel = ?",
                (*params, now, ch),
            )
            row = conn.execute(
                f"SELECT {_SYRUP_COLUMNS} FROM syrup_stock WHERE channel = ?", (ch,)
            ).fetchone()
            current = dict(row) if row else None
            _queue(conn, op_id, "syrup_refill", {"op_id": op_id, "channel": ch, "syrup": current})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    log.info("Şurup kanalı %d güncellendi → %s", ch, current)
    return current


def refill(values: Dict[str, Any], note: str = "") -> Dict[str, Any]:
    """
    Belirtilen malzemelerin miktarını YENİDEN YAZAR (eklemez).
    Boş bırakılan alanlara dokunulmaz.
    """
    op_id = str(uuid.uuid4())
    now = _now_iso()

    fields, params = [], []
    applied: Dict[str, Any] = {}
    for key in ("coffee_g", "milk_ml", "choc_g", "cups"):
        v = values.get(key)
        if v is None:
            continue
        v = int(v) if key == "cups" else float(v)
        if v < 0:
            raise ValueError(f"{key} negatif olamaz.")
        fields.append(f"{key} = ?")
        params.append(v)
        applied[key] = v

    if not fields:
        raise ValueError("En az bir malzeme miktarı belirtilmeli.")

    with _lock:
        conn = connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                f"UPDATE stock SET {', '.join(fields)}, updated_at = ? WHERE id='current'",
                (*params, now),
            )
            conn.execute(
                "INSERT INTO refill_logs (op_id, payload, note, refilled_at) VALUES (?,?,?,?)",
                (op_id, json.dumps(applied, ensure_ascii=False), note, now),
            )
            row = conn.execute(
                "SELECT coffee_g, milk_ml, choc_g, cups FROM stock WHERE id='current'"
            ).fetchone()
            remaining = dict(row)

            _queue(conn, op_id, "refill", {
                "op_id": op_id,
                "stock": remaining,
                "log": {"op_id": op_id, "refilled": applied, "note": note, "refilled_at": now},
            })
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    log.info("Stok yenilendi: %s (not=%r) → %s", applied, note, remaining)
    return {"op_id": op_id, "refilled": applied, "note": note, "remaining": remaining}


def set_thresholds(values: Dict[str, Any]) -> Dict[str, Any]:
    op_id = str(uuid.uuid4())
    now = _now_iso()

    fields, params = [], []
    for key in ("coffee_g", "milk_ml", "choc_g", "cups"):
        v = values.get(key)
        if v is None:
            continue
        v = int(v) if key == "cups" else float(v)
        if v < 0:
            raise ValueError(f"{key} negatif olamaz.")
        fields.append(f"{key} = ?")
        params.append(v)

    if not fields:
        raise ValueError("En az bir eşik değeri belirtilmeli.")

    with _lock:
        conn = connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                f"UPDATE thresholds SET {', '.join(fields)}, updated_at = ? WHERE id='current'",
                (*params, now),
            )
            row = conn.execute(
                "SELECT coffee_g, milk_ml, choc_g, cups, updated_at FROM thresholds WHERE id='current'"
            ).fetchone()
            current = dict(row)
            _queue(conn, op_id, "thresholds", {"op_id": op_id, "thresholds": current})
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    log.info("Eşikler güncellendi: %s", current)
    return current


# ══════════════════════════════════════════════
# KUYRUK (OUTBOX)
# ══════════════════════════════════════════════

def outbox_pending(limit: int = 200) -> List[Dict[str, Any]]:
    """Aktarılmayı bekleyen işlemler, eklendikleri sırayla."""
    with _lock:
        rows = connect().execute(
            "SELECT seq, op_id, kind, payload, attempts FROM outbox ORDER BY seq LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def outbox_done(op_ids: List[str]) -> None:
    """Aktarımı tamamlanan kayıtları kuyruktan siler."""
    if not op_ids:
        return
    with _lock:
        conn = connect()
        conn.executemany("DELETE FROM outbox WHERE op_id = ?", [(o,) for o in op_ids])
        conn.commit()


def outbox_failed(op_id: str, error: str) -> None:
    """Deneme sayacını artırır ve son hatayı saklar."""
    with _lock:
        conn = connect()
        conn.execute(
            "UPDATE outbox SET attempts = attempts + 1, last_error = ? WHERE op_id = ?",
            (error[:500], op_id),
        )
        conn.commit()


def outbox_count() -> int:
    with _lock:
        row = connect().execute("SELECT COUNT(*) AS n FROM outbox").fetchone()
    return int(row["n"]) if row else 0


# ══════════════════════════════════════════════
# META
# ══════════════════════════════════════════════

def meta_get(key: str) -> Optional[str]:
    with _lock:
        row = connect().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def meta_set(key: str, value: str) -> None:
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        conn.commit()
