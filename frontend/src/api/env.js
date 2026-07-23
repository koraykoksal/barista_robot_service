/**
 * api/env.js — çalışma zamanı yapılandırması
 *
 * Ayarlar iki kaynaktan okunur, URL önceliklidir:
 *
 *   1. URL sorgu parametresi   ?offline=1&live=stock
 *   2. .env dosyası            VITE_OFFLINE=true
 *
 * NEDEN URL DE VAR:
 *   Vite .env dosyasını YALNIZCA sunucu başlarken okur. Dosyayı
 *   düzenleyip sayfayı yenilemek yetmez — dev sunucusunu yeniden
 *   başlatmanız gerekir. Tasarım denerken senaryolar arasında geçmek
 *   için bu çok yavaş.
 *
 *       http://localhost:5173/?offline=1
 *       http://localhost:5173/?offline=1&scenario=machine-error
 *       http://localhost:5173/?offline=1&live=stock
 *
 * BAYRAK OKUMA:
 *   Önceki sürüm String(v) === "true" karşılaştırması yapıyordu ve
 *   şunların hepsi sessizce başarısız oluyordu:
 *       VITE_OFFLINE=TRUE
 *       VITE_OFFLINE=1
 *       VITE_OFFLINE=true      ← sondaki görünmez boşluk
 *   Artık kırpılıyor, küçük harfe çevriliyor ve yaygın doğru
 *   değerlerin hepsi kabul ediliyor.
 */

/* ─────────────────────────────────────────────
   OKUYUCULAR
   ───────────────────────────────────────────── */

const TRUTHY = new Set(["true", "1", "yes", "on", "evet"]);
const FALSY  = new Set(["false", "0", "no", "off", "hayir"]);

/** Metni boolean'a çevirir. Boşluk ve büyük/küçük harf duyarsız. */
export const asFlag = (value) => TRUTHY.has(String(value ?? "").trim().toLowerCase());

/** Değer anlamlı biçimde verilmiş mi (boş/undefined "verilmemiş" sayılır) */
const isSet = (value) => {
  const t = String(value ?? "").trim().toLowerCase();
  return TRUTHY.has(t) || FALSY.has(t);
};

/** Metni sayıya çevirir; geçersizse yedek değer. */
export const asNumber = (value, fallback) => {
  const n = Number(String(value ?? "").trim());
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

/** Metni kırpar; boşsa yedek değer. */
export const asText = (value, fallback = "") => {
  const t = String(value ?? "").trim();
  return t || fallback;
};

/** "stock, robot" → ["stock","robot"] */
const asList = (value) =>
  String(value ?? "")
    .split(",")
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);

/* ─────────────────────────────────────────────
   URL PARAMETRELERİ
   ───────────────────────────────────────────── */

// Node'da (test/derleme) window yok — güvenli varsayılan.
const params =
  typeof window !== "undefined" && window.location
    ? new URLSearchParams(window.location.search)
    : new URLSearchParams();

/* ─────────────────────────────────────────────
   ÇALIŞMA ZAMANI YAPILANDIRMASI

   public/config.js dosyası index.html tarafından düz script olarak
   yüklenir ve window.__KIOSK_CONFIG__ nesnesini kurar. Derlemeye
   dahil olmadığı için sahadaki dist/ klasöründe düzenlenebilir —
   yeniden derleme veya sunucu yeniden başlatma gerekmez.
   ───────────────────────────────────────────── */

const runtime =
  (typeof window !== "undefined" && window.__KIOSK_CONFIG__) || {};

/**
 * Değer okuma zinciri:
 *   1. URL sorgu parametresi   (?categories=coffee)
 *   2. public/config.js
 *   3. .env  (import.meta.env)
 */
const pick = (urlKey, envValue, envKey) => {
  const fromUrl = params.get(urlKey);
  if (fromUrl !== null) return fromUrl;

  if (envKey && runtime[envKey] !== undefined && String(runtime[envKey]).trim() !== "") {
    return runtime[envKey];
  }
  return envValue;
};

/** URL karşılığı olmayan ayarlar için: önce config.js, sonra .env */
const fromConfig = (envKey, envValue) =>
  runtime[envKey] !== undefined && String(runtime[envKey]).trim() !== ""
    ? runtime[envKey]
    : envValue;

/* ─────────────────────────────────────────────
   GENEL AYARLAR
   ───────────────────────────────────────────── */

/** Genel çevrimdışı anahtarı — servis bazlı ayarların varsayılanı */
export const OFFLINE = asFlag(pick("offline", import.meta.env.VITE_OFFLINE, "VITE_OFFLINE"));

/** ?debug=1 → ekran üstü teşhis paneli (kioskta devtools açmadan) */
export const DEBUG = asFlag(params.get("debug"));

export const OFFLINE_SCENARIO = asText(
  pick("scenario", import.meta.env.VITE_OFFLINE_SCENARIO, "VITE_OFFLINE_SCENARIO"),
  "ok"
);

export const OFFLINE_SPEED = asNumber(
  pick("speed", import.meta.env.VITE_OFFLINE_SPEED, "VITE_OFFLINE_SPEED"),
  1
);

export const API_URL = asText(fromConfig("VITE_API_URL", import.meta.env.VITE_API_URL), "http://127.0.0.1:8000");

export const ADMIN_TOKEN = asText(fromConfig("VITE_ADMIN_TOKEN", import.meta.env.VITE_ADMIN_TOKEN));

export const POLL = {
  order:   asNumber(fromConfig("VITE_ORDER_POLL_MS", import.meta.env.VITE_ORDER_POLL_MS), 800),
  machine: asNumber(fromConfig("VITE_MACHINE_POLL_MS", import.meta.env.VITE_MACHINE_POLL_MS), 1000),
  stock:   asNumber(fromConfig("VITE_STOCK_POLL_MS", import.meta.env.VITE_STOCK_POLL_MS), 5000),
  robot:   asNumber(fromConfig("VITE_ROBOT_POLL_MS", import.meta.env.VITE_ROBOT_POLL_MS), 2000),
};

/* ─────────────────────────────────────────────
   SERVİS BAZLI ÇEVRİMDIŞI ANAHTARLARI

   Her servis ayrı ayrı sahteye veya gerçeğe alınabilir. Böylece
   karma çalışma mümkün: kahve makinesi ve robot masanızda yokken
   onları sahteye alıp, çalışan MongoDB üzerinden gerçek stok
   servisini denemek gibi.

   ÖNCELİK SIRASI (yukarıdan aşağıya):
     1. URL  ?mock=machine,robot      → listedekiler SAHTE
     2. URL  ?live=stock              → listedekiler GERÇEK
     3. .env VITE_OFFLINE_STOCK=false
     4. genel VITE_OFFLINE / ?offline değeri

   ÖRNEKLER:
     ?offline=1                       hepsi sahte, hiç ağ trafiği yok
     ?offline=1&live=stock            stok gerçek, kalanı sahte
     ?offline=0&mock=machine,robot    yalnızca makine ve robot sahte
   ───────────────────────────────────────────── */

export const SERVICE_KEYS = ["machine", "robot", "stock", "order", "syrup"];

/** Arayüzde gösterilecek adlar */
export const SERVICE_LABELS = {
  machine: "makine",
  robot:   "robot",
  stock:   "stok",
  order:   "sipariş",
  syrup:   "şurup",
};

const forcedMock = new Set(asList(params.get("mock")));
const forcedLive = new Set(asList(params.get("live")));

const ENV_SERVICE = {
  machine: fromConfig("VITE_OFFLINE_MACHINE", import.meta.env.VITE_OFFLINE_MACHINE),
  robot:   fromConfig("VITE_OFFLINE_ROBOT",   import.meta.env.VITE_OFFLINE_ROBOT),
  stock:   fromConfig("VITE_OFFLINE_STOCK",   import.meta.env.VITE_OFFLINE_STOCK),
  order:   fromConfig("VITE_OFFLINE_ORDER",   import.meta.env.VITE_OFFLINE_ORDER),
  syrup:   fromConfig("VITE_OFFLINE_SYRUP",   import.meta.env.VITE_OFFLINE_SYRUP),
};

function resolveService(key) {
  if (forcedMock.has(key)) return true;
  if (forcedLive.has(key)) return false;
  if (isSet(ENV_SERVICE[key])) return asFlag(ENV_SERVICE[key]);
  return OFFLINE;
}

/** { machine: true, robot: true, stock: false, ... } */
export const OFFLINE_SERVICES = Object.fromEntries(
  SERVICE_KEYS.map((key) => [key, resolveService(key)])
);

/** En az bir servis sahteyse arayüzde uyarı şeridi gösterilir */
export const ANY_MOCKED = SERVICE_KEYS.some((k) => OFFLINE_SERVICES[k]);

/** Hepsi sahte mi — hiç ağ trafiği olmadığı anlamına gelir */
export const ALL_MOCKED = SERVICE_KEYS.every((k) => OFFLINE_SERVICES[k]);

/** Sahteye alınmış servislerin okunabilir listesi: "makine · robot" */
export const MOCKED_LABEL = SERVICE_KEYS
  .filter((k) => OFFLINE_SERVICES[k])
  .map((k) => SERVICE_LABELS[k])
  .join(" · ");


/* ─────────────────────────────────────────────
   MENÜ KATEGORİLERİ

   Hangi kategorinin ekranda görüneceği .env'den denetlenir. Kahve
   makinesi olan ama dondurma ünitesi olmayan bir kurulumda dondurma
   sekmesini kapatmak için kod değişikliği gerekmez.

   Boş bırakılırsa kategori AÇIK sayılır.

   URL karşılığı:  ?categories=coffee        (yalnızca kahve)
                   ?categories=coffee,ice_cream
   ───────────────────────────────────────────── */

const CATEGORY_KEYS = ["coffee", "ice_cream"];

const ENV_CATEGORY = {
  coffee:    fromConfig("VITE_CATEGORY_COFFEE",   import.meta.env.VITE_CATEGORY_COFFEE),
  ice_cream: fromConfig("VITE_CATEGORY_ICECREAM", import.meta.env.VITE_CATEGORY_ICECREAM),
};

const urlCategories = asList(params.get("categories"));

function categoryEnabled(key) {
  if (urlCategories.length) return urlCategories.includes(key);
  if (isSet(ENV_CATEGORY[key])) return asFlag(ENV_CATEGORY[key]);
  return true;   // belirtilmemişse açık
}

/** { coffee: true, ice_cream: false } */
export const CATEGORIES = Object.fromEntries(
  CATEGORY_KEYS.map((key) => [key, categoryEnabled(key)])
);

/** Açık kategori anahtarları */
export const ENABLED_CATEGORIES = CATEGORY_KEYS.filter((k) => CATEGORIES[k]);

/* ─────────────────────────────────────────────
   URL → SERVİS EŞLEMESİ
   ───────────────────────────────────────────── */

/**
 * İstek yolundan hangi servise ait olduğunu bulur.
 *
 * Sipariş uçları tek bir önek altında toplanmadığı için
 * (/order_standart, /order/status/…, /check_beverage) geri kalan
 * her şey "order" sayılır.
 */
export function serviceOf(url) {
  const path = String(url || "").replace(/^https?:\/\/[^/]+/, "");

  if (path.startsWith("/machine")) return "machine";
  if (path.startsWith("/robot"))   return "robot";
  if (path.startsWith("/stock"))   return "stock";
  if (path.startsWith("/syrup"))   return "syrup";
  return "order";
}

/** Bu istek sahte katmandan mı karşılanacak? */
export const isMocked = (url) => OFFLINE_SERVICES[serviceOf(url)] === true;

/* ─────────────────────────────────────────────
   TEŞHİS
   ───────────────────────────────────────────── */

/**
 * Açılışta konsola çözümlenmiş ayarları basar.
 *
 * "Çevrimdışı moda aldım ama hâlâ bağlanmaya çalışıyor" durumunda
 * tek bakışta neyin okunduğu görünsün diye. Genellikle sebep,
 * .env düzenlendikten sonra dev sunucusunun yeniden başlatılmamış
 * olmasıdır.
 */
export function logConfig() {
  if (typeof console === "undefined") return;

  if (ANY_MOCKED) {
    console.warn(
      `%c[ÇEVRİMDIŞI TEST MODU]%c Sahte servisler: ${MOCKED_LABEL}` +
        (ALL_MOCKED
          ? " — hiç ağ isteği yapılmıyor."
          : " — listede olmayanlar gerçek backend'e gidiyor."),
      "background:#15140D;color:#D9DA96;padding:2px 6px;border-radius:2px",
      ""
    );
  } else if (import.meta.env.VITE_OFFLINE && !asFlag(import.meta.env.VITE_OFFLINE)) {
    // Değişken tanımlı ama doğru okunmamış — en sık yapılan hata
    console.warn(
      `[config] VITE_OFFLINE="${import.meta.env.VITE_OFFLINE}" değeri "true" olarak yorumlanmadı. ` +
        "Sondaki boşluğu kontrol edin veya ?offline=1 ile URL'den deneyin."
    );
  }

  console.info("[config]", {
    apiUrl: API_URL,
    scenario: OFFLINE_SCENARIO,
    speed: OFFLINE_SPEED,
    services: OFFLINE_SERVICES,
    categories: CATEGORIES,
    kaynak: Object.keys(runtime).length ? "config.js + .env" : ".env",
  });
}
