import { useEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Modal, Typography } from "@mui/material";

import CupFill from "../CupFill";
import { palette } from "../../theme";

/**
 * PreparingCoffee — sipariş hazırlanma ekranı
 *
 * TASARIM KARARI:
 *   Ekranda saniye sayacı ve robot günlüğü YOK. İlerleme yalnızca
 *   ürünün kendi görseli üzerindeki dolum ile anlatılır. Müşteri
 *   sayı okumak zorunda kalmadan nerede olduğunu görür.
 *
 * DEĞİŞENLER:
 *   • Bileşen Home.jsx içinde YORUM SATIRINDAYDI — sipariş verildikten
 *     sonra kullanıcı hiçbir geri bildirim görmüyordu. Geri açıldı.
 *   • Önceden yalnızca 3 durum vardı (hazırlanıyor / hazır / hata).
 *     Backend zaten 8 ayrı faz üretiyor; hepsi gösteriliyor.
 *   • Açık temaya taşındı, Lottie yerine dolum göstergesi kullanılıyor.
 *
 * FAZ → İLERLEME EŞLEMESİ:
 *   Şimdilik burada tutuluyor. Aşama 2'de backend her fazın etiketini
 *   ve yüzdesini kendisi döndürecek; böylece akış değiştiğinde arayüz
 *   ile backend birbirinden ayrışmayacak.
 *
 * TIMER FAZI HAKKINDA:
 *   Backend "timer_38s" gibi bir faz adı gönderiyor — süre adın içinde.
 *   Bu süreyi ekranda göstermiyoruz, yalnızca dolumu o süre boyunca
 *   yumuşak ilerletmek için kullanıyoruz. Backend'den yeni bir faz
 *   gelirse animasyon anında ona uyar; tek doğruluk kaynağı backend.
 */

/* ─────────────────────────────────────────────
   FAZ TANIMLARI
   ───────────────────────────────────────────── */

// Sipariş tipine göre bazı fazlar hiç gelmez (buzsuz siparişte
// wait_di9_ice yoktur). Dolum o fazları atlar; sıçrama beklenen
// davranıştır, eksik faz değil.
const PHASES = {
  created:              { pct: 4,   tr: "Sipariş alındı",              en: "Order received" },
  set_sysvars:          { pct: 6,   tr: "Hazırlık",                    en: "Getting ready" },
  set_do0_true:         { pct: 10,  tr: "Bardak hazırlanıyor",         en: "Preparing the cup" },
  wait_di9_ice:         { pct: 18,  tr: "Buz ekleniyor",               en: "Adding ice" },
  wait_di8_syrup:       { pct: 26,  tr: "Şurup istasyonuna gidiliyor", en: "Heading to the syrup station" },
  syrup_dispense:       { pct: 32,  tr: "Şurup ekleniyor",             en: "Adding syrup" },
  set_do7_true:         { pct: 38,  tr: "Kahve makinesine taşınıyor",  en: "Moving to the machine" },
  wait_di1_robot_ready: { pct: 42,  tr: "Robot bardağı yerleştiriyor", en: "Robot is placing the cup" },
  coffee_task_start:    { pct: 45,  tr: "Demleme başlıyor",            en: "Brewing starts" },
  // timer_* fazı 45 → 82 aralığında yumuşak ilerler
  set_do2_true:         { pct: 85,  tr: "İçecek hazır",                en: "Drink is ready" },
  wait_di3_robot_done:  { pct: 93,  tr: "Robot içeceğinizi getiriyor", en: "Robot is bringing your drink" },
  robot_delivered:      { pct: 100, tr: "Afiyet olsun",                en: "Enjoy" },
  finalizing:           { pct: 100, tr: "Afiyet olsun",                en: "Enjoy" },
  done:                 { pct: 100, tr: "Afiyet olsun",                en: "Enjoy" },
};

const TIMER_FROM = 45;
const TIMER_TO   = 82;

const FALLBACK = {
  tr: "Hazırlanıyor",
  en: "Preparing",
};

/** "timer_38s" → 38 ; diğer fazlarda null */
const timerSeconds = (phase) => {
  const match = /^timer_(\d+)s$/.exec(String(phase ?? ""));
  return match ? Number(match[1]) : null;
};

/* ─────────────────────────────────────────────
   BİLEŞEN
   ───────────────────────────────────────────── */

const PreparingCoffee = ({
  open,
  handleClose,
  phase,
  status,
  rcpState,
  error,
  /** hazırlanan ürün — görsel ve ad için */
  item,
  language = "TR",
  /** kaçıncı içecek / toplam (çoklu siparişte) */
  currentIndex = 0,
  totalItems = 1,
}) => {
  const lang = language === "EN" ? "en" : "tr";

  const isError = status === "error" || status === "timeout";
  const isReady =
    !isError &&
    (status === "done" || phase === "robot_delivered" || rcpState === 9 || rcpState === -9);

  /* ── İlerleme yüzdesi ─────────────────────── */
  const [timerPct, setTimerPct] = useState(TIMER_FROM);
  const rafRef = useRef(null);

  const seconds = timerSeconds(phase);

  // Timer fazındayken dolumu süre boyunca yumuşak ilerlet.
  // Sayı ekranda gösterilmez; yalnızca animasyon hızını belirler.
  //
  // setState yalnızca requestAnimationFrame geri çağrısında yapılır —
  // effect gövdesinde senkron setState zincirleme render'a yol açıyor.
  // İlk kare ratio ≈ 0 verdiği için değer kendiliğinden TIMER_FROM'dan
  // başlar, ayrıca sıfırlamaya gerek yok.
  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    if (!open || seconds === null || seconds <= 0) return undefined;

    const startedAt = performance.now();
    const durationMs = seconds * 1000;

    const step = (now) => {
      const ratio = Math.min(1, (now - startedAt) / durationMs);
      setTimerPct(TIMER_FROM + (TIMER_TO - TIMER_FROM) * ratio);
      if (ratio < 1) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [open, phase, seconds]);

  const { pct, label } = useMemo(() => {
    if (isError) return { pct: 0, label: language === "EN" ? "Failed" : "Tamamlanamadı" };
    if (isReady) return { pct: 100, label: PHASES.robot_delivered[lang] };

    if (seconds !== null) {
      return { pct: timerPct, label: language === "EN" ? "Brewing" : "Demleniyor" };
    }

    const known = PHASES[phase];
    return known
      ? { pct: known.pct, label: known[lang] }
      : { pct: 8, label: FALLBACK[lang] };
  }, [isError, isReady, seconds, timerPct, phase, lang, language]);

  /* ── Hazır olunca otomatik kapan ──────────── */
  const closeTimerRef = useRef(null);

  useEffect(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    if (open && isReady && typeof handleClose === "function") {
      // Müşteri bardağı alsın diye kısa bir bekleme, sonra ekran
      // kendiliğinden yeni siparişe hazır hale gelir.
      closeTimerRef.current = setTimeout(handleClose, 6000);
    }
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, [open, isReady, handleClose]);

  const accent = isError ? palette.red : isReady ? palette.green : palette.red;
  const showQueue = totalItems > 1;

  return (
    <Modal
      open={Boolean(open)}
      onClose={isReady || isError ? handleClose : undefined}
      disableEscapeKeyDown={!isReady && !isError}
    >
      <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "92vw", sm: 480 },
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: "0 28px 70px rgba(23, 22, 15, 0.32)",
          p: { xs: 3, sm: 4 },
          outline: "none",
          textAlign: "center",
        }}
      >
        {/* Çoklu siparişte kaçıncı içecekte olduğumuz */}
        {showQueue && (
          <Typography variant="overline" color="text.secondary" display="block" mb={1}>
            {currentIndex + 1} / {totalItems}
          </Typography>
        )}

        {/* ── Dolum göstergesi ── */}
        <Box sx={{ mb: 2.5 }}>
          <CupFill
            src={item?.image}
            alt=""
            progress={pct}
            complete={isReady}
            accent={accent}
            height={220}
          />
        </Box>

        {/* Ürün adı */}
        {item && (
          <Typography variant="h3" mb={0.5}>
            {item[`Name_${language}`] ?? item.Name_TR ?? ""}
          </Typography>
        )}

        {/* Faz etiketi — makinenin sesi, mono */}
        <Typography
          variant="overline"
          sx={{ color: isError ? palette.red : "text.secondary", display: "block", mb: 2 }}
        >
          {label}
        </Typography>

        {/* Hata detayı */}
        {isError && error && (
          <Typography
            sx={{
              fontFamily: "var(--mono)",
              fontSize: 13,
              lineHeight: 1.7,
              color: "text.secondary",
              whiteSpace: "pre-line",
              mb: 2,
            }}
          >
            {error}
          </Typography>
        )}

        {/* Kapat butonu — hazırlanırken pasif */}
        <Button
          fullWidth
          variant={isReady ? "contained" : "outlined"}
          color={isReady ? "primary" : "secondary"}
          onClick={handleClose}
          disabled={!isReady && !isError}
        >
          {isReady
            ? (language === "EN" ? "Done" : "Tamam")
            : isError
              ? (language === "EN" ? "Close" : "Kapat")
              : (language === "EN" ? "Please wait" : "Lütfen bekleyin")}
        </Button>
      </Box>
    </Modal>
  );
};

export default PreparingCoffee;
