/**
 * theme.js — açık tema
 *
 * Palet kont_coffee referansından alındı. Renkler ambalaj
 * fotoğraflarından türetilmiş; ürün görselleri bu zemine dikişsiz oturur.
 *
 * NEDEN THEME:
 *   Önceki sürümde renkler yüzlerce yerde hex literal olarak gömülüydü
 *   (#2e2720, #DEC39B, #454039, #E7D9CF...). Tema değiştirmek her
 *   dosyayı tek tek düzenlemek demekti. Artık tek kaynak burası;
 *   açık/koyu geçişi veya marka rengi değişimi tek dosyadan yapılır.
 *
 * TİPOGRAFİ — iki ses:
 *   Anton + Inter Tight → insana hitap eden her şey (ürün adı, başlık)
 *   JetBrains Mono      → makinenin ürettiği her şey (durum, kod, sayı)
 *   Bir metin mono ise onu makine üretmiştir. Bu ayrımı koruyun.
 */

import { createTheme } from "@mui/material/styles";

/* ─────────────────────────────────────────────
   HAM PALET
   Bileşenlerden doğrudan kullanmak yerine aşağıdaki
   theme.palette.* yollarını tercih edin.
   ───────────────────────────────────────────── */
export const palette = {
  paper:   "#E7DFD4",   // kart zemini — hot_cup/ice_cup fotoğraflarının arka planıyla BİREBİR aynı
  sand:    "#D5CCB9",   // sayfa zemini
  ink:     "#17160F",   // ana metin / koyu butonlar
  ink2:    "#5C574A",   // ikincil metin
  red:     "#E5352A",   // birincil eylem, soğuk aksan, hata
  lime:    "#D9DA96",   // sıcak aksan
  machine: "#15140D",   // makine tarafı paneller
  rule:    "rgba(23, 22, 15, 0.14)",
  green:   "#3F7A4B",   // hazır / başarılı
  amber:   "#B26B00",   // uyarı (açık zeminde okunur ton)
};

const DISPLAY = '"Anton", "Impact", "Arial Narrow", sans-serif';
const BODY    = '"Inter Tight", ui-sans-serif, system-ui, "Segoe UI", sans-serif';
export const MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace';

/* Dokunmatik ekran için minimum hedef boyutu.
   40px'lik butonlar parmakla ıskalanıyordu. */
export const TOUCH_MIN = 56;

const theme = createTheme({
  palette: {
    mode: "light",
    primary:   { main: palette.red,  contrastText: "#FFFFFF" },
    secondary: { main: palette.ink,  contrastText: palette.paper },
    error:     { main: palette.red },
    warning:   { main: palette.amber },
    success:   { main: palette.green },
    background: {
      default: palette.sand,
      paper:   palette.paper,
    },
    text: {
      primary:   palette.ink,
      secondary: palette.ink2,
    },
    divider: palette.rule,
  },

  shape: { borderRadius: 3 },

  typography: {
    fontFamily: BODY,
    fontSize: 16,

    // Ürün adları ve başlıklar
    h1: { fontFamily: DISPLAY, fontSize: "clamp(30px, 5vw, 46px)", lineHeight: 0.95 },
    h2: { fontFamily: DISPLAY, fontSize: "clamp(26px, 4vw, 36px)", lineHeight: 1 },
    h3: { fontFamily: DISPLAY, fontSize: 24, lineHeight: 1.05 },
    h4: { fontFamily: DISPLAY, fontSize: 20, lineHeight: 1.05 },

    button: { fontFamily: DISPLAY, letterSpacing: "0.03em", textTransform: "none" },

    // Makinenin sesi — durum rozetleri, kodlar
    overline: {
      fontFamily: MONO,
      fontSize: 11,
      letterSpacing: "0.12em",
      textTransform: "uppercase",
      lineHeight: 1.6,
    },
    caption: { fontSize: 12, color: palette.ink2 },
  },

  components: {
    /* Kiosk: metin seçimi ve dokunma parlaması kapalı,
       hedefler büyük. */
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          WebkitTapHighlightColor: "transparent",
          overscrollBehavior: "none",
        },
      },
    },

    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: TOUCH_MIN,
          borderRadius: 2,
          fontSize: 18,
          paddingInline: 22,
          "&.Mui-disabled": { opacity: 0.45 },
        },
        containedPrimary: {
          "&:hover": { filter: "brightness(1.08)", backgroundColor: palette.red },
        },
        containedSecondary: {
          "&:hover": { filter: "brightness(1.35)", backgroundColor: palette.ink },
        },
      },
    },

    MuiIconButton: {
      styleOverrides: {
        root: { minWidth: 48, minHeight: 48 },
      },
    },

    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: { fontFamily: MONO, fontSize: 11, letterSpacing: "0.06em" },
      },
    },

    MuiModal: {
      styleOverrides: {
        root: { "& :focus-visible": { outline: `3px solid ${palette.red}`, outlineOffset: 2 } },
      },
    },
  },
});

export default theme;
