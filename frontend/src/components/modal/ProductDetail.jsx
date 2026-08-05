import { useState } from "react";
import {
  Box, Button, Typography, IconButton,
  Modal, Fade, Divider, Stack,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";

import { souces, syrups, getName, getDescription, extraName, extraChannel } from "../../helper/Beverages";
import { showToast } from "../../helper/toastify";
import { palette } from "../../theme";

/**
 * ProductDetail — ürün detayı ve ilave seçimi
 *
 * DÜZELTİLEN HATA:
 *   Bileşen item.Name ve item.description okuyordu, ama Beverages.js
 *   bu alanları Name_TR / Name_EN / description_TR / description_EN
 *   olarak tutuyor. Sonuç: başlık ve açıklama alanları boş çıkıyordu.
 *   Artık getName() / getDescription() yardımcıları kullanılıyor.
 *
 * DİĞER DEĞİŞİKLİKLER:
 *   • Açık temaya taşındı (hex literaller yerine tema renkleri)
 *   • "Cancel" / "Add to Cart" sabit İngilizceydi → dil desteği eklendi
 *   • Dokunma hedefleri büyütüldü, seçili ilave onay ikonuyla belirgin
 */

const LABELS = {
  TR: {
    syrup:  "Şurup seçin",
    sauce:  "Sos seçin",
    cancel: "Vazgeç",
    add:    "Sepete ekle",
    free:   "Ücretsiz",
  },
  EN: {
    syrup:  "Choose a syrup",
    sauce:  "Choose a sauce",
    cancel: "Cancel",
    add:    "Add to cart",
    free:   "Free",
  },
};

/* ─────────────────────────────────────────────
   İÇ BİLEŞEN
   ───────────────────────────────────────────── */

const ProductDetailInner = ({ item, onClose, onAdd, currency, language, disabledSyrupChannels = [] }) => {
  const [selected, setSelected] = useState(item?.customize ?? []);
  const t = LABELS[language] ?? LABELS.TR;

  // İlaveler dile bağlı olmayan `id` ile taşınır.
  // Önceden option.name kullanılıyordu ama bu alan kayıtlarda hiç
  // yoktu; undefined toggle edilince includes(undefined) her seçenek
  // için true dönüyor ve tek şurup seçilince hepsi seçili görünüyordu.
  const toggle = (id) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  const isIceCream   = item?.type === "ice_cream";
  const options      = isIceCream ? souces : syrups;
  const optionsLabel = isIceCream ? t.sauce : t.syrup;

  return (
    <Box
      sx={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: { xs: "94vw", sm: 720 },
        maxHeight: "88vh",
        overflowY: "auto",
        bgcolor: "background.paper",
        borderRadius: 1,
        boxShadow: "0 24px 60px rgba(23, 22, 15, 0.28)",
        outline: "none",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* ── Başlık ── */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          px: 3, py: 2,
          borderBottom: `1px solid ${palette.rule}`,
        }}
      >
        <Typography variant="h3" color="text.primary">
          {getName(item, language)}
        </Typography>
        <IconButton onClick={onClose} aria-label={t.cancel} sx={{ color: "text.secondary" }}>
          <CloseIcon />
        </IconButton>
      </Box>

      {/* ── Görsel + açıklama ── */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 3,
          p: 3,
          borderBottom: `1px solid ${palette.rule}`,
        }}
      >
        <Box
          component="img"
          src={item?.image}
          alt={getName(item, language)}
          sx={{ width: 130, height: 110, objectFit: "contain", flexShrink: 0 }}
        />
        <Box>
          <Typography fontSize={15} color="text.secondary" lineHeight={1.6} mb={1.5}>
            {getDescription(item, language)}
          </Typography>
          <Typography variant="h4" color="primary.main">
            {item?.price} {currency}
          </Typography>
        </Box>
      </Box>

      {/* ── İlaveler ── */}
      <Box sx={{ p: 3, flex: 1 }}>
        <Typography
          variant="overline"
          color="text.secondary"
          display="block"
          mb={2}
        >
          {optionsLabel}
        </Typography>

        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5 }}>
          {options.map((option) => {
            const channel = extraChannel(option.id);
            const soldOut = channel != null && disabledSyrupChannels.includes(channel);
            const active = selected.includes(option.id) && !soldOut;
            return (
              <Box
                key={option.id}
                role="button"
                tabIndex={0}
                onClick={() => !soldOut && toggle(option.id)}
                onKeyDown={(e) => !soldOut && (e.key === "Enter" || e.key === " ") && toggle(option.id)}
                aria-disabled={soldOut}
                sx={{
                  position: "relative",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 1,
                  p: 1.5,
                  width: 156,
                  borderRadius: 1,

                  bgcolor: active ? "rgba(229, 53, 42, 0.07)" : palette.sand,
                  border: `2px solid ${active ? palette.red : "transparent"}`,
                  transition: "border-color 0.18s, background-color 0.18s",
                  opacity: soldOut ? 0.4 : 1,
                  cursor: soldOut ? "not-allowed" : "pointer",
                  filter: soldOut ? "grayscale(1)" : "none",
                }}
              >
                {soldOut && (
                  <Box sx={{
                    position: "absolute", top: 8, left: 8, zIndex: 2,
                    bgcolor: palette.ink, color: palette.paper,
                    fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700,
                    letterSpacing: "0.08em", textTransform: "uppercase",
                    px: 0.75, py: 0.25, borderRadius: 0.5,
                  }}>
                    Tükendi
                  </Box>
                )}
                {active && (
                  <CheckCircleIcon
                    sx={{
                      position: "absolute", top: 8, right: 8, zIndex: 1,
                      fontSize: 22, color: palette.red,
                    }}
                  />
                )}

                {/* Görsel alanı 50px yükseklikteydi. Şurup şişeleri
                    119x500, yani 1:4.2 oranında; o kutuda 12x50'ye
                    inip neredeyse görünmez oluyorlardı. Yükseklik
                    116px'e çıkarıldı ve arkalarına hafif bir daire
                    kondu — şişe kart zemininden ayrışıyor. */}
                <Box
                  sx={{
                    position: "relative",
                    width: "100%",
                    height: 116,
                    display: "grid",
                    placeItems: "center",
                    "&::before": {
                      content: '""',
                      position: "absolute",
                      width: 96,
                      height: 96,
                      borderRadius: "50%",
                      bgcolor: active ? "rgba(229,53,42,0.10)" : "rgba(23,22,15,0.05)",
                      transition: "background-color 0.18s",
                    },
                  }}
                >
                  <Box
                    component="img"
                    src={option.image}
                    alt=""
                    sx={{
                      position: "relative",
                      maxWidth: "100%",
                      maxHeight: 116,
                      objectFit: "contain",
                      // Sos görselleri fotoğraf (şeffaf değil); hafif
                      // yuvarlatma onları ham kutu gibi göstermiyor.
                      // Şeffaf şişelerde görünür bir etkisi yok.
                      borderRadius: 6,
                      filter: active
                        ? "drop-shadow(0 3px 8px rgba(23,22,15,0.28))"
                        : "drop-shadow(0 2px 5px rgba(23,22,15,0.16))",
                      transform: active ? "scale(1.06)" : "none",
                      transition: "transform 0.18s, filter 0.18s",
                    }}
                  />
                </Box>
                <Typography
                  fontSize={14}
                  fontWeight={active ? 700 : 500}
                  textAlign="center"
                  color="text.primary"
                  lineHeight={1.3}
                >
                  {option[`name_${language}`] ?? option.name_TR}
                </Typography>
                <Typography variant="overline" color="text.secondary">
                  {option.price === "0,00" ? t.free : `${option.price} ${currency}`}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Box>

      <Divider />

      {/* ── Alt butonlar ── */}
      <Stack direction="row" spacing={2} sx={{ p: 2.5 }}>
        <Button fullWidth variant="outlined" color="secondary" onClick={onClose}>
          {t.cancel}
        </Button>
        <Button
          fullWidth
          variant="contained"
          color="primary"
          onClick={() => onAdd({ ...item, customize: selected })}
        >
          {t.add}
        </Button>
      </Stack>
    </Box>
  );
};

/* ─────────────────────────────────────────────
   DIŞ BİLEŞEN — Modal sarmalayıcı
   ───────────────────────────────────────────── */

const ProductDetail = ({
  productModal,
  setProductModal,
  addToCart,
  cart,
  currency,
  language = "TR",
  disabledSyrupChannels = [],
}) => {
  const item = productModal?.item;
  const itemKey = item ? `${item.type}_${item.ButtonNumber ?? item.Name_TR}` : "closed";

  const handleClose = () => setProductModal({ open: false, item: null });

  const handleAdd = (updated) => {
    const existing = Object.values(cart ?? {})[0];
    const sameProduct =
      existing &&
      existing.type === updated.type &&
      (existing.ButtonNumber ?? existing.Name_TR) === (updated.ButtonNumber ?? updated.Name_TR);

    const before = sameProduct ? (existing.customize ?? []) : [];
    const after  = updated.customize ?? [];

    const added   = after.filter((n) => !before.includes(n));
    const removed = before.filter((n) => !after.includes(n));

    addToCart(updated);
    handleClose();

    const label = (ids) => ids.map((id) => extraName(id, language)).join(", ");

    if (!sameProduct)          showToast.addToCart(getName(updated, language));
    else if (added.length)     showToast.addToCart(label(added));
    else if (removed.length)   showToast.info(`${label(removed)} çıkarıldı.`);
    else                       showToast.addToCart(getName(updated, language));
  };

  return (
    <Modal open={Boolean(productModal.open)} onClose={handleClose} closeAfterTransition>
      <Fade in={Boolean(productModal.open)}>
        <Box sx={{ outline: "none" }}>
          {item && (
            <ProductDetailInner
              key={itemKey}
              item={item}
              onClose={handleClose}
              onAdd={handleAdd}
              currency={currency}
              language={language}
              disabledSyrupChannels={disabledSyrupChannels}
            />
          )}
        </Box>
      </Fade>
    </Modal>
  );
};

export default ProductDetail;
