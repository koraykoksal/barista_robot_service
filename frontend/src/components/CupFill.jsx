import { Box } from "@mui/material";
import { palette } from "../theme";

/**
 * CupFill — ürün görseli üzerinde dolum göstergesi
 *
 * FİKİR:
 *   Aynı ürün görselini iki kez üst üste koyar.
 *     alt katman  : gri ve soluk  (henüz dolmamış kısım)
 *     üst katman  : tam renkli, clip-path ile alttan yukarı açılır
 *   Aralarında sıvı yüzeyini işaretleyen ince bir çizgi var.
 *
 *   Böylece ilerleme, ayrı bir çubuk veya sayaç olmadan doğrudan
 *   ürünün kendi görseli üzerinde okunur. Görsel dosyaları
 *   DEĞİŞTİRİLMEZ — mevcut .webp/.png varlıkları aynen kullanılır,
 *   yalnızca iki kez render edilirler.
 *
 * KULLANIM:
 *   <CupFill src={item.image} alt={name} progress={62} />
 *
 * progress:
 *   0   → görsel tamamen soluk (henüz başlamadı)
 *   100 → görsel tamamen renkli (hazır)
 *
 *   Bu değer Aşama 2'de backend'in faz bilgisinden türetilir,
 *   arayüzde sayaç çalıştırılmaz. Tek doğruluk kaynağı backend'dir.
 */
const CupFill = ({
  src,
  alt = "",
  progress = 0,
  accent = palette.red,
  height = 160,
  width = "100%",
  /** true → dolum tamamlanmış gibi göster (hazır durumu) */
  complete = false,
}) => {
  const pct = complete ? 100 : Math.min(100, Math.max(0, Number(progress) || 0));

  // clip-path inset üstten kırpar: %100 boş = hiç görünmüyor
  const emptyPct = 100 - pct;

  const layer = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: "contain",
    display: "block",
    pointerEvents: "none",
  };

  return (
    <Box
      sx={{
        position: "relative",
        width,
        height,
        overflow: "hidden",
        display: "grid",
        placeItems: "center",
      }}
    >
      {/* Alt katman — henüz dolmamış kısım */}
      <Box
        component="img"
        src={src}
        alt={alt}
        sx={{
          ...layer,
          filter: "grayscale(1) brightness(1.06) contrast(0.82)",
          opacity: 0.42,
        }}
      />

      {/* Üst katman — dolan kısım */}
      <Box
        component="img"
        src={src}
        alt=""
        aria-hidden="true"
        sx={{
          ...layer,
          clipPath: `inset(${emptyPct}% 0 0 0)`,
          transition: "clip-path 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      />

      {/* Sıvı yüzeyi — dolum seviyesini okunur kılan ince çizgi.
          Dolum başlamadıysa veya tamamlandıysa gizlenir. */}
      {pct > 0 && pct < 100 && (
        <Box
          aria-hidden="true"
          sx={{
            position: "absolute",
            left: "8%",
            right: "8%",
            top: `${emptyPct}%`,
            height: 2,
            borderRadius: 1,
            backgroundColor: accent,
            opacity: 0.85,
            transition: "top 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      )}
    </Box>
  );
};

export default CupFill;
