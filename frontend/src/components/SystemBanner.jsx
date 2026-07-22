import { Box, Typography } from "@mui/material";
import { palette } from "../theme";

/**
 * SystemBanner — ekranın üstünde duran sistem uyarısı
 *
 * NEDEN:
 *   Önceki davranışta makineye veya robota ulaşılamadığında Home.jsx
 *   tüm ekranı tek bir mesajla değiştiriyordu:
 *
 *       if (!machine.online) return fullscreen("Kahve makinesi çevrimdışı.")
 *
 *   Müşteri boş bir ekran görüyordu; menünün var olduğunu, hangi
 *   içeceklerin sunulduğunu, sorunun geçici mi kalıcı mı olduğunu
 *   anlayamıyordu. Personel için de teşhis edilmesi zordu.
 *
 *   Artık ekran her zaman açılır. Sorun varsa üstte kırmızı bir şerit
 *   çıkar ve içerik etkileşime kapatılır (bkz. Home.jsx içindeki
 *   blocked sarmalayıcı).
 *
 * severity:
 *   "error"   → kırmızı, sipariş alınamaz
 *   "warning" → kehribar, sipariş alınabilir ama kısıtlı
 *   "info"    → koyu, bilgilendirme (ör. bağlanılıyor)
 */

const TONE = {
  error:   { bg: palette.red,     fg: "#FFFFFF" },
  warning: { bg: palette.amber,   fg: "#FFFFFF" },
  info:    { bg: palette.machine, fg: palette.paper },
};

const SystemBanner = ({ severity = "error", message, detail, pulse = false }) => {
  if (!message) return null;

  const tone = TONE[severity] ?? TONE.error;

  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{
        // Yapışkanlık üst sarmalayıcıda (Home.jsx) — banner ile başlığın
        // ayrı ayrı sticky olması kaydırmada üst üste binmelerine yol açıyordu.
        bgcolor: tone.bg,
        color: tone.fg,
        px: { xs: 2, md: 4 },
        py: 1.75,
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        boxShadow: "0 2px 12px rgba(23, 22, 15, 0.25)",
      }}
    >
      {/* Durum noktası — bağlanmayı beklerken yanıp söner */}
      <Box
        aria-hidden="true"
        sx={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          bgcolor: tone.fg,
          flex: "none",
          animation: pulse ? "bannerPulse 1.4s ease-in-out infinite" : "none",
          "@keyframes bannerPulse": {
            "0%, 100%": { opacity: 1 },
            "50%": { opacity: 0.25 },
          },
        }}
      />

      <Box sx={{ minWidth: 0 }}>
        <Typography
          sx={{
            fontFamily: "var(--mono)",
            fontSize: { xs: 13, sm: 15 },
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            lineHeight: 1.3,
          }}
        >
          {message}
        </Typography>

        {/* Teknik ayrıntı — personel için, müşteriyi boğmayacak boyutta */}
        {detail && (
          <Typography
            sx={{
              fontFamily: "var(--mono)",
              fontSize: 11,
              opacity: 0.85,
              lineHeight: 1.5,
              mt: 0.25,
            }}
          >
            {detail}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default SystemBanner;
