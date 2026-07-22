import { useRef, useEffect } from 'react';
import Modal from "@mui/material/Modal";
import Box from "@mui/material/Box";
import { Typography, Button } from "@mui/material";
import Lottie from "lottie-react";
import preparingAnimationData from "../../assets/CoffeeTea.json";
import readyAnimationData     from "../../assets/Correct.json";

// ─────────────────────────────────────────────
// Tek modal — 3 durum:
//   preparing : kahve hazırlanıyor (animasyon döner, Close disabled)
//   ready     : hazır (animasyon tamamlandı, Close aktif, 8s sonra oto kapanır)
//   error     : hata (Close aktif)
// ─────────────────────────────────────────────

const PreparingCoffee = ({ open, handleClose, rcpState, status, phase, error }) => {

  const isReady = (
    status === "done"              ||
    phase  === "robot_delivered"   ||
    rcpState === 9                 ||
    rcpState === -9
  );

  const isError = status === "error" || status === "timeout";

  // isReady olduğunda 8 saniye sonra otomatik kapat
  const timerRef = useRef(null);

  useEffect(() => {
    if (!open) return;

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    if (isReady && typeof handleClose === "function") {
      timerRef.current = setTimeout(() => {
        handleClose();
      }, 8000);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [open, isReady]);  // eslint-disable-line

  return (
    <Modal
      open={open}
      onClose={isReady || isError ? handleClose : undefined}
      disableEscapeKeyDown={!isReady && !isError}
    >
      <Box sx={{
        position: "absolute",
        top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        width: { xs: "90%", sm: "70%", md: "50%", lg: "40%" },
        bgcolor: "background.paper",
        boxShadow: 24,
        borderRadius: 3,
        p: 4,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 2,
        outline: "none",
      }}>

        {/* Animasyon */}
        <Box sx={{ width: "100%", maxWidth: 280, mx: "auto" }}>
          <Lottie
            animationData={isReady ? readyAnimationData : preparingAnimationData}
            loop={!isReady && !isError}
            autoPlay
          />
        </Box>

        {/* Başlık */}
        <Typography
          variant="overline"
          fontSize={20}
          align="center"
          color={isError ? "error" : "text.primary"}
          fontWeight={600}
          lineHeight={1.4}
        >
          {isReady
            ? "İçeceğiniz hazır ☕"
            : isError
              ? "Bir hata oluştu"
              : "Kahveniz hazırlanıyor..."}
        </Typography>

        {/* Hata mesajı */}
        {isError && error && (
          <Typography variant="body2" align="center" color="text.secondary">
            {error}
          </Typography>
        )}

        {/* Close butonu */}
        <Button
          variant={isReady ? "contained" : "outlined"}
          onClick={handleClose}
          disabled={!isReady && !isError}
          sx={{
            mt: 1,
            height: 52,
            width: 180,
            fontWeight: 700,
            fontSize: 15,
            borderRadius: 2,
          }}
        >
          {isReady ? "Tamam" : isError ? "Kapat" : "Lütfen bekleyin..."}
        </Button>

      </Box>
    </Modal>
  );
};

export default PreparingCoffee;
