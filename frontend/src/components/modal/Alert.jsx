import Modal from "@mui/material/Modal";
import Box from "@mui/material/Box";
import { Typography, Container, Button } from "@mui/material";

const style = {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    width: "45%",
    bgcolor: "background.paper",
    boxShadow: 24,
    borderRadius: 3,
    p: 4,
};

const Alert = ({ openAlert, handleCloseAlert, alertData, setAlertData }) => {
    const { title, message, code, errorId } = alertData || {};

    const closeAndReset = () => {
        handleCloseAlert();
        if (setAlertData) {
            setAlertData({
                title: "",
                message: "",
                code: null,
                errorId: null,
            });
        }
    };

    return (
        <Modal keepMounted open={openAlert} onClose={closeAndReset}>
            <Box sx={style}>
                <Container sx={{ display: "flex", flexDirection: "column", gap: 2 }} maxWidth="sm">

                    <Typography variant="h6" color="black">
                        {title || "Warning"}
                    </Typography>

                    {message ? (
                        <Typography variant="body1" fontSize={20} color="gray">
                            {message}
                        </Typography>
                    ) : null}

                    {/* {(code !== null && code !== undefined) ? (
                        <Typography variant="caption" color="gray">
                            returnvalue: {code}
                        </Typography>
                    ) : null} */}

                    {/* {(errorId !== null && errorId !== undefined) ? (
                        <Typography variant="caption" color="gray">
                            errorId: {errorId}
                        </Typography>
                    ) : null} */}

                    <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, mt: 2 }}>
                        <Button variant="contained" onClick={closeAndReset}>
                            OK
                        </Button>
                    </Box>
                </Container>
            </Box>
        </Modal>
    );
};

export default Alert;
