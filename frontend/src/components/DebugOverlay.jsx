import { Box, Typography } from "@mui/material";

import {
  ALL_MOCKED,
  API_URL,
  MOCKED_LABEL,
  OFFLINE_SCENARIO,
  OFFLINE_SERVICES,
  OFFLINE_SPEED,
  SERVICE_KEYS,
  SERVICE_LABELS,
} from "../api/env";
import { palette } from "../theme";

/**
 * DebugOverlay — ekran üstü teşhis paneli
 *
 * AÇMAK İÇİN:  http://localhost:5173/?debug=1
 *
 * NEDEN VAR:
 *   Kiosk dokunmatik panelde tarayıcı geliştirici araçlarını açmak
 *   zahmetli. "Çevrimdışı moda aldım ama hâlâ bağlanmaya çalışıyor"
 *   gibi durumlarda hangi ayarın gerçekten okunduğunu görmenin
 *   pratik bir yolu olmalı.
 *
 *   Panel, uygulamanın O ANDA kullandığı değerleri gösterir — .env
 *   dosyasında ne yazdığını değil. İkisi farklıysa sorun ayarın
 *   uygulamaya ulaşmamasıdır:
 *     • .env dosyası frontend/ klasöründe mi? (repo kökünde değil)
 *     • dev sunucusu .env düzenlendikten sonra yeniden başlatıldı mı?
 *     • derlenmiş dist/ mi servis ediliyor? Vite değerleri DERLEME
 *       anında gömer; sonradan .env değiştirmek etkilemez.
 */

const Row = ({ label, value, tone }) => (
  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, py: 0.25 }}>
    <span style={{ opacity: 0.65 }}>{label}</span>
    <span style={{ color: tone || "inherit", fontWeight: 700 }}>{value}</span>
  </Box>
);

const DebugOverlay = ({ machine, robotStatus, stockStatus, blocked, bannerMessage }) => (
  <Box
    sx={{
      position: "fixed",
      right: 12,
      bottom: 12,
      zIndex: 2000,
      width: 340,
      maxHeight: "70vh",
      overflowY: "auto",
      bgcolor: palette.machine,
      color: palette.paper,
      borderRadius: 1,
      border: `1px solid ${palette.lime}`,
      p: 2,
      fontFamily: "var(--mono)",
      fontSize: 11,
      lineHeight: 1.7,
      boxShadow: "0 12px 32px rgba(0,0,0,0.4)",
    }}
  >
    <Typography
      sx={{
        fontFamily: "var(--mono)",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.14em",
        color: palette.lime,
        mb: 1,
      }}
    >
      TEŞHİS · ?debug=1
    </Typography>

    <Row label="API adresi" value={API_URL} />
    <Row
      label="çevrimdışı"
      value={ALL_MOCKED ? "hepsi sahte" : MOCKED_LABEL || "KAPALI"}
      tone={MOCKED_LABEL ? palette.lime : palette.red}
    />
    <Row label="senaryo" value={OFFLINE_SCENARIO} />
    <Row label="hız" value={`${OFFLINE_SPEED}×`} />

    <Box sx={{ borderTop: `1px solid ${palette.lime}33`, mt: 1, pt: 1 }}>
      {SERVICE_KEYS.map((key) => (
        <Row
          key={key}
          label={SERVICE_LABELS[key]}
          value={OFFLINE_SERVICES[key] ? "sahte" : "gerçek"}
          tone={OFFLINE_SERVICES[key] ? palette.lime : "#E9A23B"}
        />
      ))}
    </Box>

    <Box sx={{ borderTop: `1px solid ${palette.lime}33`, mt: 1, pt: 1 }}>
      <Row label="makine online" value={String(machine?.online)} />
      <Row label="makine hata" value={String(machine?.has_blocking_error)} />
      <Row label="robot can_order" value={String(robotStatus?.can_order)} />
      <Row label="stok kilidi" value={String(stockStatus?.status?.all_disabled)} />
      <Row
        label="ekran"
        value={blocked ? "BLOKE" : "açık"}
        tone={blocked ? palette.red : palette.lime}
      />
    </Box>

    {bannerMessage && (
      <Box sx={{ borderTop: `1px solid ${palette.lime}33`, mt: 1, pt: 1, opacity: 0.8 }}>
        {bannerMessage}
      </Box>
    )}

    {/* En sık karşılaşılan durum için doğrudan ipucu */}
    {!MOCKED_LABEL && (
      <Box sx={{ mt: 1.5, p: 1, bgcolor: "rgba(229,53,42,0.18)", borderRadius: 0.5 }}>
        Çevrimdışı mod KAPALI görünüyor. `.env` dosyası
        <b> frontend/ </b> klasöründe mi ve dev sunucusu yeniden
        başlatıldı mı? Denemek için adrese <b>?offline=1</b> ekleyin.
      </Box>
    )}
  </Box>
);

export default DebugOverlay;
