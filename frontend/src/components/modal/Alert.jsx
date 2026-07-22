import { Box, Button, Modal, Stack, Typography } from "@mui/material";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";

import { palette } from "../../theme";

/**
 * Alert — hata bildirimi
 *
 * DEĞİŞENLER:
 *   • Açık temaya taşındı, genişlik dokunmatik panele göre ayarlandı
 *   • "OK" sabit İngilizceydi → dil desteği
 *   • Sipariş hatalarında kullanıcıya ne yapacağını söyleyen bir
 *     alt satır eklendi; ekranda tek başına duran hata metni
 *     müşteriye bir şey ifade etmiyordu
 */

const LABELS = {
  TR: { title: "Bir sorun oluştu", ok: "Tamam", hint: "Tekrar deneyebilir veya personelden yardım isteyebilirsiniz." },
  EN: { title: "Something went wrong", ok: "OK", hint: "You can try again or ask a staff member for help." },
};

const Alert = ({ openAlert, handleCloseAlert, alertData, setAlertData, language = "TR" }) => {
  const { title, message } = alertData || {};
  const t = LABELS[language] ?? LABELS.TR;

  const closeAndReset = () => {
    handleCloseAlert();
    setAlertData?.({ title: "", message: "", code: null, errorId: null });
  };

  return (
    <Modal open={Boolean(openAlert)} onClose={closeAndReset}>
      <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "92vw", sm: 520 },
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: "0 24px 60px rgba(23, 22, 15, 0.3)",
          p: 4,
          outline: "none",
          // Sol kenarda kırmızı şerit — hata olduğu tek bakışta anlaşılsın
          borderLeft: `5px solid ${palette.red}`,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" mb={2}>
          <ErrorOutlineIcon sx={{ color: palette.red, fontSize: 30 }} />
          <Typography variant="h3">{title || t.title}</Typography>
        </Stack>

        {message && (
          <Typography
            sx={{
              fontFamily: "var(--mono)",
              fontSize: 14,
              lineHeight: 1.7,
              color: "text.secondary",
              whiteSpace: "pre-line",   // backend "\n" içeren mesajlar gönderiyor
              mb: 2,
            }}
          >
            {message}
          </Typography>
        )}

        <Typography variant="caption" display="block" mb={3}>
          {t.hint}
        </Typography>

        <Button fullWidth variant="contained" color="secondary" onClick={closeAndReset}>
          {t.ok}
        </Button>
      </Box>
    </Modal>
  );
};

export default Alert;
