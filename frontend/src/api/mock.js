/**
 * api/mock.js — ÇEVRİMDIŞI TEST MODU
 *
 * Backend, kahve makinesi ve robot olmadan arayüz tasarımını
 * denemek için sahte bir API katmanı.
 *
 * NASIL AÇILIR — iki yol var:
 *
 *   A) URL ile (hızlı, sunucuyu yeniden başlatmak gerekmez):
 *       http://localhost:5173/?offline=1
 *       http://localhost:5173/?offline=1&scenario=machine-error&speed=0.2
 *
 *   B) frontend/.env içine (kalıcı):
 *       VITE_OFFLINE=true
 *       ⚠️  Vite .env'i yalnızca sunucu başlarken okur —
 *          düzenledikten sonra dev sunucusunu yeniden başlatın.
 *
 * NE YAPAR:
 *   axios'un adapter'ını değiştirir. Ağa hiç çıkılmaz; her istek
 *   burada karşılanır. Home.jsx ve StockManagement.jsx'te tek satır
 *   değişiklik gerekmez — onlar normal isteklerini atmaya devam eder.
 *
 * SENARYOLAR — ?scenario=... veya VITE_OFFLINE_SCENARIO ile seçilir:
 *   ok             (varsayılan) her şey yolunda
 *   no-service     backend'e hiç ulaşılamıyor (ağ hatası)
 *   machine-offline  kahve makinesi çevrimdışı
 *   machine-error  makine engelleyici hata veriyor (kod 68 + 80)
 *   cleaning       makine temizlik modunda
 *   robot-manual   robot manuel modda
 *   low-stock      süt ve çikolata eşiğin altında (kısmi kısıt)
 *   out-of-stock   bardak bitti (tam kilit)
 *   order-error    sipariş demleme sırasında hata veriyor
 *
 * HIZ — ?speed=... veya VITE_OFFLINE_SPEED ile ayarlanır:
 *   1    gerçek zamanlı (varsayılan). Latte 40 saniye sürer.
 *   0.2  beş kat hızlı — dolum animasyonunu denerken pratik.
 *
 * ⚠️  Üretimde asla VITE_OFFLINE=true ile derlemeyin. Arayüz bu moddayken
 *     ekranın üstünde kalıcı bir "ÇEVRİMDIŞI TEST MODU" şeridi gösterir;
 *     kazara canlıya çıkarsa fark edilsin diye.
 */

/* ═════════════════════════════════════════════
   YAPILANDIRMA

   api/env.js'den gelir — hem .env dosyasından hem URL sorgu
   parametresinden okunur, URL önceliklidir.
   ═════════════════════════════════════════════ */

import { OFFLINE_SCENARIO, OFFLINE_SPEED } from "./env";

export const SCENARIO = OFFLINE_SCENARIO;
const SPEED = OFFLINE_SPEED;

/** Ağ gecikmesi taklidi — arayüzün yükleme durumları da denenebilsin */
const LATENCY_MS = 120;

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/* ═════════════════════════════════════════════
   İÇECEK SÜRELERİ
   Backend'deki catalog.py ile aynı değerler.
   ═════════════════════════════════════════════ */

const BREW_SECONDS = {
  1: 23,   // Espresso
  2: 38,   // Americano
  3: 40,   // Latte
  5: 20,   // Ristretto
  12: 28,  // Cappuccino
  14: 41,  // Sütlü Çikolata
  // Çevrimdışı demo soğuk içecekler 
  7: 34,
};

/* ═════════════════════════════════════════════
   SAHTE DURUM
   ═════════════════════════════════════════════ */

const s = SCENARIO;

const machineState = () => {
  if (s === "machine-offline") {
    return { online: false, has_error: false, has_blocking_error: false,
             errors: [], blocking_errors: [], cleaning: null, rinsing: null,
             error_description: null };
  }
  if (s === "machine-error") {
    return { online: true, has_error: true, has_blocking_error: true,
             errors: [68, 80], blocking_errors: [68, 80], cleaning: null, rinsing: null,
             error_description: "Çekirdek kahve bölmesi boş veya kapağı açık | Su deposu boş veya yerinde değil" };
  }
  if (s === "cleaning") {
    return { online: true, has_error: false, has_blocking_error: false,
             errors: [], blocking_errors: [], cleaning: { type: "sistem temizliği" },
             rinsing: null, error_description: null };
  }
  return { online: true, has_error: false, has_blocking_error: false,
           errors: [], blocking_errors: [], cleaning: null, rinsing: null,
           error_description: null };
};

const robotState = () => {
  if (s === "robot-manual") {
    return { connected: true, robot_mode: 1, robot_state: 1,
             mode_label: "manual", state_label: "stopped", can_order: false };
  }
  return { connected: true, robot_mode: 0, robot_state: 1,
           mode_label: "auto", state_label: "ready", can_order: true };
};

// Stok canlı tutulur — sipariş verildikçe düşer, /stock/refill ile dolar
const stock = (() => {
  if (s === "out-of-stock") return { coffee_g: 620, milk_ml: 4200, choc_g: 430, cups: 1 };
  if (s === "low-stock")    return { coffee_g: 620, milk_ml: 180,  choc_g: 30,  cups: 44 };
  return { coffee_g: 700, milk_ml: 5000, choc_g: 500, cups: 70 };
})();

const thresholds = { coffee_g: 50, milk_ml: 350, choc_g: 50, cups: 2 };

// Şurup kanalları — senaryoya göre biri düşük olabilir
// dose_ml: bir siparişte bu kanaldan akıtılacak miktar. Backend'de
// syrup_stock tablosunda tutulur; sipariş mesajı miktar taşımaz.
const syrupChannels = (() => {
  const base = {
    1: { channel: 1, name: "Vanilya",        ml: 1000, threshold: 50, dose_ml: 18, low: false },
    2: { channel: 2, name: "Karamel",        ml: 1000, threshold: 50, dose_ml: 18, low: false },
    3: { channel: 3, name: "Çikolata",       ml: 1000, threshold: 50, dose_ml: 18, low: false },
    4: { channel: 4, name: "Beyaz Çikolata", ml: 1000, threshold: 50, dose_ml: 18, low: false },
    5: { channel: 5, name: "Fındık",         ml: 1000, threshold: 50, dose_ml: 18, low: false },
    6: { channel: 6, name: "Çilek",          ml: 1000, threshold: 50, dose_ml: 18, low: false },
  };
  if (s === "low-stock") {
    base[2].ml = 20; base[2].low = true;   // Karamel düşük
  }
  return base;
})();

/**
 * Şurup stok kapısı — backend'deki resolve_syrup_selection'ın karşılığı.
 * Seçilen kanallardan biri eşiğin altındaysa sipariş engellenir.
 */
function syrupGate(channels) {
  for (const raw of channels ?? []) {
    const ch = syrupChannels[Number(raw)];
    if (!ch) {
      return { channel: raw, reason: "channel_missing",
               message: `Kanal ${raw} tanımlı değil.` };
    }
    if (ch.ml < ch.threshold || ch.ml < ch.dose_ml) {
      return {
        channel: ch.channel, name: ch.name,
        reason: ch.ml < ch.threshold ? "below_threshold" : "insufficient",
        remaining_ml: ch.ml, need_ml: ch.dose_ml,
        message: `${ch.name} şurubu yetersiz — bu içecek geçici olarak verilemiyor.`,
      };
    }
  }
  return null;
}

function stockStatus() {
  const coffeeCrit = stock.coffee_g < thresholds.coffee_g;
  const cupsCrit   = stock.cups     < thresholds.cups;
  const milkCrit   = stock.milk_ml  < thresholds.milk_ml;
  const chocCrit   = stock.choc_g   < thresholds.choc_g;

  const allDisabled = coffeeCrit || cupsCrit;
  const alerts = [];

  if (cupsCrit)   alerts.push({ type: "critical", material: "cups",
    message: `Bardak adedi kritik seviyede! Kalan: ${stock.cups} adet (eşik: ${thresholds.cups})`, action: "all_disabled" });
  if (coffeeCrit) alerts.push({ type: "critical", material: "coffee",
    message: `Çekirdek kahve kritik seviyede! Kalan: ${stock.coffee_g.toFixed(1)}g`, action: "all_disabled" });
  if (milkCrit && !allDisabled) alerts.push({ type: "warning", material: "milk",
    message: `Süt miktarı düşük! Kalan: ${stock.milk_ml.toFixed(0)}ml`, action: "milk_disabled" });
  if (chocCrit && !allDisabled) alerts.push({ type: "warning", material: "chocolate",
    message: `Çikolata miktarı düşük! Kalan: ${stock.choc_g.toFixed(1)}g`, action: "choc_disabled" });

  const disabled_syrup_channels = Object.values(syrupChannels)
    .filter((c) => c.low)
    .map((c) => c.channel);

  return {
    stock: { ...stock },
    thresholds: { ...thresholds },
    syrup_channels: syrupChannels,
    disabled_syrup_channels,
    status: {
      overall: alerts.some((a) => a.type === "critical") ? "critical"
             : alerts.length ? "warning" : "ok",
      all_disabled : allDisabled,
      milk_disabled: milkCrit,
      choc_disabled: chocCrit,
    },
    alerts,
    updated_at: new Date().toISOString(),
  };
}

/* ═════════════════════════════════════════════
   SİPARİŞ SİMÜLASYONU

   Backend'in ürettiği fazlar aynı sırayla, gerçekçi sürelerle
   yürütülür. Böylece dolum göstergesi, faz etiketleri ve
   "yeni siparişe hazır" akışı backend olmadan denenebilir.
   ═════════════════════════════════════════════ */

const jobs = new Map();

function startJob(body) {
  const buttonNumber = body?.message?.a_iBtnNbr;
  const useIce  = Boolean(body?.ice);
  const syrups  = Array.isArray(body?.syrups) ? body.syrups : [];
  const jobId = `offline-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
  const brew = BREW_SECONDS[Number(buttonNumber)] ?? 25;

  // Zaman çizelgesi sipariş TİPİNE göre kurulur — backend'in ürettiği
  // fazların aynısı. Buzsuz siparişte buz fazı hiç görünmez.
  const timeline = [
    { phase: "created",              ms: 300 },
    ...(useIce || syrups.length ? [{ phase: "set_sysvars", ms: 250 }] : []),
    { phase: "set_do0_true",         ms: 700 },
    ...(useIce ? [{ phase: "wait_di9_ice", ms: 4200 }] : []),
    ...(syrups.length ? [
      { phase: "wait_di8_syrup", ms: 3000 },
      { phase: "syrup_dispense", ms: 1400 * syrups.length },
      { phase: "set_do7_true",   ms: 500 },
    ] : []),
    { phase: "wait_di1_robot_ready", ms: 3200 },
    { phase: "coffee_task_start",    ms: 900 },
    { phase: `timer_${brew}s`,       ms: brew * 1000 },
    { phase: "set_do2_true",         ms: 600 },
    { phase: "wait_di3_robot_done",  ms: 2600 },
    { phase: "robot_delivered",      ms: 0 },
  ];

  const job = { status: "running", phase: "created", rcp_state: null, error: null };
  jobs.set(jobId, job);

  (async () => {
    for (let i = 0; i < timeline.length; i += 1) {
      const step = timeline[i];
      job.phase = step.phase;
      job.status = step.phase.startsWith("timer_") || step.phase.startsWith("wait_")
        ? "waiting" : "running";

      // Demleme sırasında makine Rcp State yayınlar
      if (step.phase.startsWith("timer_")) job.rcp_state = 99;

      // order-error senaryosu: demlemenin ortasında hata
      if (s === "order-error" && step.phase.startsWith("timer_")) {
        await wait((step.ms / 2) * SPEED);
        job.status = "error";
        job.phase  = "aborted";
        job.error  = "Makine hatası: Çekirdek kahve bölmesi boş veya kapağı açık";
        return;
      }

      await wait(step.ms * SPEED);
    }

    job.phase  = "robot_delivered";
    job.status = "done";
    job.rcp_state = 9;

    // Stok düş — /stock/status yanıtı gerçekten değişsin
    const btn = Number(buttonNumber);
    stock.cups = Math.max(0, stock.cups - 1);
    stock.coffee_g = Math.max(0, stock.coffee_g - 9);
    if ([3, 12, 14, 901, 902].includes(btn)) stock.milk_ml = Math.max(0, stock.milk_ml - 150);
    if (btn === 14) stock.choc_g = Math.max(0, stock.choc_g - 20);

    // Akıtılan şurup da kanaldan düşer
    for (const raw of syrups) {
      const ch = syrupChannels[Number(raw)];
      if (!ch) continue;
      ch.ml = Math.max(0, ch.ml - ch.dose_ml);
      ch.low = ch.ml < ch.threshold;
    }
  })();

  return jobId;
}

/* ═════════════════════════════════════════════
   YÖNLENDİRME
   ═════════════════════════════════════════════ */

const ok = (data, config) => ({
  data, status: 200, statusText: "OK", headers: {}, config,
});

function route(config) {
  // baseURL'i at, yalnızca yol kalsın
  const url = String(config.url || "").replace(/^https?:\/\/[^/]+/, "");
  const method = (config.method || "get").toLowerCase();
  const body = config.data ? JSON.parse(config.data) : {};

  if (url === "/" || url === "")        return ok({ response: "Coffee Service is running (OFFLINE MOCK).", version: "offline", admin_protected: false }, config);
  if (url === "/machine/status")        return ok(machineState(), config);
  if (url === "/robot/status")          return ok(robotState(), config);
  if (url === "/stock/status")          return ok(stockStatus(), config);
  if (url === "/stock/syrup")           return ok({ channels: Object.values(syrupChannels).map(c => ({ ...c, capacity: 1000, updated_at: new Date().toISOString() })) }, config);
  if (url.startsWith("/stock/syrup/") && method === "put") {
    const ch = Number(url.split("/").pop());
    if (syrupChannels[ch]) {
      if (body.ml != null) { syrupChannels[ch].ml = Number(body.ml); syrupChannels[ch].low = syrupChannels[ch].ml < syrupChannels[ch].threshold; }
      if (body.threshold != null) syrupChannels[ch].threshold = Number(body.threshold);
      if (body.dose_ml != null) syrupChannels[ch].dose_ml = Number(body.dose_ml);
      if (body.name != null) syrupChannels[ch].name = body.name;
    }
    return ok(syrupChannels[ch] ?? {}, config);
  }

  if (url === "/check_beverage") {
    const m = machineState();
    // Şurup kapısı makineden ÖNCE uygulanır — backend de böyle yapıyor.
    const blocked = syrupGate(body.syrups);
    if (blocked) {
      return ok({
        ws_uri: "ws://offline/",
        sent: body.message,
        result: { returnvalue: 5, status: "syrup_unavailable" },
        machine_error_detail: null,
        syrup_block: blocked,
      }, config);
    }
    const returnvalue = !m.online ? 1 : m.has_blocking_error ? 4 : 0;
    return ok({
      ws_uri: "ws://offline/",
      sent: body.message,
      result: { returnvalue, status: returnvalue === 0 ? "ready" : "not ready" },
      machine_error_detail: returnvalue === 4 ? m.error_description : null,
      syrup_block: null,
    }, config);
  }

  if (url === "/order_standart" && method === "post") {
    return ok({ job_id: startJob(body) }, config);
  }

  if (url.startsWith("/order/status/")) {
    const jobId = url.split("/").pop();
    const job = jobs.get(jobId);
    if (!job) {
      const err = new Error("job_id bulunamadı.");
      err.response = { status: 404, data: { detail: "job_id bulunamadı." } };
      throw err;
    }
    return ok({ job_id: jobId, ...job }, config);
  }

  // ── Stok yönetimi ──
  if (url === "/stock/refill" && method === "put") {
    for (const key of ["coffee_g", "milk_ml", "choc_g", "cups"]) {
      if (body[key] !== null && body[key] !== undefined) stock[key] = Number(body[key]);
    }
    return ok({ refilled: body, note: body.note ?? "", remaining: { ...stock } }, config);
  }

  if (url === "/stock/thresholds" && method === "put") {
    for (const key of ["coffee_g", "milk_ml", "choc_g", "cups"]) {
      if (body[key] !== null && body[key] !== undefined) thresholds[key] = Number(body[key]);
    }
    return ok({ ...thresholds }, config);
  }

  if (url.startsWith("/stock/logs/orders")) {
    return ok(
      Array.from({ length: 8 }, (_, i) => ({
        job_id: `offline-demo-${i}`,
        button_number: [1, 2, 3, 12][i % 4],
        recipe_name: ["Espresso", "Americano", "Latte", "Cappuccino"][i % 4],
        coffee_g: 9, milk_ml: i % 2 ? 150 : 0, choc_g: 0, cups: 1,
        ordered_at: new Date(Date.now() - i * 3600_000).toISOString(),
      })),
      config
    );
  }

  if (url.startsWith("/stock/logs/refills")) {
    return ok(
      Array.from({ length: 3 }, (_, i) => ({
        refilled: { coffee_g: 700, cups: 70 },
        note: "Çevrimdışı demo dolumu",
        refilled_at: new Date(Date.now() - i * 86_400_000).toISOString(),
      })),
      config
    );
  }

  // Tanımsız uç — 404
  const err = new Error(`Çevrimdışı modda tanımsız uç: ${method.toUpperCase()} ${url}`);
  err.response = { status: 404, data: { detail: `Mock'ta karşılığı yok: ${url}` } };
  throw err;
}

/* ═════════════════════════════════════════════
   ADAPTER
   ═════════════════════════════════════════════ */

export function mockAdapter(config) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      // no-service senaryosu: hiçbir istek cevaplanmaz
      if (SCENARIO === "no-service") {
        const err = new Error("Network Error");
        err.code = "ERR_NETWORK";
        reject(err);
        return;
      }
      try {
        resolve(route(config));
      } catch (e) {
        reject(e);
      }
    }, LATENCY_MS);
  });
}
