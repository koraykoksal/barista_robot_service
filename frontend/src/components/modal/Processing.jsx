import React from 'react'
import { Modal, Fade, Backdrop, LinearProgress } from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import CoffeeIcon from "@mui/icons-material/Coffee";
import {
    Box, Button, Typography, IconButton, Badge,
    Divider, Drawer,
} from "@mui/material";

const Processing = ({orderModal,setOrderModal}) => {
  return (


    <Modal
      open={orderModal.open}
      onClose={() => orderModal.status === "ready" && setOrderModal({ open: false, status: null })}
      closeAfterTransition
      slots={{ backdrop: Backdrop }}
      slotProps={{ backdrop: { timeout: 500 } }}
    >
      <Fade in={orderModal.open}>
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: { xs: "85vw", sm: "420px" },
            backgroundColor: "#2e2720",
            border: orderModal.status === "ready"
              ? "1px solid #4CAF50"
              : "1px solid #DEC39B",
            borderRadius: 3,
            boxShadow: orderModal.status === "ready"
              ? "0 0 144px rgba(76, 175, 80, 0.4)"
              : "0 0 144px rgba(222, 195, 155, 0.4)",
            p: 4,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 3,
            outline: "none",
          }}
        >
          {orderModal.status === "preparing" ? (
            <>
              {/* Preparing içeriği */}
              <CoffeeIcon sx={{ fontSize: "64px", color: "#DEC39B" }} />
              <Typography
                fontSize={26}
                fontWeight="bold"
                color="#DEC39B"
                letterSpacing={2}
              >
                Preparing...
              </Typography>
              <Typography fontSize={14} color="#a08060" textAlign="center">
                Siparişiniz hazırlanıyor, lütfen bekleyiniz.
              </Typography>
              <LinearProgress
                sx={{
                  width: "100%",
                  borderRadius: 2,
                  height: 6,
                  backgroundColor: "#3a312a",
                  "& .MuiLinearProgress-bar": {
                    backgroundColor: "#DEC39B",
                  },
                }}
              />
            </>
          ) : (
            <>
              {/* Ready içeriği */}
              <CheckCircleOutlineIcon sx={{ fontSize: "64px", color: "#4CAF50" }} />
              <Typography
                fontSize={26}
                fontWeight="bold"
                color="#4CAF50"
                letterSpacing={2}
              >
                Ready!
              </Typography>
              <Typography fontSize={14} color="#a08060" textAlign="center">
                Siparişiniz hazır, afiyet olsun!
              </Typography>
              <Button
                fullWidth
                onClick={() => setOrderModal({ open: false, status: null })}
                sx={{
                  backgroundColor: "#4CAF50",
                  color: "#fff",
                  fontWeight: "bold",
                  textTransform: "none",
                  fontSize: "16px",
                  borderRadius: 2,
                  "&:hover": { backgroundColor: "#388E3C" },
                }}
              >
                Tamam
              </Button>
            </>
          )}
        </Box>
      </Fade>
    </Modal>

  )
}

export default Processing