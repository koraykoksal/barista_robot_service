import React, { useState } from "react";
import {
    Box, Button, Typography, IconButton,
    Modal, Fade, Backdrop, Divider,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { souces, syrups } from "../../helper/Beverages";
import { showToast } from "../../helper/toastify";


/* ─── İç bileşen: item, onClose, onAdd, currency alır ─── */
const ProductDetailInner = ({ item, onClose, onAdd, currency }) => {

    const [selectedCustomize, setSelectedCustomize] = useState(item?.customize ?? []);

    const toggleCustomize = (name) => {
        setSelectedCustomize((prev) =>
            prev.includes(name)
                ? prev.filter((n) => n !== name)
                : [...prev, name]
        );
    };

    const customizeList = item?.type === "ice_cream" ? souces : syrups;
    const customizeLabel = item?.type === "ice_cream" ? "🍦 Sauce Seç" : "☕ Syrup Seç";

    return (
        <Box
            sx={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                width: { xs: "90vw", sm: "560px" },
                maxHeight: "85vh",
                overflowY: "auto",
                backgroundColor: "#2e2720",
                border: "1px solid #DEC39B",
                borderRadius: 3,
                boxShadow: "0 0 32px rgba(222, 195, 155, 0.3)",
                outline: "none",
                display: "flex",
                flexDirection: "column",
            }}
        >
            {/* ── Header ── */}
            <Box sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                p: 2,
                borderBottom: "1px solid rgba(222,195,155,0.2)",
            }}>
                <Typography fontSize={20} fontWeight="bold" color="#DEC39B" letterSpacing={1}>
                    {item?.Name}
                </Typography>
                <IconButton onClick={onClose} sx={{ color: "#DEC39B" }}>
                    <CloseIcon />
                </IconButton>
            </Box>

            {/* ── Ürün Resim + Bilgi ── */}
            <Box sx={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                p: 3,
                borderBottom: "1px solid rgba(222,195,155,0.1)",
            }}>
                <img
                    src={item?.image}
                    alt={item?.Name}
                    style={{ width: "110px", height: "90px", objectFit: "contain" }}
                />
                <Box>
                    <Typography fontSize={15} color="#E7D9CF" mb={1.5} lineHeight={1.6}>
                        {item?.description}
                    </Typography>
                    <Typography fontSize={18} fontWeight="bold" color="#FFB74D">
                        {item?.price} {currency}
                    </Typography>
                </Box>
            </Box>

            {/* ── Customize Alanı ── */}
            <Box sx={{ p: 3, flex: 1 }}>
                <Typography fontSize={16} fontWeight="bold" color="#DEC39B" mb={2} letterSpacing={1}>
                    {customizeLabel}
                </Typography>

                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
                    {customizeList.map((option) => {
                        const isSelected = selectedCustomize.includes(option.name);
                        return (
                            <Box
                                key={option.name}
                                onClick={() => toggleCustomize(option.name)}
                                sx={{
                                    display: "flex",
                                    flexDirection: "column",
                                    alignItems: "center",
                                    gap: 1,
                                    p: 1.5,
                                    borderRadius: 2,
                                    cursor: "pointer",
                                    width: "150px",
                                    backgroundColor: isSelected ? "rgba(222,195,155,0.15)" : "#3a312a",
                                    border: isSelected ? "2px solid #DEC39B" : "2px solid transparent",
                                    boxShadow: isSelected ? "0 0 10px rgba(222,195,155,0.5)" : "none",
                                    transition: "all 0.2s",
                                    "&:hover": { border: "2px solid rgba(222,195,155,0.5)" },
                                }}
                            >
                                <img
                                    src={option.image}
                                    alt={option.name}
                                    style={{ width: "60px", height: "50px", objectFit: "contain" }}
                                />
                                <Typography
                                    fontSize={13}
                                    fontWeight={isSelected ? "bold" : "normal"}
                                    color={isSelected ? "#DEC39B" : "#E7D9CF"}
                                    textAlign="center"
                                >
                                    {option.name}
                                </Typography>
                                <Typography
                                    fontSize={12}
                                    color={option.price === "0,00" ? "#6b9e6b" : "#FFB74D"}
                                    fontWeight={isSelected ? "bold" : "normal"}
                                >
                                    {/* {option.price === "0,00" ? "Ücretsiz" : `+${option.price} ${currency}`} */}
                                    {`${option.price} ${currency}`}
                                </Typography>
                            </Box>
                        );
                    })}
                </Box>
            </Box>

            <Divider sx={{ borderColor: "rgba(222,195,155,0.15)" }} />

            {/* ── Alt Butonlar ── */}
            <Box sx={{ display: "flex", gap: 2, p: 2 }}>
                <Button
                    fullWidth
                    onClick={onClose}
                    sx={{
                        height: "48px",
                        textTransform: "none",
                        fontSize: "16px",
                        fontWeight: "bold",
                        backgroundColor: "transparent",
                        border: "1px solid rgba(222,195,155,0.4)",
                        color: "#a08060",
                        borderRadius: 2,
                        "&:hover": { backgroundColor: "rgba(222,195,155,0.05)" },
                    }}
                >
                    Cancel
                </Button>

                <Button
                    fullWidth
                    onClick={() => onAdd({ ...item, customize: selectedCustomize })}
                    sx={{
                        height: "48px",
                        textTransform: "none",
                        fontSize: "16px",
                        fontWeight: "bold",
                        backgroundColor: "#DEC39B",
                        color: "#454039",
                        borderRadius: 2,
                        boxShadow: "0 0 10px rgba(222,195,155,0.4)",
                        "&:hover": { backgroundColor: "#cdb080" },
                    }}
                >
                    Add to Cart
                </Button>
            </Box>
        </Box>
    );
};

/* ─── Dış bileşen: Modal wrapper ─── */
const ProductDetail = ({ productModal, setProductModal, addToCart, cart, currency }) => {

    const item = productModal?.item;
    const itemKey = item ? `${item.type}_${item.ButtonNumber ?? item.Name}` : "closed";

    const handleClose = () => {
        setProductModal({ open: false, item: null });
    };

    // Sepete eklenir/güncellenir, akıllı toast mesajı gösterilir
    const handleAdd = (updatedItem) => {
        // Sepetteki mevcut ürün (varsa)
        const existing = Object.values(cart ?? {})[0];
        const isSameProduct =
            existing &&
            existing.type === updatedItem.type &&
            (existing.ButtonNumber ?? existing.Name) === (updatedItem.ButtonNumber ?? updatedItem.Name);

        const oldCustomize = isSameProduct ? (existing.customize ?? []) : [];
        const newCustomize = updatedItem.customize ?? [];

        // Yeni eklenenler
        const added = newCustomize.filter((n) => !oldCustomize.includes(n));
        // Çıkarılanlar
        const removed = oldCustomize.filter((n) => !newCustomize.includes(n));

        addToCart(updatedItem);

        // Toast: yeni eklenen varsa onun adını, yoksa çıkarılan adını, hiçbiri yoksa ürün adını göster
        if (!isSameProduct) {
            // Yeni ürün eklenmiş
            showToast.addToCart(updatedItem.Name);
        } else if (added.length > 0) {
            // Customize eklendi
            showToast.addToCart(added.join(", "));
        } else if (removed.length > 0) {
            // Customize çıkarıldı
            showToast.info(`${removed.join(", ")} çıkarıldı.`);
        } else {
            // Değişiklik yok ama Add to Cart yine de basılmış
            showToast.addToCart(updatedItem.Name);
        }
    };

    return (
        <Modal
            open={productModal.open}
            onClose={handleClose}
            closeAfterTransition
            slots={{ backdrop: Backdrop }}
            slotProps={{ backdrop: { timeout: 400 } }}
        >
            <Fade in={productModal.open}>
                <Box sx={{ outline: "none" }}>
                    {item && (
                        <ProductDetailInner
                            key={itemKey}
                            item={item}
                            onClose={handleClose}
                            onAdd={handleAdd}
                            currency={currency}
                        />
                    )}
                </Box>
            </Fade>
        </Modal>
    );
};

export default ProductDetail;
