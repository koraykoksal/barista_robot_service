import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, ENDPOINTS, adminConfig } from "../api/client";

// ─────────────────────────────────────────────
// PAROLA — değiştirmek için burası yeterli
// ─────────────────────────────────────────────
// Parola .env'den okunur (VITE_ADMIN_PASSWORD); tanımlı değilse
// eski varsayılan kullanılır.
//
// ⚠️  Bu tarayıcıda çalışan bir sabit — derlenmiş pakette açıkça
// görünür ve gerçek bir koruma DEĞİLDİR. Yalnızca personelin
// yanlışlıkla bu sayfaya girmesini engeller. Asıl koruma backend'deki
// X-Admin-Token başlığıdır; artık /stock/refill ve /stock/thresholds
// uçlarına gerçekten takılı.
const ADMIN_PASSWORD   = import.meta.env.VITE_ADMIN_PASSWORD || "wmf2024";
const SESSION_KEY      = "stock_admin_auth";
const SESSION_DURATION = 30 * 60 * 1000; // 30 dakika (ms)

// Backend adresi artık api/client.js üzerinden .env'den gelir.
// Önceden burada sabit yazılıydı ve Home.jsx ile ayrı ayrı güncellenmesi
// gerekiyordu; biri unutulduğunda hata sessiz kalıyordu.
//
// ⚠️  ADMIN_PASSWORD tarayıcıda çalışan bir sabit — derlenmiş pakette
// açıkça görünür ve gerçek bir koruma DEĞİLDİR. Yalnızca personelin
// yanlışlıkla bu sayfaya girmesini engeller. Asıl koruma backend
// tarafındaki X-Admin-Token başlığıdır (bkz. adminConfig).

/** Oturumun bitmesine kalan dakika. ts null ise 0. */
const minutesLeft = (ts) =>
  ts === null || ts === undefined
    ? 0
    : Math.max(0, Math.ceil((SESSION_DURATION - (Date.now() - ts)) / 60000));

const MATERIALS = [
  { key: "coffee_g", label: "Çekirdek Kahve", unit: "g",    max: 200,  icon: "☕", accent: "#6B4226" },
  { key: "milk_ml",  label: "Süt",            unit: "ml",   max: 5000, icon: "🥛", accent: "#4A7FA5" },
  { key: "choc_g",   label: "Çikolata",       unit: "g",    max: 150,  icon: "🍫", accent: "#7B4F2E" },
  { key: "cups",     label: "Bardak",         unit: "adet", max: 70,   icon: "🥤", accent: "#4A7A55" },
];

const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --cream:      #FAF7F2;
    --cream-dark: #F2EDE4;
    --cream-mid:  #E8E0D4;
    --ink:        #2C2416;
    --ink-mid:    #6B5E4A;
    --ink-light:  #A8997E;
    --amber:      #C47D2B;
    --amber-light:#F5E6C8;
    --error:      #B94040;
    --error-light:#F9ECEC;
    --warn:       #B87820;
    --warn-light: #FBF0D8;
    --ok:         #3A6B45;
    --ok-light:   #E6F0E8;
    --border:     rgba(107,94,74,0.15);
    --border-mid: rgba(107,94,74,0.25);
    --shadow:     0 1px 3px rgba(44,36,22,0.08), 0 4px 12px rgba(44,36,22,0.05);
    --shadow-sm:  0 1px 2px rgba(44,36,22,0.06);
  }

  body { background: var(--cream); font-family: 'DM Sans', sans-serif; }

  .page {
    min-height: 100vh;
    background: var(--cream);
    padding: 0;
  }

  /* Header */
  .header {
    background: var(--ink);
    padding: 28px 48px 24px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-bottom: 3px solid var(--amber);
  }
  .header-title {
    font-family: 'DM Serif Display', serif;
    font-size: 28px;
    color: #FAF7F2;
    letter-spacing: -0.3px;
  }
  .header-sub {
    font-size: 12px;
    color: var(--ink-light);
    margin-top: 4px;
    font-weight: 300;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .header-badge {
    display: flex; align-items: center; gap: 8px;
    background: rgba(196,125,43,0.15);
    border: 1px solid rgba(196,125,43,0.3);
    border-radius: 20px;
    padding: 6px 14px;
    color: var(--amber);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
  }
  .header-badge:hover { background: rgba(196,125,43,0.25); }

  /* Tabs */
  .tabs {
    display: flex;
    border-bottom: 1px solid var(--border);
    background: var(--cream);
    padding: 0 48px;
  }
  .tab-btn {
    padding: 16px 24px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.3px;
    color: var(--ink-light);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
  }
  .tab-btn:hover { color: var(--ink); }
  .tab-btn.active {
    color: var(--ink);
    border-bottom-color: var(--amber);
  }

  /* Content */
  .content { padding: 40px 48px; max-width: 1000px; }

  /* Stock cards */
  .stock-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 40px;
  }
  .stock-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px 20px;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.2s;
  }
  .stock-card:hover { box-shadow: var(--shadow); }
  .stock-card.crit { border-color: rgba(185,64,64,0.3); background: var(--error-light); }
  .stock-card.warn { border-color: rgba(184,120,32,0.3); background: var(--warn-light); }
  .stock-card.ok   { border-color: var(--border); }

  .card-icon { font-size: 24px; margin-bottom: 12px; display: block; }
  .card-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 500;
    color: var(--ink-light);
    margin-bottom: 6px;
  }
  .card-value {
    font-family: 'DM Serif Display', serif;
    font-size: 32px;
    color: var(--ink);
    line-height: 1;
  }
  .card-value.crit { color: var(--error); }
  .card-value.warn { color: var(--warn); }
  .card-unit {
    font-size: 13px;
    color: var(--ink-mid);
    margin-left: 4px;
    font-weight: 300;
  }
  .card-threshold {
    font-size: 11px;
    color: var(--ink-light);
    margin-top: 8px;
  }
  .progress-wrap {
    margin-top: 14px;
    height: 4px;
    background: var(--cream-mid);
    border-radius: 2px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s cubic-bezier(0.4,0,0.2,1);
  }
  .progress-fill.crit { background: var(--error); }
  .progress-fill.warn { background: var(--warn); }
  .progress-fill.ok   { background: var(--ok); }

  /* Alerts */
  .alert-strip {
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
    font-size: 13px;
    font-weight: 400;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .alert-strip.crit { background: var(--error-light); color: var(--error); border: 1px solid rgba(185,64,64,0.2); }
  .alert-strip.warn { background: var(--warn-light);  color: var(--warn);  border: 1px solid rgba(184,120,32,0.2); }
  .alert-strip.ok   { background: var(--ok-light);    color: var(--ok);    border: 1px solid rgba(58,107,69,0.2); }

  /* Status pill */
  .status-row { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }
  .status-pill {
    font-size: 11px; font-weight: 500; letter-spacing: 0.6px;
    text-transform: uppercase; border-radius: 20px; padding: 5px 14px;
    border: 1px solid;
  }
  .status-pill.ok   { color: var(--ok);   background: var(--ok-light);   border-color: rgba(58,107,69,0.25); }
  .status-pill.warn { color: var(--warn); background: var(--warn-light);  border-color: rgba(184,120,32,0.25); }
  .status-pill.crit { color: var(--error); background: var(--error-light); border-color: rgba(185,64,64,0.25); }

  /* Section title */
  .section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 18px;
    color: var(--ink);
    margin-bottom: 8px;
  }
  .section-sub {
    font-size: 13px;
    color: var(--ink-light);
    margin-bottom: 24px;
    font-weight: 300;
    line-height: 1.6;
  }

  /* Divider */
  .divider { border: none; border-top: 1px solid var(--border); margin: 36px 0; }
  .divider-label {
    font-size: 11px; letter-spacing: 0.8px; text-transform: uppercase;
    color: var(--ink-light); font-weight: 500;
    display: flex; align-items: center; gap: 12px; margin: 36px 0 20px;
  }
  .divider-label::before, .divider-label::after {
    content: ''; flex: 1; border-top: 1px solid var(--border);
  }

  /* Form rows */
  .form-row {
    display: flex; align-items: center; gap: 16px; margin-bottom: 14px;
  }
  .form-label {
    font-size: 13px; font-weight: 500; color: var(--ink);
    min-width: 140px;
    display: flex; align-items: center; gap: 8px;
  }
  .form-label span { font-size: 16px; }
  .form-input-wrap { position: relative; flex: 1; }
  .form-input {
    width: 100%;
    padding: 10px 44px 10px 14px;
    border: 1px solid var(--border-mid);
    border-radius: 8px;
    background: #fff;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .form-input:focus {
    border-color: var(--amber);
    box-shadow: 0 0 0 3px rgba(196,125,43,0.12);
  }
  .form-input.input-error {
    border-color: var(--error) !important;
    box-shadow: 0 0 0 3px rgba(185,64,64,0.12) !important;
  }
  .input-hint {
    font-size: 11px;
    color: var(--error);
    margin-top: 3px;
    min-height: 14px;
  }
  .form-input[type="number"]::-webkit-inner-spin-button,
  .form-input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
  .form-input[type="number"] { -moz-appearance: textfield; }
  .form-unit {
    position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    font-size: 11px; color: var(--ink-light); font-weight: 500;
    pointer-events: none;
  }
  .form-note {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border-mid);
    border-radius: 8px;
    background: #fff;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    color: var(--ink);
    outline: none;
    margin-top: 4px;
    transition: border-color 0.2s;
  }
  .form-note:focus { border-color: var(--amber); box-shadow: 0 0 0 3px rgba(196,125,43,0.12); }

  /* Buttons */
  .btn-primary {
    padding: 11px 28px;
    background: var(--ink);
    color: var(--cream);
    border: none; border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px; font-weight: 500;
    letter-spacing: 0.4px;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
  }
  .btn-primary:hover  { background: var(--amber); }
  .btn-primary:active { transform: scale(0.98); }

  .btn-secondary {
    padding: 11px 28px;
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--border-mid);
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px; font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-secondary:hover { border-color: var(--amber); color: var(--amber); }

  .btn-ghost {
    padding: 7px 14px;
    background: transparent;
    color: var(--ink-mid);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px; font-weight: 400;
    cursor: pointer; transition: all 0.15s;
    display: flex; align-items: center; gap: 5px;
  }
  .btn-ghost:hover { border-color: var(--ink-mid); color: var(--ink); }

  /* Table */
  .tbl-wrap {
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    margin-bottom: 36px;
  }
  table { width: 100%; border-collapse: collapse; background: #fff; }
  thead tr { background: var(--cream-dark); }
  thead th {
    padding: 11px 14px;
    text-align: left;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.7px;
    text-transform: uppercase;
    color: var(--ink-mid);
    border-bottom: 1px solid var(--border);
  }
  tbody tr { border-bottom: 1px solid var(--border); transition: background 0.15s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--cream); }
  tbody td { padding: 10px 14px; font-size: 13px; color: var(--ink); }
  .td-muted { color: var(--ink-light); }
  .td-mono { font-variant-numeric: tabular-nums; }

  /* Empty state */
  .empty-row td { text-align: center; padding: 32px; color: var(--ink-light); font-size: 13px; }

  /* Toast */
  .toast {
    position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
    padding: 12px 24px; border-radius: 8px;
    font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500;
    box-shadow: 0 4px 20px rgba(44,36,22,0.2);
    z-index: 9999; animation: slideUp 0.3s ease;
    max-width: 90vw;
  }
  .toast.success { background: var(--ink); color: var(--cream); }
  .toast.error   { background: var(--error); color: #fff; }
  .toast.warning { background: var(--warn); color: #fff; }
  @keyframes slideUp { from { opacity:0; transform: translateX(-50%) translateY(12px); } to { opacity:1; transform: translateX(-50%) translateY(0); } }

  /* ── Login ekranı ────────────────────── */
  .login-overlay {
    min-height: 100vh;
    background: var(--cream);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .login-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: 0 4px 32px rgba(44,36,22,0.10);
    padding: 48px 44px 40px;
    width: 100%;
    max-width: 400px;
    text-align: center;
  }
  .login-icon {
    font-size: 40px;
    margin-bottom: 16px;
    display: block;
  }
  .login-title {
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    color: var(--ink);
    margin-bottom: 6px;
  }
  .login-sub {
    font-size: 13px;
    color: var(--ink-light);
    margin-bottom: 32px;
    font-weight: 300;
  }
  .login-field {
    position: relative;
    margin-bottom: 16px;
  }
  .login-input {
    width: 100%;
    padding: 13px 44px 13px 16px;
    border: 1px solid var(--border-mid);
    border-radius: 8px;
    background: var(--cream);
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    color: var(--ink);
    letter-spacing: 0.12em;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    text-align: center;
  }
  .login-input:focus {
    border-color: var(--amber);
    box-shadow: 0 0 0 3px rgba(196,125,43,0.12);
    background: #fff;
  }
  .login-input.shake {
    animation: shake 0.4s ease;
    border-color: var(--error);
    box-shadow: 0 0 0 3px rgba(185,64,64,0.12);
  }
  .login-toggle {
    position: absolute;
    right: 13px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    cursor: pointer;
    font-size: 15px;
    color: var(--ink-light);
    padding: 4px;
    line-height: 1;
  }
  .login-toggle:hover { color: var(--ink-mid); }
  .login-error {
    font-size: 12px;
    color: var(--error);
    margin-bottom: 14px;
    min-height: 18px;
    text-align: center;
  }
  .login-btn {
    width: 100%;
    padding: 13px;
    background: var(--ink);
    color: var(--cream);
    border: none;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.4px;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
  }
  .login-btn:hover   { background: var(--amber); }
  .login-btn:active  { transform: scale(0.98); }
  .login-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .login-hint {
    margin-top: 20px;
    font-size: 11px;
    color: var(--ink-light);
    letter-spacing: 0.3px;
  }
  @keyframes shake {
    0%,100% { transform: translateX(0); }
    20%     { transform: translateX(-8px); }
    40%     { transform: translateX(8px); }
    60%     { transform: translateX(-5px); }
    80%     { transform: translateX(5px); }
  }

  /* ── Home butonu ─────────────────────── */
  .btn-home {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    background: rgba(250,247,242,0.12);
    color: rgba(250,247,242,0.75);
    border: 1px solid rgba(250,247,242,0.18);
    border-radius: 6px;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
  }
  .btn-home:hover {
    background: rgba(250,247,242,0.2);
    color: #FAF7F2;
    border-color: rgba(250,247,242,0.35);
  }

  /* ── Oturum süresi ───────────────────── */
  .session-timer {
    font-size: 11px;
    color: rgba(250,247,242,0.4);
    letter-spacing: 0.3px;
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 14px;
  }
    display: flex; align-items: center; justify-content: center;
    padding: 60px; color: var(--ink-light); font-size: 13px; gap: 10px;
  }
  .spinner {
    width: 18px; height: 18px;
    border: 2px solid var(--cream-mid);
    border-top-color: var(--amber);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Log tabs */
  .log-tabs { display: flex; gap: 4px; margin-bottom: 20px; }
  .log-tab {
    padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500;
    border: 1px solid var(--border); background: #fff; color: var(--ink-mid);
    cursor: pointer; transition: all 0.15s;
  }
  .log-tab.active { background: var(--ink); color: var(--cream); border-color: var(--ink); }
`;

// ─────────────────────────────────────────────
// YARDIMCILAR
// ─────────────────────────────────────────────
const fmtDate = (v) => {
  if (!v) return "—";
  try { return new Date(v).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" }); }
  catch { return v; }
};
const fmtNum = (v, dec = 0) => {
  if (v === null || v === undefined) return "—";
  return typeof v === "number" ? (dec ? v.toFixed(dec) : String(Math.round(v))) : String(v);
};
const severity = (val, minVal) => {
  if (val <= minVal)      return "crit";
  if (val <= minVal * 2)  return "warn";
  return "ok";
};

// ─────────────────────────────────────────────
// ANA BİLEŞEN
// ─────────────────────────────────────────────
const StockManagement = () => {
  const [tab, setTab]           = useState(0);
  const [stockData, setStockData] = useState(null);
  const navigate = useNavigate();

  // ── Auth state ───────────────────────────
  // Oturum geri yükleme — sayfa yenilenirse 30dk boyunca giriş korunur.
  //
  // useState başlangıç fonksiyonu kullanılıyor: effect içinde setState
  // çağırmak fazladan bir render turu doğuruyor ve giriş ekranı bir kare
  // boyunca yanıp sönüyordu. Ayrıca eski kod startSessionTimer'ı
  // tanımlanmadan ÖNCE çağırıyordu — çalışıyordu ama kırılgandı.
  //
  // Başlangıç fonksiyonu yalnızca değer döndürür; ref'e yazmaz.
  // Render sırasında ref'e dokunmak React'in beklemediği bir davranış.
  const [restoredTs] = useState(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_KEY);
      if (!stored) return null;
      const { ts } = JSON.parse(stored);
      if (Date.now() - ts < SESSION_DURATION) return ts;
    } catch {
      // bozuk kayıt — aşağıda temizleniyor
    }
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  });

  const [authed, setAuthed]       = useState(restoredTs !== null);
  const [password, setPassword]   = useState("");
  const [showPw, setShowPw]       = useState(false);
  const [loginErr, setLoginErr]   = useState("");
  const [shaking, setShaking]     = useState(false);
  // Kalan süre baştan hesaplanır; startSessionTimer artık yalnızca
  // aralığı kurar, senkron setState yapmaz.
  const [sessionLeft, setSessionLeft] = useState(() => minutesLeft(restoredTs));
  const sessionTimer = useRef(null);
  const inputRef     = useRef(null);

  const startSessionTimer = (ts) => {
    if (sessionTimer.current) clearInterval(sessionTimer.current);
    sessionTimer.current = setInterval(() => {
      const left = SESSION_DURATION - (Date.now() - ts);
      if (left <= 0) {
        clearInterval(sessionTimer.current);
        sessionStorage.removeItem(SESSION_KEY);
        setAuthed(false);
        setPassword("");
      } else {
        setSessionLeft(Math.ceil(left / 60000)); // dakika
      }
    }, 10000);
  };

  // Geri yüklenen oturumun geri sayımını başlat
  useEffect(() => {
    if (restoredTs !== null) startSessionTimer(restoredTs);
  }, [restoredTs]);

  useEffect(() => () => { if (sessionTimer.current) clearInterval(sessionTimer.current); }, []);

  const handleLogin = () => {
    if (password === ADMIN_PASSWORD) {
      const ts = Date.now();
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ts }));
      setAuthed(true);
      setLoginErr("");
      setPassword("");
      setSessionLeft(minutesLeft(ts));
      startSessionTimer(ts);
    } else {
      setLoginErr("Hatalı parola. Tekrar deneyin.");
      setShaking(true);
      setTimeout(() => setShaking(false), 500);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    if (sessionTimer.current) clearInterval(sessionTimer.current);
    setAuthed(false);
    setPassword("");
    setLoginErr("");
  };

  // ── Diğer state'ler ──────────────────────
  const [loading, setLoading]   = useState(true);

  const [refillValues, setRefillValues] = useState({ coffee_g: "", milk_ml: "", choc_g: "", cups: "" });
  const [threshValues, setThreshValues] = useState({ coffee_g: "", milk_ml: "", choc_g: "", cups: "" });
  const [refillNote, setRefillNote]     = useState("");

  const [orderLogs, setOrderLogs]   = useState([]);
  const [refillLogs, setRefillLogs] = useState([]);
  const [syrups, setSyrups] = useState([]);
  const [syrupEdit, setSyrupEdit] = useState({});   // channel → { ml, threshold }
  const [logsLoading, setLogsLoading] = useState(false);
  const [logTab, setLogTab]         = useState(0);

  const [toast, setToast] = useState(null);
  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  // ── Veri çekme ───────────────────────────
  const fetchStock = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(ENDPOINTS.stockStatus, { timeout: 5000 });
      try {
        const sy = await api.get(ENDPOINTS.stockSyrup, { timeout: 5000 });
        const channels = sy.data?.channels ?? [];
        setSyrups(channels);
        if (channels.length === 0) {
          console.warn("[Stock] /stock/syrup boş döndü — şurup bölümleri gizli kalır.");
        }
      } catch (e) {
        // Şurup ucu yoksa (eski backend → 404) veya erişilemezse, şurup
        // bölümleri gizlenir. Sessizce yutmak yerine sebebi konsola yaz —
        // "görünmüyor" sorununun teşhisini kolaylaştırır.
        setSyrups([]);
        console.warn(
          "[Stock] /stock/syrup alınamadı (%s) — şurup yenileme/eşik bölümleri "
          + "gösterilmeyecek. Backend güncel mi ve bu ucu sunuyor mu kontrol edin.",
          e?.response?.status || e?.message || "bilinmeyen hata"
        );
      }
      setStockData(res.data);
      const t = res.data?.thresholds || {};
      setThreshValues({
        coffee_g: t.coffee_g ?? "", milk_ml: t.milk_ml ?? "",
        choc_g: t.choc_g ?? "", cups: t.cups ?? "",
      });
    } catch (e) {
      showToast("Stok verisi alınamadı: " + (e?.message || ""), "error");
    } finally { setLoading(false); }
  }, []);

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const [oRes, rRes] = await Promise.all([
        api.get(ENDPOINTS.stockOrderLogs(30)),
        api.get(ENDPOINTS.stockRefillLogs(20)),
      ]);
      setOrderLogs(oRes.data || []);
      setRefillLogs(rRes.data || []);
    } catch (e) {
      showToast("Loglar alınamadı: " + (e?.message || ""), "error");
    } finally { setLogsLoading(false); }
  }, []);

  // Veri çekme effect'leri. setState çağrısı senkron effect gövdesinde
  // değil, await sonrası geri çağrıda olduğu için zincirleme render
  // oluşmaz; kural yine de uyarı verdiğinden burada bilinçli olarak
  // susturuluyor.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => { fetchStock(); }, [fetchStock]);
  useEffect(() => { if (tab === 2) fetchLogs(); }, [tab, fetchLogs]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // ── İşlemler ─────────────────────────────
  // Yazma işlemleri backend tarafında X-Admin-Token ile korunuyor
  const axiosCfg = adminConfig();

  // Sadece tam sayı (integer ≥ 0) girişine izin ver
  const ALLOWED_KEYS = new Set([
    "Backspace","Delete","Tab","Enter","Escape",
    "ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Home","End",
  ]);
  const onIntegerKeyDown = (e) => {
    if (ALLOWED_KEYS.has(e.key) || e.ctrlKey || e.metaKey) return;
    if (!/^[0-9]$/.test(e.key)) e.preventDefault();
  };

  // Yapıştırma dahil her girişi temizle — sadece rakam bırak
  const toDigits = (val) => val.replace(/[^0-9]/g, "");

  // Geçerli integer mi?
  const isValidInt = (val) => val !== "" && /^[0-9]+$/.test(val);

  const handleRefill = async () => {
    const payload = {};
    const invalid = [];
    MATERIALS.forEach(({ key, label }) => {
      const v = refillValues[key];
      if (v === "") return;
      if (!isValidInt(v)) { invalid.push(label); return; }
      payload[key] = parseInt(v, 10);
    });
    if (invalid.length) {
      showToast(`Geçersiz değer: ${invalid.join(", ")} — sadece tam sayı girin.`, "warning");
      return;
    }
    if (!Object.keys(payload).length) {
      showToast("En az bir malzeme miktarı girin.", "warning"); return;
    }
    // Değişiklik özetiyle onay al. Bu uç $set kullanıyor: 700 yerine
    // yanlışlıkla 70 yazmak stoğun %90'ını sessizce siler. Ne olacağını
    // önceden göstermek bu hatayı önler.
    const summary = MATERIALS
      .filter(({ key }) => payload[key] !== undefined)
      .map(({ key, label, unit }) => {
        const before = stockData?.stock?.[key];
        const after = payload[key];
        const arrow = before != null ? `${fmtNum(before)} → ${after}` : `${after}`;
        const warn = before != null && after < before ? "  ⚠ AZALIYOR" : "";
        return `  ${label}: ${arrow} ${unit}${warn}`;
      })
      .join("\n");

    const confirmed = window.confirm(
      `Stok değerleri aşağıdaki gibi DEĞİŞTİRİLECEK:\n\n${summary}\n\n` +
      "Girilen değerler mevcut miktara eklenmez, yerine yazılır.\n\nOnaylıyor musunuz?"
    );
    if (!confirmed) return;

    payload.note = refillNote;
    try {
      await api.put(ENDPOINTS.stockRefill, payload, axiosCfg);
      showToast("Stok başarıyla güncellendi.");
      setRefillValues({ coffee_g: "", milk_ml: "", choc_g: "", cups: "" });
      setRefillNote("");
      fetchStock();
    } catch (e) {
      const msg = e?.response?.status === 401
        ? "Yönetici token'ı geçersiz veya eksik. frontend/.env içindeki "
          + "VITE_ADMIN_TOKEN, backend .env içindeki ADMIN_TOKEN ile aynı olmalı."
        : (e?.response?.data?.detail || e?.message || "Bilinmeyen hata");
      showToast("Güncelleme hatası: " + msg, "error");
      console.error("[Refill] PUT /stock/refill →", e?.response?.status, msg);
    }
  };

  const handleThresholds = async () => {
    const payload = {};
    const invalid = [];
    MATERIALS.forEach(({ key, label }) => {
      const v = threshValues[key];
      if (v === "") return;
      if (!isValidInt(v)) { invalid.push(label); return; }
      payload[key] = parseInt(v, 10);
    });
    if (invalid.length) {
      showToast(`Geçersiz değer: ${invalid.join(", ")} — sadece tam sayı girin.`, "warning");
      return;
    }
    if (!Object.keys(payload).length) {
      showToast("En az bir eşik değeri girin.", "warning"); return;
    }
    try {
      await api.put(ENDPOINTS.stockThresholds, payload, axiosCfg);
      showToast("Eşik değerleri kaydedildi.");
      fetchStock();
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Bilinmeyen hata";
      showToast("Eşik hatası: " + msg, "error");
      console.error("[Thresholds] PUT /stock/thresholds →", e?.response?.status, msg);
    }
  };

  // ── Render yardımcıları ───────────────────
  const saveSyrup = async (channel) => {
    const edit = syrupEdit[channel] || {};
    const payload = {};
    if (edit.ml !== undefined && edit.ml !== "") payload.ml = Number(edit.ml);
    if (edit.threshold !== undefined && edit.threshold !== "") payload.threshold = Number(edit.threshold);
    if (Object.keys(payload).length === 0) return;

    const ch = syrups.find((x) => x.channel === channel);
    const confirmed = window.confirm(
      `${ch?.name ?? "Kanal " + channel} güncellenecek:\n\n` +
      (payload.ml !== undefined ? `  Miktar: ${fmtNum(ch?.ml)} → ${payload.ml} ml\n` : "") +
      (payload.threshold !== undefined ? `  Eşik: ${fmtNum(ch?.threshold)} → ${payload.threshold} ml\n` : "") +
      "\nMiktar mevcut değere eklenmez, yerine yazılır.\n\nOnaylıyor musunuz?"
    );
    if (!confirmed) return;

    try {
      await api.put(ENDPOINTS.stockSyrupRefill(channel), payload, axiosCfg);
      showToast(`${ch?.name ?? "Kanal " + channel} güncellendi.`, "success");
      setSyrupEdit((prev) => ({ ...prev, [channel]: {} }));
      fetchStock();
    } catch (e) {
      const msg = e?.response?.status === 401
        ? "Yönetici token'ı geçersiz veya eksik."
        : (e?.response?.data?.detail || e?.message || "Bilinmeyen hata");
      showToast("Şurup güncelleme hatası: " + msg, "error");
    }
  };

  const stock  = stockData?.stock      || {};
  const thresh = stockData?.thresholds || {};
  const alerts = stockData?.alerts     || [];
  const overall = stockData?.status?.overall || "ok";

  // Render sırasında bileşen TANIMLAMAYIN: her render'da yeni bir bileşen
  // tipi doğar, React eskisini söküp yenisini takar ve durum sıfırlanır.
  // Düz bir JSX ifadesi bu sorunu ortadan kaldırır.
  const overallPill = (
    <span className={`status-pill ${overall}`}>
      {overall === "ok" ? "✓ Normal" : overall === "warning" ? "⚠ Uyarı" : "⛔ Kritik"}
    </span>
  );

  // ── SEKME: Güncel stok ───────────────────
  const stockTabContent = (
    <>
      <div className="status-row">
        {overallPill}
        <button className="btn-ghost" onClick={fetchStock}>↻ Yenile</button>
      </div>

      {alerts.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          {alerts.map((a, i) => (
            <div key={i} className={`alert-strip ${a.type === "critical" ? "crit" : "warn"}`}>
              <span>{a.type === "critical" ? "⛔" : "⚠"}</span>
              <span>{a.message}</span>
            </div>
          ))}
        </div>
      )}

      {alerts.length === 0 && (
        <div className="alert-strip ok" style={{ marginBottom: 28 }}>
          <span>✓</span>
          <span>Tüm malzeme seviyeleri normal.</span>
        </div>
      )}

      <div className="stock-grid">
        {MATERIALS.map((m) => {
          const val   = Number(stock[m.key] ?? 0);
          const minV  = Number(thresh[m.key] ?? 50);
          const sev   = severity(val, minV);
          const pct   = Math.min(100, Math.max(0, (val / m.max) * 100));
          return (
            <div key={m.key} className={`stock-card ${sev}`}>
              <span className="card-icon">{m.icon}</span>
              <div className="card-label">{m.label}</div>
              <div className={`card-value ${sev}`}>
                {fmtNum(val)}
                <span className="card-unit">{m.unit}</span>
              </div>
              <div className="card-threshold">Eşik: {fmtNum(minV)} {m.unit}</div>
              <div className="progress-wrap">
                <div className={`progress-fill ${sev}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {syrups.length > 0 && (
        <>
          <h2 className="section-title" style={{ marginTop: 36 }}>Şurup Kanalları</h2>
          <p className="section-sub">
            Eşiğin altındaki kanalları kullanan içecekler sipariş edilemez
            (dozaj yarıda kesilmesin diye). Düzenleme için “Yenileme &amp; Eşikler” sekmesine geçin.
          </p>
          <div className="stock-grid">
            {syrups.map((sy) => {
              const low = Number(sy.ml) < Number(sy.threshold);
              const pct = Math.min(100, Math.max(0, (Number(sy.ml) / Number(sy.capacity || 1000)) * 100));
              return (
                <div key={sy.channel} className={`stock-card ${low ? "critical" : "ok"}`}>
                  <div className="card-label">{sy.name || `Kanal ${sy.channel}`}</div>
                  <div className={`card-value ${low ? "critical" : "ok"}`}>
                    {fmtNum(sy.ml)}<span className="card-unit">ml</span>
                  </div>
                  <div className="card-threshold">
                    Eşik: {fmtNum(sy.threshold)} ml {low && "· DÜŞÜK"}
                  </div>
                  <div className="progress-wrap">
                    <div className={`progress-fill ${low ? "critical" : "ok"}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );

  // ── SEKME: Yenileme ──────────────────────
  const refillTabContent = (
    <>
      <div>
        <h2 className="section-title">Stok Yenileme</h2>
        <p className="section-sub">
          Girilen değer mevcut miktara <strong>eklenmez</strong>, onun
          <strong> yerine yazılır</strong>. Deponun yeni toplam miktarını girin.<br />
          Boş bırakılan alanlar değiştirilmez.
        </p>
        {MATERIALS.map((m) => (
          <div key={m.key} className="form-row">
            {/* Mevcut değer burada gösterilmezse personel "Güncel Stok"
                sekmesine gidip geri dönmek zorunda kalıyordu; üstelik
                değer yazılmadan önce ne olduğunu görmeden yazmak,
                $set semantiğinde sessiz stok kaybına yol açabiliyor. */}
            <label className="form-label">
              <span>{m.icon}</span> {m.label}
              {stockData?.stock?.[m.key] != null && (
                <span className="td-muted" style={{ marginLeft: 8, fontSize: 12 }}>
                  şu an {fmtNum(stockData.stock[m.key])} {m.unit}
                </span>
              )}
            </label>
            <div className="form-input-wrap">
              <input
                className={`form-input${refillValues[m.key] !== "" && !isValidInt(refillValues[m.key]) ? " input-error" : ""}`}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="Tam sayı girin"
                value={refillValues[m.key]}
                onChange={(e) => setRefillValues((p) => ({ ...p, [m.key]: toDigits(e.target.value) }))}
                onKeyDown={onIntegerKeyDown}
                autoComplete="off"
              />
              <span className="form-unit">{m.unit}</span>
            </div>
          </div>
        ))}

        <div style={{ marginBottom: 20 }}>
          <label className="form-label" style={{ marginBottom: 6, display: "block" }}>Not</label>
          <input
            className="form-note" type="text"
            placeholder="Örn: Sabah dolumu, 3. lot"
            value={refillNote}
            onChange={(e) => setRefillNote(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>
        <button className="btn-primary" onClick={handleRefill}>Stoku Güncelle</button>
      </div>

      <div className="divider-label">Uyarı Eşikleri</div>

      <div>
        <p className="section-sub">
          Bu değerlerin altına düşüldüğünde ilgili içecekler otomatik olarak devre dışı bırakılır.
        </p>
        {MATERIALS.map((m) => (
          <div key={m.key} className="form-row">
            <label className="form-label"><span>{m.icon}</span> {m.label}</label>
            <div className="form-input-wrap">
              <input
                className={`form-input${threshValues[m.key] !== "" && !isValidInt(threshValues[m.key]) ? " input-error" : ""}`}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="Tam sayı girin"
                value={threshValues[m.key]}
                onChange={(e) => setThreshValues((p) => ({ ...p, [m.key]: toDigits(e.target.value) }))}
                onKeyDown={onIntegerKeyDown}
                autoComplete="off"
              />
              <span className="form-unit">{m.unit}</span>
            </div>
          </div>
        ))}
        <button className="btn-secondary" onClick={handleThresholds}>Eşikleri Kaydet</button>
      </div>

      {syrups.length > 0 && (
        <div style={{ marginTop: 40 }}>
          <h2 className="section-title">Şurup Kanalları — Miktar &amp; Eşik</h2>
          <p className="section-sub">
            Her kanal için miktar (ml) ve eşik ayrı ayrı güncellenir.
            Girilen miktar mevcut değere <strong>eklenmez, yerine yazılır</strong>.
            Boş bırakılan alanlara dokunulmaz.
          </p>
          {syrups.map((sy) => {
            const edit = syrupEdit[sy.channel] || {};
            const low = Number(sy.ml) < Number(sy.threshold);
            return (
              <div key={sy.channel} className="form-row" style={{ alignItems: "flex-end", gap: 12 }}>
                <label className="form-label" style={{ minWidth: 130 }}>
                  {sy.name || `Kanal ${sy.channel}`}
                  <span className="td-muted" style={{ display: "block", fontSize: 11 }}>
                    şu an {fmtNum(sy.ml)} ml {low && "· DÜŞÜK"}
                  </span>
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, opacity: 0.6 }}>Miktar (ml)</span>
                  <input
                    className="form-input" type="number" placeholder={fmtNum(sy.ml)}
                    value={edit.ml ?? ""}
                    onChange={(e) => setSyrupEdit((prev) => ({ ...prev, [sy.channel]: { ...edit, ml: e.target.value } }))}
                    style={{ width: 110 }}
                  />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, opacity: 0.6 }}>Eşik (ml)</span>
                  <input
                    className="form-input" type="number" placeholder={fmtNum(sy.threshold)}
                    value={edit.threshold ?? ""}
                    onChange={(e) => setSyrupEdit((prev) => ({ ...prev, [sy.channel]: { ...edit, threshold: e.target.value } }))}
                    style={{ width: 110 }}
                  />
                </div>
                <button className="btn-ghost" onClick={() => saveSyrup(sy.channel)}
                        style={{ marginBottom: 2 }}>Kaydet</button>
              </div>
            );
          })}
        </div>
      )}
    </>
  );

  // ── SEKME: Loglar ────────────────────────
  const logsTabContent = (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div className="log-tabs">
          <button className={`log-tab ${logTab === 0 ? "active" : ""}`} onClick={() => setLogTab(0)}>
            Sipariş Logları
          </button>
          <button className={`log-tab ${logTab === 1 ? "active" : ""}`} onClick={() => setLogTab(1)}>
            Dolum Logları
          </button>
        </div>
        <button className="btn-ghost" onClick={fetchLogs}>↻ Yenile</button>
      </div>

      {logsLoading ? (
        <div className="loader"><div className="spinner" /> Yükleniyor...</div>
      ) : logTab === 0 ? (
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Tarih</th>
                <th>İçecek</th>
                <th>Kahve</th>
                <th>Süt</th>
                <th>Çikolata</th>
                <th>Bardak</th>
              </tr>
            </thead>
            <tbody>
              {orderLogs.length === 0 ? (
                <tr className="empty-row"><td colSpan={6}>Henüz sipariş kaydı yok</td></tr>
              ) : orderLogs.map((log, i) => (
                <tr key={i}>
                  <td className="td-muted">{fmtDate(log.ordered_at)}</td>
                  <td>{log.recipe_name || `Btn ${log.button_number}`}</td>
                  <td className="td-mono">{fmtNum(log.coffee_g)} g</td>
                  <td className="td-mono">{fmtNum(log.milk_ml)} ml</td>
                  <td className="td-mono">{fmtNum(log.choc_g)} g</td>
                  <td className="td-mono">{log.cups ?? 1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Tarih</th>
                <th>Kahve</th>
                <th>Süt</th>
                <th>Çikolata</th>
                <th>Bardak</th>
                <th>Not</th>
              </tr>
            </thead>
            <tbody>
              {refillLogs.length === 0 ? (
                <tr className="empty-row"><td colSpan={6}>Henüz dolum kaydı yok</td></tr>
              ) : refillLogs.map((log, i) => (
                <tr key={i}>
                  <td className="td-muted">{fmtDate(log.refilled_at)}</td>
                  <td className="td-mono">{log.refilled?.coffee_g != null ? `${fmtNum(log.refilled.coffee_g)} g` : "—"}</td>
                  <td className="td-mono">{log.refilled?.milk_ml  != null ? `${fmtNum(log.refilled.milk_ml)} ml`  : "—"}</td>
                  <td className="td-mono">{log.refilled?.choc_g   != null ? `${fmtNum(log.refilled.choc_g)} g`   : "—"}</td>
                  <td className="td-mono">{log.refilled?.cups     != null ? `${fmtNum(log.refilled.cups)} adet`  : "—"}</td>
                  <td className="td-muted">{log.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  // ── Login ekranı (auth değilse) ──────────
  if (!authed) {
    return (
      <>
        <style>{css}</style>
        <div className="login-overlay">
          <div className="login-card">
            <span className="login-icon">🔐</span>
            <div className="login-title">Yönetim Paneli</div>
            <p className="login-sub">Stok yönetimine erişmek için parolayı girin.</p>

            <div className="login-field">
              <input
                ref={inputRef}
                className={`login-input ${shaking ? "shake" : ""}`}
                type={showPw ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setLoginErr(""); }}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                autoFocus
              />
              <button className="login-toggle" tabIndex={-1}
                onClick={() => setShowPw((p) => !p)}>
                {showPw ? "🙈" : "👁"}
              </button>
            </div>

            <div className="login-error">{loginErr}</div>

            <button className="login-btn" onClick={handleLogin} disabled={!password}>
              Giriş Yap
            </button>

            <p className="login-hint">Oturum 30 dakika sonra otomatik sona erer.</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{css}</style>
      <div className="page">

        {/* Header */}
        <div className="header">
          <div>
            <div className="header-title">Stok Yönetimi</div>
            <div className="header-sub">WMF Coffee Service — Malzeme Takip Paneli</div>
          </div>

          <div className="header-right">
            {/* Oturum süresi */}
            {sessionLeft > 0 && (
              <span className="session-timer">⏱ {sessionLeft} dk</span>
            )}

            {/* Stok durum rozeti */}
            {!loading && stockData && (
              <div className="header-badge" style={{
                background: overall === "ok" ? "rgba(58,107,69,0.15)" : overall === "warning" ? "rgba(184,120,32,0.15)" : "rgba(185,64,64,0.15)",
                borderColor: overall === "ok" ? "rgba(58,107,69,0.3)" : overall === "warning" ? "rgba(184,120,32,0.3)" : "rgba(185,64,64,0.3)",
                color: overall === "ok" ? "var(--ok)" : overall === "warning" ? "var(--warn)" : "var(--error)",
              }}>
                {overall === "ok" ? "✓ Stok Normal" : overall === "warning" ? "⚠ Uyarı" : "⛔ Kritik Seviye"}
              </div>
            )}

            {/* Ana sayfa */}
            <button className="btn-home" onClick={() => navigate("/")}>
              ← Ana Sayfa
            </button>

            {/* Çıkış */}
            <button className="btn-home" onClick={handleLogout}
              style={{ borderColor: "rgba(185,64,64,0.3)", color: "rgba(249,236,236,0.75)" }}>
              Çıkış
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          {["Güncel Stok", "Yenileme & Eşikler", "Geçmiş Loglar"].map((t, i) => (
            <button key={i} className={`tab-btn ${tab === i ? "active" : ""}`} onClick={() => setTab(i)}>{t}</button>
          ))}
        </div>

        {/* Content */}
        <div className="content">
          {loading ? (
            <div className="loader"><div className="spinner" /> Yükleniyor...</div>
          ) : (
            <>
              {tab === 0 && stockTabContent}
              {tab === 1 && refillTabContent}
              {tab === 2 && logsTabContent}
            </>
          )}
        </div>

      </div>

      {/* Toast */}
      {toast && (
        <div className={`toast ${toast.type}`}>{toast.msg}</div>
      )}
    </>
  );
};

export default StockManagement;
