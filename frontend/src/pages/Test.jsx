import React from 'react'
import {
    Box, Button, Typography, IconButton, Badge,
    Divider, Drawer,
} from "@mui/material";
import ShoppingCartIcon from "@mui/icons-material/ShoppingCart";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { beverages, souces, syrups } from "../helper/Beverages";
import { useRef, useState } from "react";
import coffee from "../assets/coffee.webp";
import ice_cream from "../assets/ice_cream.webp";
import ArrowBackIosIcon from "@mui/icons-material/ArrowBackIos";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import tr_flag from "../assets/tr_flag.png";
import en_flag from "../assets/uk_flag.png";
import logo from "../assets/logorob_logo.png";
import Processing from '../components/modal/Processing';
import ProductDetail from '../components/modal/ProductDetail';
import Chip from "@mui/material/Chip";


const Test = () => {

    const [cart, setCart] = useState({});         // { ButtonNumber: { ...item, qty } }
    const [cartOpen, setCartOpen] = useState(false);

    const currency = "₺"; // TL simgesi için Unicode karakteri
    const [coffee_page, setCoffee_page] = useState(false);
    const [chocolate_page, setChocolate_page] = useState(false);
    const [coffeeIndex, setCoffeeIndex] = useState(0);
    const itemsPerPage = 3;
    const [language, setLanguage] = useState("TR"); // aktif dil state'i
    const [orderModal, setOrderModal] = useState({ open: false, status: null });
    // status: null | "preparing" | "ready"

    const [productModal, setProductModal] = useState({ open: false, item: null });

    const touchStartX = useRef(null);

    /* ─── Touch handlers ─── */
    const handleTouchStart = (e) => {
        touchStartX.current = e.touches[0].clientX;
    };

    const handleTouchEnd = (e, listLength) => {
        if (touchStartX.current === null) return;
        const diff = touchStartX.current - e.changedTouches[0].clientX;
        if (diff > 50) {
            setCoffeeIndex((prev) => (prev + 1) * itemsPerPage < listLength ? prev + 1 : prev);
        } else if (diff < -50) {
            setCoffeeIndex((prev) => Math.max(prev - 1, 0));
        }
        touchStartX.current = null;
    };

    /* ─── Page reset ─── */
    const handleReset = () => {
        setCoffee_page(false);
        setChocolate_page(false);
        setCoffeeIndex(0);
    };

    const handlePageSelect = (data) => {
        data?.type === "coffee" && setCoffee_page(true);
        data?.type === "ice_cream" && setChocolate_page(true);
    };

    /* ─── Cart helpers (Tek Ürün Modu) ─── */
    const SINGLE_CART_KEY = "current_order";

    // "12,50" → 12.50
    const parsePrice = (priceStr) => parseFloat((priceStr ?? "0").replace(",", ".")) || 0;

    // Bir item'ın toplam fiyatı (ürün + customize) * qty
    const calcItemTotal = (item) => {
        const basePrice = parsePrice(item.price);
        const customizePrice = (item.customize ?? []).reduce((sum, name) => {
            const allExtras = [...(souces ?? []), ...(syrups ?? [])];
            const found = allExtras.find((e) => e.name === name);
            return sum + parsePrice(found?.price);
        }, 0);
        return (basePrice + customizePrice) * item.qty;
    };

    const totalCartItems = Object.values(cart).reduce((sum, i) => sum + i.qty, 0);
    const totalCartPrice = Object.values(cart).reduce((sum, i) => sum + calcItemTotal(i), 0);

    // Sepete ekle / güncelle
    // - Aynı ürün ise: customize güncellenir, qty AYNI KALIR
    // - Farklı ürün ise: sepet sıfırlanır, yeni ürün 1 adet eklenir
    const addToCart = (item) => {
        setCart((prev) => {
            const existing = prev[SINGLE_CART_KEY];
            const isSameProduct =
                existing &&
                existing.type === item.type &&
                (existing.ButtonNumber ?? existing.Name) === (item.ButtonNumber ?? item.Name);

            if (isSameProduct) {
                return {
                    [SINGLE_CART_KEY]: {
                        ...existing,
                        customize: item.customize ?? [],
                    },
                };
            }

            return {
                [SINGLE_CART_KEY]: {
                    ...item,
                    qty: 1,
                    customize: item.customize ?? [],
                    cartKey: SINGLE_CART_KEY,
                },
            };
        });
    };

    const removeFromCart = () => {
        setCart((prev) => {
            const item = prev[SINGLE_CART_KEY];
            if (!item) return prev;
            if (item.qty > 1) {
                return { [SINGLE_CART_KEY]: { ...item, qty: item.qty - 1 } };
            }
            return {};
        });
    };

    const deleteFromCart = () => {
        setCart({});
    };

    const removeCustomizeFromCart = (item, customizeName) => {
        setCart((prev) => {
            if (!prev[SINGLE_CART_KEY]) return prev;
            const newCustomize = (prev[SINGLE_CART_KEY].customize ?? []).filter((n) => n !== customizeName);
            return {
                [SINGLE_CART_KEY]: {
                    ...prev[SINGLE_CART_KEY],
                    customize: newCustomize,
                },
            };
        });
    };

    /* ─── Reusable card renderer ─── */
    const renderCards = (list) =>
        list
            .slice(coffeeIndex * itemsPerPage, coffeeIndex * itemsPerPage + itemsPerPage)
            .map((item) => {
                // Tek ürün modu: sepetteki ürün bu mu?
                const currentInCart = cart[SINGLE_CART_KEY];
                const baseKey = `${item.type}_${item.ButtonNumber ?? item.Name}`;
                const inCart = currentInCart &&
                    `${currentInCart.type}_${currentInCart.ButtonNumber ?? currentInCart.Name}` === baseKey;
                const itemQty = inCart ? currentInCart.qty : 0;

                return (
                    <Box
                        key={baseKey}
                        onClick={() => {
                            // Aynı ürün ise mevcut customize ile aç, farklı ürün için boş
                            const existingCustomize = inCart ? (currentInCart.customize ?? []) : [];
                            setProductModal({
                                open: true,
                                item: { ...item, customize: existingCustomize },
                            });
                        }}
                        sx={{
                            border: inCart ? "1px solid #42a5f5" : "1px solid #DEC39B",
                            borderRadius: 2,
                            width: { xs: "250px", sm: "280px", md: "300px", lg: "320px", xl: "350px" },
                            height: { xs: "210px", sm: "230px", md: "250px" },
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexDirection: "column",
                            gap: 2,
                            marginBottom: 2,
                            backgroundColor: "#454039",
                            cursor: "pointer",
                            boxShadow: inCart
                                ? "0 0 12px rgba(66, 165, 245, 0.85)"
                                : "0 2px 8px rgba(222, 195, 155, 1)",
                            transition: "transform 0.2s, box-shadow 0.3s",
                            "&:hover": { transform: "translateY(-2px)" },
                        }}
                    >
                        {/* Ürün görseli ve adı */}
                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
                            {/* <img src={item?.image} alt={item?.Name} style={{ width: "100px", height: "85px" }} /> */}
                            <Badge
                                badgeContent={itemQty}
                                color="error"
                                sx={{
                                    "& .MuiBadge-badge": {
                                        fontSize: "18px",      // font büyüklüğü
                                        height: "32px",        // badge yüksekliği
                                        minWidth: "33px",      // badge genişliği
                                        borderRadius: "14px",  // yuvarlak kalması için
                                        padding: "0 6px",
                                    }
                                }}
                            >
                                <img src={item?.image} alt={item?.Name} style={{ width: "100px", height: "85px" }} />
                            </Badge>
                            <Typography
                                fontSize={"24px"}
                                align='center'
                                color='#E7D9CF'
                                sx={{ textShadow: "0 0px 2px rgba(222, 195, 155, 1)", letterSpacing: "1px" }}
                            >
                                {item?.Name}
                            </Typography>

                            <Typography
                                fontSize={"18px"}
                                fontWeight="bold"
                                color="#FFB74D"
                                sx={{
                                    textShadow: "0 0px 4px rgba(222, 195, 155, 0.6)",
                                    letterSpacing: "1px",
                                }}
                            >
                                {item?.price} {currency}
                            </Typography>
                        </Box>

                        {/* Add / Remove butonları */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>

                            {/* <Button
                                size="small"
                                // startIcon={<AddIcon sx={{ fontSize: "28px !important" }}/>}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    // customize sayfasına yönlendirme yapılacaksa buraya eklenebilir
                                }}
                                sx={{
                                    height: "40px",
                                    minWidth: "100px",
                                    fontSize: "16px",
                                    textTransform: "none",
                                    backgroundColor: "#7B5EA7",
                                    color: "#F3EEF9",
                                    fontWeight: "bold",
                                    boxShadow: "0px 0px 4px rgba(222, 195, 155, 1)",
                                    "&:hover": { backgroundColor: "#6A4F94" },
                                }}
                            >
                                Customize
                            </Button> */}

                            {/* <IconButton
                                onClick={(e) => {
                                    e.stopPropagation();
                                    addToCart(item);
                                }}
                                sx={{
                                    width: "40px",
                                    height: "40px",
                                    backgroundColor: "#DEC39B",
                                    color: "#454039",
                                    borderRadius: 1,
                                    padding: 0,           // ← padding'i sıfırla
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    boxShadow: "0px 0px 4px rgba(222, 195, 155, 1)",
                                    "&:hover": { backgroundColor: "#cdb080" },
                                }}
                            >
                                <AddIcon sx={{ fontSize: "28px" }} />
                            </IconButton> */}

                            {/* Sepette varsa Remove butonu göster */}
                            {inCart && (
                                <IconButton
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeFromCart(item);
                                    }}
                                    sx={{
                                        width: "40px",
                                        height: "40px",
                                        backgroundColor: "#6b3a2a",
                                        color: "#E7D9CF",
                                        borderRadius: 1,
                                        padding: 0,           // ← padding'i sıfırla
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        boxShadow: "0px 0px 4px rgba(107, 58, 42, 0.8)",
                                        "&:hover": { backgroundColor: "#7d4433" },
                                    }}
                                >
                                    <RemoveIcon sx={{ fontSize: "28px" }} />
                                </IconButton>
                            )}
                        </Box>
                    </Box>
                );
            });

    /* ─── Reusable paginated list ─── */
    const renderPage = (list, title) => {
        const totalPages = Math.ceil(list.length / itemsPerPage);
        return (
            <Box>

                <Typography
                    align='center'
                    p={3}
                    fontSize={22}
                    fontWeight="bold"
                    sx={{
                        letterSpacing: "2px",
                        background: "linear-gradient(135deg, #DEC39B 0%, #c9a87a 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                    }}
                >
                    {title}
                </Typography>

                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 2, width: "100%" }}>

                    <IconButton
                        onClick={() => setCoffeeIndex((prev) => Math.max(prev - 1, 0))}
                        disabled={coffeeIndex === 0 || totalPages <= 1}
                        sx={{ color: "#DEC39B" }}
                    >
                        <ArrowBackIosIcon fontSize='large' />
                    </IconButton>

                    <Box
                        onTouchStart={handleTouchStart}
                        onTouchEnd={(e) => handleTouchEnd(e, list.length)}
                        sx={{ display: "flex", justifyContent: "center", gap: 2 }}
                    >
                        {renderCards(list)}
                    </Box>

                    <IconButton
                        onClick={() => setCoffeeIndex((prev) =>
                            (prev + 1) * itemsPerPage < list.length ? prev + 1 : prev
                        )}
                        disabled={(coffeeIndex + 1) * itemsPerPage >= list.length || totalPages <= 1}
                        sx={{ color: "#DEC39B" }}
                    >
                        <ArrowForwardIosIcon fontSize='large' />
                    </IconButton>

                </Box>
            </Box>
        );
    };


    const handleLanguageChange = (lang) => {
        setLanguage(lang);
        // i18n entegrasyonu varsa buraya eklenebilir
    };



    return (
        <Box sx={{ height: "100vh", display: "flex", flexDirection: "column" }}>

            {/* ─── Header ─── */}
            <Box sx={{
                display: "flex",
                justifyContent: "space-evenly",
                alignItems: "center",
            }}>

                {/* logo */}
                <Box sx={{ p: 3 }}>
                    <img src={logo} alt="Logo" style={{ width: "120px", objectFit: "cover" }} />
                </Box>

                {/* menü ve sepet butonu */}
                <Box sx={{ p: 3, display: "flex", justifyContent: "center", }}>

                    {/* Menü butonu */}
                    <Button
                        onClick={handleReset}
                        // startIcon={<MenuBookIcon />}
                        sx={{
                            backgroundColor: "#DEC39B",
                            textTransform: "none",
                            fontWeight: "bold",
                            color: "#454039",
                            boxShadow: "0px 0px 4px rgba(222, 195, 155, 1)",
                            height: "60px",
                            width: "150px",
                            fontSize: "19px",
                        }}
                    >
                        Menu
                    </Button>

                </Box>


                {/* türkçe ve ingilizce dil seçenekleri */}
                <Box sx={{ p: 3, display: "flex", justifyContent: "flex-start", gap: 2 }}>

                    {/* Türkçe */}
                    <Box
                        onClick={() => handleLanguageChange("TR")}
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 0.5,
                            width: "70px",
                            height: "60px",
                            borderRadius: 2,
                            cursor: "pointer",
                            backgroundColor: "#3a312a",
                            border: language === "TR" ? "2px solid #DEC39B" : "2px solid transparent",
                            boxShadow: language === "TR"
                                ? "0px 0px 6px rgba(222, 195, 155, 0.9)"
                                : "none",
                            transition: "all 0.25s",
                            "&:hover": {
                                boxShadow: "0px 0px 6px rgba(222, 195, 155, 0.5)",
                            },
                        }}
                    >
                        <img
                            src={tr_flag}
                            alt="TR"
                            style={{ width: "40px", height: "27px", objectFit: "cover" }}
                        />
                    </Box>

                    {/* İngilizce */}
                    <Box
                        onClick={() => handleLanguageChange("EN")}
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 0.5,
                            width: "70px",
                            height: "60px",
                            borderRadius: 2,
                            cursor: "pointer",
                            backgroundColor: "#3a312a",
                            border: language === "EN" ? "2px solid #DEC39B" : "2px solid transparent",
                            boxShadow: language === "EN"
                                ? "0px 0px 6px rgba(222, 195, 155, 0.9)"
                                : "none",
                            transition: "all 0.25s",
                            "&:hover": {
                                boxShadow: "0px 0px 6px rgba(222, 195, 155, 0.5)",
                            },
                        }}
                    >
                        <img
                            src={en_flag}
                            alt="EN"
                            style={{ width: "40px", height: "27px", objectFit: "cover" }}
                        />
                    </Box>

                </Box>

            </Box>

            {/* ─── İçerik ─── */}
            <Box sx={{
                width: "100%",
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
            }}>
                {/* Kategori seçim ekranı */}
                {!coffee_page && !chocolate_page && (
                    beverages?.categories?.filter((data => data.type === "coffee")).map((categories) => (
                        <Box
                            component="button"
                            onClick={() => handlePageSelect(categories)}
                            key={categories?.id}
                            sx={{
                                border: "1px solid #DEC39B",
                                borderRadius: 2,
                                width: { xs: "250px", sm: "280px", md: "300px", lg: "320px", xl: "350px" },
                                height: { xs: "180px", sm: "200px", md: "220px" },
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                marginBottom: 2,
                                cursor: "pointer",
                                backgroundColor: "#454039",
                                boxShadow: "0 0 8px rgba(222, 195, 155, 1)",
                                transition: "transform 0.2s, box-shadow 0.2s",
                                "&:hover": { transform: "translateY(-2px)" },
                            }}
                        >
                            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
                                <img
                                    src={categories.type === "coffee" ? coffee : ice_cream}
                                    alt={categories.name}
                                    style={{ width: "150px", height: "110px" }}
                                />
                                <Typography fontSize="26px">{categories.name}</Typography>
                            </Box>
                        </Box>
                    ))
                )}

                {/* Coffee listesi */}
                {coffee_page && (() => {
                    const coffeeList = beverages?.drinks.filter(i => i?.type === "coffee");
                    return renderPage(coffeeList, "Coffee List");
                })()}

                {/* Ice Cream listesi */}
                {/* {chocolate_page && (() => {
                    const chocolateList = beverages?.iceCreams.filter(i => i?.type === "ice_cream");
                    return renderPage(chocolateList, "Ice Cream List");
                })()} */}
            </Box>


            {/* CARD */}
            <Box sx={{ height: "100px", display: "flex", justifyContent: "center", gap: 2 }}>

                {
                    Object.keys(cart).length > 0 ?

                        <Chip
                            icon={
                                <Badge badgeContent={totalCartItems} color="error">
                                    <ShoppingCartIcon />
                                </Badge>
                            }
                            // label={`View Cart · ${totalCartItems} ürün`}
                            label={`View Cart`}
                            onClick={() => setCartOpen(true)}
                            sx={{
                                width: "350px",
                                height: "58px",
                                fontSize: "18px",
                                fontWeight: "bold",
                                backgroundColor: "#DEC39B",
                                color: "#454039",
                                px: 2,
                                borderRadius: "24px",
                                boxShadow: "0px 0px 12px rgba(222, 195, 155, 0.5)",
                                animation: totalCartItems > 0 ? "pulse 1.5s infinite" : "none",
                                "@keyframes pulse": {
                                    "0%": { boxShadow: "0 0 0 0 rgba(222, 195, 155, 0.7)" },
                                    "70%": { boxShadow: "0 0 0 10px rgba(222, 195, 155, 0)" },
                                    "100%": { boxShadow: "0 0 0 0 rgba(222, 195, 155, 0)" },
                                },
                                "&:hover": { backgroundColor: "#cdb080" },
                            }}
                        />
                        :
                        <Button
                            fullWidth
                            onClick={() => setCartOpen(true)}
                            // disabled={Object.keys(cart).length > 0 ? false : true}
                            startIcon={
                                <Badge badgeContent={totalCartItems} color="error">
                                    <ShoppingCartIcon />
                                </Badge>
                            }
                            sx={{
                                // backgroundColor: "#DEC39B",
                                backgroundColor: "#3A312A",
                                textTransform: "none",
                                fontWeight: "bold",
                                // color: "#454039",
                                color: "#BFC6C4",
                                // boxShadow: "0px 0px 4px rgba(222, 195, 155, 1)",
                                fontSize: "16px",
                            }}
                        >
                            Cart is empty.
                        </Button>
                }

            </Box>


            {/* ─── Sepet Drawer (sağdan açılır) ─── */}
            <Drawer
                anchor="right"
                open={cartOpen}
                onClose={() => setCartOpen(false)}
                PaperProps={{
                    sx: {
                        width: { xs: "85vw", sm: "50%" },
                        backgroundColor: "#2e2720",
                        color: "#E7D9CF",
                        p: 2,
                        display: "flex",
                        flexDirection: "column", // ← içeriği dikey sırala
                    },
                }}
            >
                {/* Drawer başlık */}
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, p: 1 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <ShoppingCartIcon sx={{ color: "#DEC39B" }} />
                        <Typography fontSize={20} fontWeight="bold" color="#DEC39B">
                            Sepet
                        </Typography>
                    </Box>
                    <IconButton onClick={() => setCartOpen(false)} sx={{ color: "#DEC39B" }}>
                        <CloseIcon />
                    </IconButton>
                </Box>

                <Divider sx={{ borderColor: "rgba(222,195,155,0.3)", mb: 2 }} />

                {/* Kaydırılabilir içerik alanı */}
                <Box sx={{ flex: 1, overflowY: "auto", p: 1 }}>

                    {Object.keys(cart).length === 0 ? (
                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mt: 6, gap: 2, opacity: 0.5 }}>
                            <ShoppingCartIcon sx={{ fontSize: 60, color: "#DEC39B" }} />
                            <Typography>Sepet boş</Typography>
                        </Box>
                    ) : (
                        Object.values(cart).map((item) => (
                            <Box
                                key={item.cartKey}
                                sx={{
                                    py: 1.5,
                                    px: 1.5,
                                    mb: 1.5,
                                    borderRadius: 2,
                                    backgroundColor: "#3a312a",
                                    boxShadow: "0 1px 4px rgba(222,195,155,0.2)",
                                }}
                            >
                                {/* Üst satır: resim, isim, miktar, sil */}
                                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                                    <img src={item?.image} alt={item?.Name} style={{ width: "60px", height: "48px", objectFit: "contain" }} />

                                    {/* İsim + fiyat */}
                                    <Box sx={{ flex: 1, px: 1.5 }}>
                                        <Typography fontSize={15} fontWeight="bold" color="#E7D9CF">
                                            {item.Name}
                                        </Typography>
                                        <Typography fontSize={13} color="#FFB74D">
                                            {item.price} {currency} × {item.qty}
                                        </Typography>
                                    </Box>

                                    {/* Miktar kontrolü */}
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 2, mr: 5 }}>
                                        <IconButton
                                            size="small"
                                            onClick={() => removeFromCart(item)}
                                            sx={{ color: "#DEC39B", p: 0.5, border: "1px solid #DEC39B", borderRadius: 1 }}
                                        >
                                            <RemoveIcon fontSize="small" />
                                        </IconButton>
                                        <Typography sx={{ minWidth: "24px", textAlign: "center", fontWeight: "bold", color: "#DEC39B", fontSize: 15 }}>
                                            {item.qty}
                                        </Typography>
                                        <IconButton
                                            size="small"
                                            onClick={() => addToCart(item)}
                                            sx={{ color: "#DEC39B", p: 0.5, border: "1px solid #DEC39B", borderRadius: 1 }}
                                        >
                                            <AddIcon fontSize="small" />
                                        </IconButton>
                                    </Box>

                                    {/* Sil */}
                                    <IconButton
                                        size="small"
                                        onClick={() => deleteFromCart(item)}
                                        sx={{ color: "#c0392b", ml: 1, border: "1px solid #c0392b", borderRadius: 1, p: 0.5 }}
                                    >
                                        <DeleteOutlineIcon fontSize="small" />
                                    </IconButton>
                                </Box>

                                {/* Customize listesi */}
                                {item.customize && item.customize.length > 0 && (
                                    <Box sx={{ mt: 1, pl: 1, borderTop: "1px solid rgba(222,195,155,0.1)", pt: 1 }}>
                                        <Typography fontSize={12} color="#a08060" mb={0.5}>
                                            İlaveler:
                                        </Typography>
                                        {item.customize.map((name) => {
                                            const allExtras = [...(souces ?? []), ...(syrups ?? [])];
                                            const found = allExtras.find((e) => e.name === name);
                                            return (
                                                <Box
                                                    key={name}
                                                    sx={{
                                                        display: "flex",
                                                        justifyContent: "space-between",
                                                        alignItems: "center",
                                                        py: 0.3,
                                                    }}
                                                >
                                                    <Typography fontSize={13} color="#E7D9CF">
                                                        + {name}
                                                    </Typography>
                                                    <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                                                        <Typography fontSize={14} color={found?.price === "0,00" ? "#6b9e6b" : "#FFB74D"}>
                                                            {`${found?.price} ${currency}`}
                                                        </Typography>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => removeCustomizeFromCart(item, name)}
                                                            sx={{
                                                                p: 0.3,
                                                                color: "#c0392b",
                                                                border: "1px solid #c0392b",
                                                                borderRadius: 1,
                                                                "&:hover": { backgroundColor: "rgba(192,57,43,0.1)" },
                                                            }}
                                                        >
                                                            <CloseIcon sx={{ fontSize: "16px" }} />
                                                        </IconButton>
                                                    </Box>
                                                </Box>
                                            );
                                        })}
                                    </Box>
                                )}

                                {/* Item toplam fiyat */}
                                <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 2 }}>
                                    <Typography fontSize={16} fontWeight="bold" color="#DEC39B">
                                        Toplam: {calcItemTotal(item).toFixed(2).replace(".", ",")} {currency}
                                    </Typography>
                                </Box>
                            </Box>
                        ))
                    )}

                    {Object.keys(cart).length > 0 && (
                        <>
                            <Divider sx={{ borderColor: "rgba(222,195,155,0.3)", mt: 2, mb: 1 }} />
                            <Box sx={{ display: "flex", justifyContent: "space-between", p: 1 }}>
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>Toplam Ürün</Typography>
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>{totalCartItems}</Typography>
                            </Box>
                            <Box sx={{ display: "flex", justifyContent: "space-between", p: 1 }}>
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>Toplam Fiyat</Typography>
                                <Typography color="#FFB74D" fontWeight="bold" fontSize={20}>
                                    {totalCartPrice.toFixed(2).replace(".", ",")} {currency}
                                </Typography>
                            </Box>
                        </>
                    )}
                </Box>

                {/* Get butonu — her zaman en altta sabit */}
                <Box sx={{ pt: 2, borderTop: "1px solid rgba(222,195,155,0.3)" }}>
                    <Button
                        onClick={() => setOrderModal({ open: true, status: "preparing" })}
                        fullWidth
                        disabled={Object.keys(cart).length === 0}
                        sx={{
                            textTransform: "none",
                            letterSpacing: 3,
                            height: "50px",
                            fontSize: "24px",
                            fontWeight: "bold",
                            backgroundColor: Object.keys(cart).length === 0 ? "#3a312a" : "#F57C00",
                            color: Object.keys(cart).length === 0 ? "#a08060" : "#FFF8E1",
                            borderRadius: 2,
                            "&:hover": {
                                backgroundColor: "#E65100",
                            },
                        }}
                    >
                        Get
                    </Button>
                </Box>

            </Drawer>

            {/* ─── Order Processing Modal ─── */}
            <Processing
                orderModal={orderModal}
                setOrderModal={setOrderModal}
            />

            {/* ─── Ürün Detay & Customize Modal ─── */}
            <ProductDetail
                key={productModal.item ? `${productModal.item.type}_${productModal.item.ButtonNumber ?? productModal.item.Name}` : "closed"}
                productModal={productModal}
                setProductModal={setProductModal}
                addToCart={addToCart}
                cart={cart}
                currency={currency}
            />


        </Box>
    );
};

export default Test;
