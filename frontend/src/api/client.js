/**
 * api/client.js
 *
 * Backend adresi, uç noktalar ve ortak hata metinleri.
 *
 * Yapılandırma api/env.js'den gelir; oradaki değerler hem .env
 * dosyasından hem URL sorgu parametresinden okunur.
 */

import axios from "axios";

import {
  ADMIN_TOKEN as TOKEN,
  ALL_MOCKED as EVERYTHING_MOCKED,
  ANY_MOCKED as SOMETHING_MOCKED,
  API_URL,
  MOCKED_LABEL as MOCKED_SERVICES_LABEL,
  OFFLINE as IS_OFFLINE,
  OFFLINE_SCENARIO as SCENARIO,
  OFFLINE_SERVICES as SERVICES,
  POLL as POLL_INTERVALS,
  isMocked,
  logConfig,
} from "./env";
import { mockAdapter } from "./mock";

/* ─────────────────────────────────────────────
   YENİDEN DIŞA AKTARIM
   Çağıran dosyalar tek yerden import etsin diye.
   ───────────────────────────────────────────── */

/** Sondaki eğik çizgi temizlenmiş backend adresi */
export const BASE_URL = API_URL.replace(/\/+$/, "");
export const ADMIN_TOKEN = TOKEN;
export const POLL = POLL_INTERVALS;
export const OFFLINE = IS_OFFLINE;
export const OFFLINE_SCENARIO = SCENARIO;

/** Servis bazlı durum: { machine: true, stock: false, ... } */
export const OFFLINE_SERVICES = SERVICES;
/** En az bir servis sahteyse arayüz uyarı şeridi gösterir */
export const ANY_MOCKED = SOMETHING_MOCKED;
/** Hepsi sahteyse hiç ağ trafiği yoktur */
export const ALL_MOCKED = EVERYTHING_MOCKED;
/** "makine · robot · stok" */
export const MOCKED_LABEL = MOCKED_SERVICES_LABEL;

/* ─────────────────────────────────────────────
   AXIOS ÖRNEĞİ
   ───────────────────────────────────────────── */

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 8000,
  headers: { "Content-Type": "application/json" },
});

/**
 * Sahte katman İSTEK BAZINDA devreye girer.
 *
 * Adapter'ı global olarak değiştirmek yerine her istekte yolun hangi
 * servise ait olduğuna bakıp yalnızca o servis sahteye alınmışsa
 * config.adapter atanıyor. Atanmayan istekler axios'un normal
 * adapter'ıyla gerçek backend'e gider.
 *
 * Bunun iki faydası var:
 *   • Karma çalışma mümkün — makine ve robot sahte, stok gerçek.
 *   • Çağıran dosyalarda (Home.jsx, StockManagement.jsx) tek satır
 *     bile değişmez; normal isteklerini atmaya devam ederler.
 *
 * Tüm servisler sahteyken hiçbir ağ isteği yapılmaz.
 */
if (ANY_MOCKED) {
  api.interceptors.request.use((config) => {
    if (isMocked(config.url)) {
      config.adapter = mockAdapter;
    }
    return config;
  });
}

logConfig();

/** Yönetici uçları için — X-Admin-Token başlığını ekler */
export const adminConfig = () => ({
  headers: ADMIN_TOKEN ? { "X-Admin-Token": ADMIN_TOKEN } : {},
});

/* ─────────────────────────────────────────────
   UÇ NOKTALAR
   ───────────────────────────────────────────── */

export const ENDPOINTS = {
  root:          "/",
  machineStatus: "/machine/status",
  robotStatus:   "/robot/status",

  checkBeverage: "/check_beverage",
  orderStandart: "/order_standart",
  orderStatus:   (jobId) => `/order/status/${jobId}`,
  orderStream:   (jobId) => `${BASE_URL}/order/stream/${jobId}`,  // SSE — tam URL ister

  stockStatus:     "/stock/status",
  stockRefill:     "/stock/refill",
  stockThresholds: "/stock/thresholds",
  stockOrderLogs:  (limit = 30) => `/stock/logs/orders?limit=${limit}`,
  stockRefillLogs: (limit = 20) => `/stock/logs/refills?limit=${limit}`,
};

/* ─────────────────────────────────────────────
   HATA MESAJI NORMALLEŞTİRME
   ───────────────────────────────────────────── */

/**
 * Axios hatasını kullanıcıya gösterilebilir tek bir metne indirger.
 * FastAPI hataları {detail: "..."} biçiminde döner; ağ hatalarında
 * response hiç yoktur.
 */
export function errorText(err, fallback = "Bağlantı hatası.") {
  if (!err) return fallback;

  const detail = err?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  // Pydantic doğrulama hataları dizi döner
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d?.msg).filter(Boolean).join(" · ") || fallback;
  }

  if (err?.code === "ECONNABORTED") return "İstek zaman aşımına uğradı.";

  // Ağ hatasında adresi de göster — "neden bağlanamıyor" sorusunun
  // cevabı çoğu zaman yanlış IP veya kapalı servistir.
  if (err?.message === "Network Error" || err?.code === "ERR_NETWORK") {
    return `${BASE_URL} adresine ulaşılamıyor.`;
  }

  return err?.message || fallback;
}
