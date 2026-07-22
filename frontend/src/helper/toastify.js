import { toast } from "react-toastify";
import { palette, MONO } from "../theme";

/**
 * toastify.js — bildirim yardımcısı
 *
 * DEĞİŞENLER:
 *   • Koyu tema renkleri (#2e2720 / #DEC39B) açık temaya taşındı
 *   • Metin mono yazı tipiyle — makinenin sesi
 *   • Dokunmatik için biraz daha büyük ve daha kısa süreli
 */

const base = {
  position: "top-center",
  autoClose: 2200,
  hideProgressBar: false,
  closeOnClick: true,
  pauseOnHover: false,
  draggable: false,
  style: {
    background: palette.paper,
    color: palette.ink,
    border: `1px solid ${palette.rule}`,
    borderRadius: 3,
    fontFamily: MONO,
    fontSize: 14,
    minHeight: 60,
    boxShadow: "0 10px 28px rgba(23, 22, 15, 0.18)",
  },
  progressStyle: { background: palette.ink },
};

const accented = (color) => ({
  ...base,
  style: { ...base.style, borderLeft: `4px solid ${color}` },
  progressStyle: { background: color },
});

export const showToast = {
  addToCart: (name) => toast.success(`${name} sepete eklendi`, { ...accented(palette.green), icon: "🛒" }),

  removeFromCart: (name) => toast.info(`${name} çıkarıldı`, { ...accented(palette.ink2), icon: "🗑️" }),

  success: (message) => toast.success(message, { ...accented(palette.green), icon: "✅" }),

  error: (message) => toast.error(message, { ...accented(palette.red), icon: "⛔" }),

  warning: (message) => toast.warning(message, { ...accented(palette.amber), icon: "⚠️" }),

  info: (message) => toast.info(message, { ...accented(palette.ink2), icon: "ℹ️" }),
};
