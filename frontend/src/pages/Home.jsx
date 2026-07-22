import React from 'react'
import {
    Box, Button, Typography, IconButton, Badge,
    Divider, Drawer, Modal, LinearProgress,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import ShoppingCartIcon from "@mui/icons-material/ShoppingCart";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import CloseIcon from "@mui/icons-material/Close";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import ArrowBackIosIcon from "@mui/icons-material/ArrowBackIos";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import Chip from "@mui/material/Chip";

import { beverages, souces, syrups, buildCheckBeverageMessage, getName } from "../helper/Beverages";
import PreparingCoffee from "../components/modal/PreparingCoffee";
import Alert from "../components/modal/Alert";
import Processing from '../components/modal/Processing';
import ProductDetail from '../components/modal/ProductDetail';

import { useRef, useState, useEffect, useCallback } from "react";
import axios from "axios";

import coffee_beans from "../assets/coffee-beans.png";
import milk from "../assets/milk.png";
import coffee from "../assets/coffee.webp";
import ice_cream from "../assets/ice_cream.webp";
import tr_flag from "../assets/tr_flag.png";
import en_flag from "../assets/uk_flag.png";
import logo from "../assets/logorob_logo.png";


// ───────────────────────── Backend constants ─────────────────────────
const BACKEND_URI = "http://192.168.1.40:8000/";
const POLL_MS = 800;
const MACHINE_POLL = 1000;
const STOCK_POLL = 5000;
const ROBOT_POLL = 2000;
const MAX_QTY = 5;

const buildStartMessage = (beverage) => ({
    function: "startBeverage",
    a_iBtnNbr: String(beverage.ButtonNumber),
    a_iBarista: "1", a_iDecaf: "0", a_iSML: "1",
    a_iMilktype: "-1", a_iSirupType: "0", a_iSirupSML: "1",
    a_iBeanPortioner: "0", a_iCupSizeAdj: "100",
});

const buildCheckMessage = (beverage) => ({
    function: "checkBeverage",
    a_iBtnNbr: String(beverage.ButtonNumber),
    a_iBarista: "1", a_iDecaf: "0", a_iSML: "1",
    a_iMilktype: "-1", a_iSirupType: "0", a_iSirupSML: "1",
});


// ───────────────────────── Stok Uyarı Modal ─────────────────────────
const StockAlertModal = ({ open, alerts }) => (
    <Modal open={open} disableEscapeKeyDown>
        <Box sx={{
            position: "absolute", top: "50%", left: "50%",
            transform: "translate(-50%,-50%)",
            width: { xs: "92%", sm: 460 },
            backgroundColor: "#2e2720",
            border: "1px solid #DEC39B",
            borderRadius: 3,
            boxShadow: "0 24px 64px rgba(0,0,0,0.7)",
            p: 4, outline: "none",
        }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 2 }}>
                <WarningAmberIcon sx={{ color: "#DEC39B", fontSize: 28 }} />
                <Typography fontWeight={700} fontSize={17} color="#DEC39B">
                    Sistem Kullanılamıyor
                </Typography>
            </Box>
            <Divider sx={{ mb: 2.5, borderColor: "rgba(222,195,155,0.3)" }} />
            {alerts.map((a, i) => (
                <Box key={i} sx={{
                    p: 1.5, borderRadius: 2, mb: 1.5,
                    backgroundColor: "rgba(192,57,43,0.15)",
                    border: "1px solid rgba(192,57,43,0.4)",
                }}>
                    <Typography variant="body2" color="#E7D9CF">⛔ {a.message}</Typography>
                </Box>
            ))}
            <Typography variant="caption" color="#a08060" mt={1} display="block">
                Stok yenileme yapın veya yöneticiyle iletişime geçin.
            </Typography>
        </Box>
    </Modal>
);


// ───────────────────────── Stok Bar ─────────────────────────
const StockBar = ({ stockStatus }) => {
    const { stock = {}, thresholds = {} } = stockStatus;
    const items = [
        { label: "Kahve", val: stock.coffee_g, max: 200, unit: "g", min: thresholds.coffee_g ?? 50 },
        { label: "Süt", val: stock.milk_ml, max: 5000, unit: "ml", min: thresholds.milk_ml ?? 350 },
        { label: "Çikolata", val: stock.choc_g, max: 150, unit: "g", min: thresholds.choc_g ?? 50 },
        { label: "Bardak", val: stock.cups, max: 70, unit: "adet", min: thresholds.cups ?? 2 },
    ];
    return (
        <Box sx={{
            display: "flex", gap: { xs: 2, sm: 4 },
            px: { xs: 2, md: 4 }, py: 1.5,
            backgroundColor: "#3a312a",
            borderBottom: "1px solid rgba(222,195,155,0.3)",
            flexWrap: "wrap",
        }}>
            {items.map((item) => {
                const v = item.val ?? 0;
                const pct = Math.min(100, Math.max(0, (v / item.max) * 100));
                const isCrit = v <= item.min;
                const isWarn = v <= item.min * 2 && !isCrit;
                const color = isCrit ? "#c0392b" : isWarn ? "#F57C00" : "#6b9e6b";
                return (
                    <Box key={item.label} sx={{ minWidth: 90, flex: "1 1 90px" }}>
                        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                            <Typography fontSize={11} fontWeight={500} color="#a08060">{item.label}</Typography>
                            <Typography fontSize={11} fontWeight={isCrit ? 700 : 400}
                                color={isCrit ? "#c0392b" : isWarn ? "#F57C00" : "#a08060"}>
                                {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(0)) : "?"} {item.unit}
                            </Typography>
                        </Box>
                        <Box sx={{ height: 3, borderRadius: 2, backgroundColor: "rgba(222,195,155,0.2)", overflow: "hidden" }}>
                            <Box sx={{
                                height: "100%", width: `${pct}%`, backgroundColor: color,
                                borderRadius: 2, transition: "width 0.6s ease",
                            }} />
                        </Box>
                    </Box>
                );
            })}
        </Box>
    );
};


// ───────────────────────── ANA BİLEŞEN ─────────────────────────
const Home = () => {

    // ── Sepet (Tek Ürün Modu — Test.jsx mantığı) ──
    const [cart, setCart] = useState({});
    const [cartOpen, setCartOpen] = useState(false);

    const currency = "₺";

    // ── Kategori / sayfalama (Test.jsx) ──
    const [coffee_page, setCoffee_page] = useState(false);
    const [chocolate_page, setChocolate_page] = useState(false);
    const [coffeeIndex, setCoffeeIndex] = useState(0);
    const itemsPerPage = 3;
    const [language, setLanguage] = useState("TR");

    // ── Ürün Detay Modal ──
    const [productModal, setProductModal] = useState({ open: false, item: null });

    // ── Backend state'leri (Home.jsx orijinal) ──
    const [machine, setMachine] = useState({ online: false, has_blocking_error: false, errors: [], cleaning: null });
    const [machineLoading, setMachineLoading] = useState(true);
    const [machineErr, setMachineErr] = useState(null);

    const [stockStatus, setStockStatus] = useState({
        stock: { coffee_g: 999, milk_ml: 9999, choc_g: 999, cups: 99 },
        thresholds: { coffee_g: 50, milk_ml: 350, choc_g: 50, cups: 2 },
        status: { overall: "ok", all_disabled: false, milk_disabled: false, choc_disabled: false },
        alerts: [],
    });

    const [robotStatus, setRobotStatus] = useState({
        connected: false, robot_mode: null, robot_state: null,
        mode_label: "disconnected", state_label: "disconnected", can_order: false,
    });
    const [robotLoading, setRobotLoading] = useState(true);

    const [orderQueue, setOrderQueue] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [totalItems, setTotalItems] = useState(0);
    const [progress, setProgress] = useState({ jobId: null, status: null, rcpState: null, phase: null, error: null });
    const [preparingOpen, setPreparingOpen] = useState(false);
    const [alertData, setAlertData] = useState({ title: "", message: "", code: null });
    const [alertOpen, setAlertOpen] = useState(false);

    const timerRef = useRef(null);
    const stockTimerRef = useRef(null);
    const robotTimerRef = useRef(null);
    const pollRef = useRef(null);
    const isProcessingRef = useRef(false);
    const touchStartX = useRef(null);


    // ───────────────────── Polling ─────────────────────
    const fetchMachineStatus = async () => {
        try {
            const res = await axios.get(`${BACKEND_URI}machine/status`, { timeout: 4000 });
            setMachine(res.data); setMachineErr(null);
        } catch { setMachineErr("Makine durumu alınamadı."); }
        finally { setMachineLoading(false); }
    };
    useEffect(() => {
        fetchMachineStatus();
        timerRef.current = setInterval(fetchMachineStatus, MACHINE_POLL);
        return () => clearInterval(timerRef.current);
    }, []);

    const fetchStockStatus = useCallback(async () => {
        try {
            const res = await axios.get(`${BACKEND_URI}stock/status`, { timeout: 4000 });
            setStockStatus(res.data);
        } catch { }
    }, []);
    useEffect(() => {
        fetchStockStatus();
        stockTimerRef.current = setInterval(fetchStockStatus, STOCK_POLL);
        return () => clearInterval(stockTimerRef.current);
    }, [fetchStockStatus]);

    const fetchRobotStatus = useCallback(async () => {
        try {
            const res = await axios.get(`${BACKEND_URI}robot/status`, { timeout: 3000 });
            setRobotStatus(res.data);
        } catch { setRobotStatus((p) => ({ ...p, connected: false, can_order: false })); }
        finally { setRobotLoading(false); }
    }, []);
    useEffect(() => {
        fetchRobotStatus();
        robotTimerRef.current = setInterval(fetchRobotStatus, ROBOT_POLL);
        return () => clearInterval(robotTimerRef.current);
    }, [fetchRobotStatus]);

    useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);


    // ───────────────────── Durum hesapla ─────────────────────
    const { all_disabled: allDisabled, milk_disabled: milkDisabled, choc_disabled: chocDisabled } =
        stockStatus.status || {};
    const critAlerts = (stockStatus.alerts || []).filter((a) => a.type === "critical");

    const isBeverageDisabled = (b) => {
        if (allDisabled) return true;
        if (milkDisabled && b?.milk) return true;
        if (chocDisabled && b?.milkChocolate) return true;
        return false;
    };

    const canOrder = (
        machine.online &&
        !machine.has_blocking_error &&
        !machine.cleaning &&
        !allDisabled &&
        robotStatus.can_order
    );


    // ───────────────────── Cart helpers (Tek Ürün Modu) ─────────────────────
    const SINGLE_CART_KEY = "current_order";

    const parsePrice = (priceStr) => parseFloat((priceStr ?? "0").replace(",", ".")) || 0;

    const calcItemTotal = (item) => {
        const basePrice = parsePrice(item.price);
        const customizePrice = (item.customize ?? []).reduce((sum, name) => {
            const allExtras = [...(souces ?? []), ...(syrups ?? [])];
            const found = allExtras.find((e) => (e[`name_${language}`] ?? e.name) === name || e.name_TR === name || e.name_EN === name || e.name === name);
            return sum + parsePrice(found?.price);
        }, 0);
        return (basePrice + customizePrice) * item.qty;
    };

    const totalCartItems = Object.values(cart).reduce((sum, i) => sum + i.qty, 0);
    const totalCartPrice = Object.values(cart).reduce((sum, i) => sum + calcItemTotal(i), 0);

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

    const deleteFromCart = () => { setCart({}); };

    const clearCart = () => { setCart({}); setCartOpen(false); };

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


    // ───────────────────── Sipariş işlemleri (Home.jsx orijinal) ─────────────────────
    const buildQueueDisplay = (items) => {
        const d = [];
        items.forEach(({ beverage, qty }) => {
            for (let i = 0; i < qty; i++) d.push({ name: beverage.Name, qty: 1 });
        });
        return d;
    };

    const stopPolling = () => {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };

    const startPolling = (jobId, onDone, onError) => {
        stopPolling();
        pollRef.current = setInterval(async () => {
            try {
                const res = await axios.get(`${BACKEND_URI}order/status/${jobId}`);
                const { status, rcp_state, phase, error } = res.data;
                setProgress((prev) => ({
                    ...prev, jobId, status,
                    rcpState: rcp_state ?? prev.rcpState,
                    phase: phase ?? prev.phase,
                    error: error ?? null,
                }));
                if (status === "done" || phase === "robot_delivered") { stopPolling(); onDone(); }
                else if (status === "error" || status === "timeout") { stopPolling(); onError(error || "Bilinmeyen hata"); }
            } catch { stopPolling(); onError("Job status okunamadı."); }
        }, POLL_MS);
    };

    const orderSingleBeverage = (beverage) =>
        new Promise(async (resolve, reject) => {
            try {
                const checkRes = await axios.post(
                    `${BACKEND_URI}check_beverage`,
                    { message: buildCheckMessage(beverage) },
                    { headers: { "Content-Type": "application/json" } }
                );
                const result = checkRes.data?.result;
                const detail = checkRes.data?.machine_error_detail;
                if (!result || result.returnvalue !== 0) {
                    return reject(detail
                        ? `${buildCheckBeverageMessage(result)}\nMakine: ${detail}`
                        : buildCheckBeverageMessage(result));
                }
                const endpoint = "order_standart";
                let retryCount = 0, orderRes;
                while (retryCount <= 3) {
                    try {
                        orderRes = await axios.post(
                            `${BACKEND_URI}${endpoint}`,
                            { message: buildStartMessage(beverage) },
                            { headers: { "Content-Type": "application/json" } }
                        );
                        break;
                    } catch (axiosErr) {
                        if (axiosErr?.response?.status === 409 && retryCount < 3) {
                            retryCount++;
                            await new Promise((r) => setTimeout(r, 2000));
                        } else throw axiosErr;
                    }
                }
                const jobId = orderRes?.data?.job_id;
                if (!jobId) return reject("Backend job_id döndürmedi.");
                setProgress((prev) => ({ ...prev, jobId, status: "running", rcpState: null, phase: null, error: null }));
                startPolling(jobId, resolve, reject);
            } catch (err) { reject(err?.response?.data?.detail || err?.message || "Bağlantı hatası."); }
        });

    const processQueue = useCallback(async (items) => {
        if (isProcessingRef.current) return;
        isProcessingRef.current = true;
        const flat = [];
        items.forEach(({ beverage, qty }) => {
            for (let i = 0; i < qty; i++) flat.push(beverage);
        });
        setTotalItems(flat.length);
        setCurrentIndex(0);
        setOrderQueue(buildQueueDisplay(items));
        setPreparingOpen(true);
        clearCart();
        for (let i = 0; i < flat.length; i++) {
            setCurrentIndex(i);
            setProgress({ jobId: null, status: "running", rcpState: null, phase: null, error: null });
            try { await orderSingleBeverage(flat[i]); fetchStockStatus(); }
            catch (errMsg) {
                setProgress((prev) => ({ ...prev, status: "error", error: errMsg }));
                setAlertData({ title: `Sipariş Hatası (${i + 1}/${flat.length})`, message: String(errMsg), code: null });
                setAlertOpen(true);
                isProcessingRef.current = false;
                return;
            }
        }
        setProgress((prev) => ({ ...prev, status: "done" }));
        fetchStockStatus();
        isProcessingRef.current = false;
    }, [fetchStockStatus]); // eslint-disable-line

    const handlePreparingClose = () => {
        if (isProcessingRef.current) return;
        stopPolling();
        setPreparingOpen(false);
        setProgress({ jobId: null, status: null, rcpState: null, phase: null, error: null });
        setOrderQueue([]); setCurrentIndex(0); setTotalItems(0);
    };

    const handlePlaceOrder = () => {
        if (!canOrder || totalCartItems === 0 || isProcessingRef.current) return;
        // Tek ürün modunda sepetteki ürünleri queue formatına çevir
        const queueItems = Object.values(cart).map((item) => ({
            beverage: item,
            qty: item.qty,
        }));
        setCartOpen(false);
        processQueue(queueItems);
    };


    // ───────────────────── Touch handlers ─────────────────────
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


    // ───────────────────── Sayfa / Dil ─────────────────────
    const handleReset = () => {
        setCoffee_page(false);
        setChocolate_page(false);
        setCoffeeIndex(0);
    };

    const handlePageSelect = (data) => {
        data?.type === "coffee" && setCoffee_page(true);
        data?.type === "ice_cream" && setChocolate_page(true);
    };

    const handleLanguageChange = (lang) => {
        setLanguage(lang);
    };


    // ───────────────────── renderCards ─────────────────────
    const renderCards = (list) =>
        list
            .map((item) => {
                const currentInCart = cart[SINGLE_CART_KEY];
                const baseKey = `${item.type}_${item.ButtonNumber ?? item.Name}`;
                const inCart = currentInCart &&
                    `${currentInCart.type}_${currentInCart.ButtonNumber ?? currentInCart.Name}` === baseKey;
                const itemQty = inCart ? currentInCart.qty : 0;

                const disabled = isBeverageDisabled(item);

                return (
                    <Box
                        key={baseKey}
                        onClick={() => {
                            if (disabled) return;
                            const existingCustomize = inCart ? (currentInCart.customize ?? []) : [];
                            setProductModal({
                                open: true,
                                item: { ...item, customize: existingCustomize },
                            });
                        }}
                        sx={{
                            border: inCart ? "1px solid #42a5f5" : "1px solid #DEC39B",
                            borderRadius: 2,
                            width: "100%",
                            height: { xs: "260px", sm: "290px", md: "320px" },
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexDirection: "column",
                            gap: 2,
                            marginBottom: 2,
                            backgroundColor: "#454039",
                            cursor: disabled ? "not-allowed" : "pointer",
                            opacity: disabled ? 0.5 : 1,
                            boxShadow: inCart
                                ? "0 0 12px rgba(66, 165, 245, 0.85)"
                                : "0 2px 8px rgba(222, 195, 155, 1)",
                            transition: "transform 0.2s, box-shadow 0.3s",
                            "&:hover": !disabled && { transform: "translateY(-2px)" },
                            position: "relative",
                        }}
                    >
                        {disabled && (
                            <Box sx={{
                                position: "absolute", top: 8, right: 8,
                                bgcolor: "rgba(192,57,43,0.2)",
                                border: "1px solid #c0392b",
                                borderRadius: "12px", px: 1, py: 0.3,
                            }}>
                                <Typography fontSize={10} color="#c0392b" fontWeight={700}>{language === "EN" ? "Out of stock" : "Stok yok"}</Typography>
                            </Box>
                        )}

                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
                            <Badge
                                badgeContent={itemQty}
                                color="error"
                                sx={{
                                    "& .MuiBadge-badge": {
                                        fontSize: "18px",
                                        height: "32px",
                                        minWidth: "33px",
                                        borderRadius: "14px",
                                        padding: "0 6px",
                                    },
                                }}
                            >
                                <img src={item?.image} alt={getName(item, language)} style={{ width: "100px", height: "85px" }} />
                            </Badge>
                            <Typography
                                fontSize={"24px"}
                                align='center'
                                color='#E7D9CF'
                                sx={{ textShadow: "0 0px 2px rgba(222, 195, 155, 1)", letterSpacing: "1px" }}
                            >
                                {getName(item, language)}
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

                        {/* Ürün etiketleri (Sütlü/Sütsüz, Kafein) */}
                        <Box sx={{ display: "flex", gap: 0.75 }}>
                            <Box sx={{
                                display: "flex", alignItems: "center", gap: 0.4,
                                bgcolor: "#3a312a", borderRadius: "6px", px: 0.75, py: 0.3,
                            }}>
                                <img src={milk} alt="" style={{ width: 11, height: 11 }} />
                                <Typography fontSize={9} color="#a08060" fontWeight={500}>
                                    {item.milk ? (language === "EN" ? "With Milk" : "Sütlü") : (language === "EN" ? "No Milk" : "Sütsüz")}
                                </Typography>
                            </Box>
                            <Box sx={{
                                display: "flex", alignItems: "center", gap: 0.4,
                                bgcolor: "#3a312a", borderRadius: "6px", px: 0.75, py: 0.3,
                            }}>
                                <img src={coffee_beans} alt="" style={{ width: 11, height: 11 }} />
                                <Typography fontSize={9} color="#a08060" fontWeight={500}>
                                    {item.milkChocolate ? (language === "EN" ? "Decaf" : "Kahvesiz") : (item[`caffeine_${language}`] ?? item.caffeine ?? "—")}
                                </Typography>
                            </Box>
                        </Box>

                        {/* Remove butonu (sepette varsa) */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            {inCart && (
                                <IconButton
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeFromCart();
                                    }}
                                    sx={{
                                        width: "40px",
                                        height: "40px",
                                        backgroundColor: "#6b3a2a",
                                        color: "#E7D9CF",
                                        borderRadius: 1,
                                        padding: 0,
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


    // ───────────────────── renderPage ─────────────────────
    const renderPage = (list, title) => {
        return (
            <Box sx={{ width: "100%", px: { xs: 2, sm: 3, md: 4 } }}>
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
                <Box sx={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                    gap: { xs: 2, sm: 2.5, md: 3 },
                    justifyItems: "center",
                    width: "100%",
                }}>
                    {renderCards(list)}
                </Box>
            </Box>
        );
    };


    // ───────────────────── Makine durum ekranları ─────────────────────
    const fullscreen = (msg, color = "#a08060") => (
        <Box sx={{
            minHeight: "100vh", backgroundColor: "#2e2720",
            display: "flex", alignItems: "center", justifyContent: "center",
        }}>
            <Typography fontSize={17} fontWeight={600} color={color} textAlign="center" px={3}>{msg}</Typography>
        </Box>
    );
    if (machineLoading) return fullscreen(language === "EN" ? "Checking machine status..." : "Makine durumu kontrol ediliyor...");
    if (machineErr) return fullscreen(`${language === "EN" ? "Connection error" : "Bağlantı hatası"}: ${machineErr}`, "#F57C00");
    if (!machine.online) return fullscreen(language === "EN" ? "Coffee machine is offline." : "Kahve makinesi çevrimdışı.", "#c0392b");
    if (machine.has_blocking_error) return fullscreen(language === "EN" ? "Coffee machine is unavailable." : "Kahve makinesi kullanılamıyor.", "#c0392b");
    if (machine.cleaning) return fullscreen(language === "EN" ? "Coffee machine is in cleaning mode." : "Kahve makinesi temizlik modunda.");


    // ───────────────────── RENDER ─────────────────────
    return (
        <Box sx={{ minHeight: "100vh", backgroundColor: "#2e27207a", display: "flex", flexDirection: "column" }}>

            {/* <StockAlertModal open={allDisabled && critAlerts.length > 0} alerts={critAlerts} /> */}

            {/* ── Header (logo + menü + diller) ── */}
            <Box sx={{
                display: "flex",
                justifyContent: "space-evenly",
                alignItems: "center",
            }}>

                <Box sx={{ p: 3 }}>
                    <img src={logo} alt="Logo" style={{ width: "120px", objectFit: "cover" }} />
                </Box>

                <Box sx={{ p: 3, display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
                    <Button
                        onClick={handleReset}
                        sx={{
                            backgroundColor: (!robotLoading && !robotStatus.can_order) ? "#c0392b" : "#DEC39B",
                            textTransform: "none",
                            fontWeight: "bold",
                            color: (!robotLoading && !robotStatus.can_order) ? "#ffffff" : "#454039",
                            boxShadow: (!robotLoading && !robotStatus.can_order)
                                ? "0px 0px 8px rgba(192,57,43,0.8)"
                                : "0px 0px 4px rgba(222, 195, 155, 1)",
                            height: "60px",
                            width: "150px",
                            fontSize: "19px",
                            transition: "background-color 0.3s, color 0.3s",
                        }}
                    >
                        Menu
                    </Button>
                    {!robotLoading && robotStatus.mode_label === "manual" && (
                        <Typography fontSize={11} fontWeight={600} color="#c0392b" textAlign="center">
                            {language === "EN" ? "Robot in manual mode" : "Robot manuel modda"}
                        </Typography>
                    )}
                </Box>

                <Box sx={{ p: 3, display: "flex", justifyContent: "flex-start", gap: 2 }}>
                    <Box
                        onClick={() => handleLanguageChange("TR")}
                        sx={{
                            display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center",
                            gap: 0.5, width: "70px", height: "60px",
                            borderRadius: 2, cursor: "pointer",
                            backgroundColor: "#3a312a",
                            border: language === "TR" ? "2px solid #DEC39B" : "2px solid transparent",
                            boxShadow: language === "TR" ? "0px 0px 6px rgba(222, 195, 155, 0.9)" : "none",
                            transition: "all 0.25s",
                            "&:hover": { boxShadow: "0px 0px 6px rgba(222, 195, 155, 0.5)" },
                        }}
                    >
                        <img src={tr_flag} alt="TR" style={{ width: "40px", height: "27px", objectFit: "cover" }} />
                    </Box>

                    <Box
                        onClick={() => handleLanguageChange("EN")}
                        sx={{
                            display: "flex", flexDirection: "column",
                            alignItems: "center", justifyContent: "center",
                            gap: 0.5, width: "70px", height: "60px",
                            borderRadius: 2, cursor: "pointer",
                            backgroundColor: "#3a312a",
                            border: language === "EN" ? "2px solid #DEC39B" : "2px solid transparent",
                            boxShadow: language === "EN" ? "0px 0px 6px rgba(222, 195, 155, 0.9)" : "none",
                            transition: "all 0.25s",
                            "&:hover": { boxShadow: "0px 0px 6px rgba(222, 195, 155, 0.5)" },
                        }}
                    >
                        <img src={en_flag} alt="EN" style={{ width: "40px", height: "27px", objectFit: "cover" }} />
                    </Box>
                </Box>
            </Box>

            {/* ── Stok Bar ── */}
            {/* StockBar gizlendi */}

            {/* Robot uyarısı Menu butonuna taşındı */}
            {milkDisabled && !allDisabled && (
                <Box sx={{
                    mx: { xs: 2, md: 4 }, mt: 1, p: 1.25, borderRadius: "8px",
                    backgroundColor: "rgba(245,124,0,0.15)", border: "1px solid rgba(245,124,0,0.4)",
                }}>
                    <Typography fontSize={12} fontWeight={600} color="#F57C00">
                        {language === "EN" ? "⚠ Milk level low — milk drinks disabled" : "⚠ Süt miktarı düşük — sütlü içecekler devre dışı"}
                    </Typography>
                </Box>
            )}
            {chocDisabled && !allDisabled && (
                <Box sx={{
                    mx: { xs: 2, md: 4 }, mt: 0.75, p: 1.25, borderRadius: "8px",
                    backgroundColor: "rgba(245,124,0,0.15)", border: "1px solid rgba(245,124,0,0.4)",
                }}>
                    <Typography fontSize={12} fontWeight={600} color="#F57C00">
                        {language === "EN" ? "⚠ Chocolate level low — chocolate drinks disabled" : "⚠ Çikolata miktarı düşük — çikolatalı içecekler devre dışı"}
                    </Typography>
                </Box>
            )}

            {/* ── İçerik: Kategori seçim veya ürün listesi ── */}
            <Box sx={{
                width: "100%",
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                overflowY: "auto",
            }}>
                {/* Kategori seçim */}
                {!coffee_page && !chocolate_page && (
                    beverages?.categories?.filter((data) => data?.type === "coffee")
                    .map((categories) => (
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
                                <Typography fontSize="26px" color="#E7D9CF">{categories[`name_${language}`] ?? categories.name}</Typography>
                            </Box>
                        </Box>
                    ))
                )}

                {/* Coffee listesi */}
                {coffee_page && (() => {
                    const coffeeList = beverages?.drinks?.filter(i => i?.type === "coffee") ?? [];
                    return renderPage(coffeeList, language === "TR" ? "Kahve Listesi" : "Coffee List");
                })()}

                {/* Ice Cream listesi */}
                {chocolate_page && (() => {
                    const iceList = beverages?.iceCreams?.filter(i => i?.type === "ice_cream") ?? [];
                    return renderPage(iceList, language === "TR" ? "Dondurma Listesi" : "Ice Cream List");
                })()}
            </Box>

            {/* ── Sepet butonu (Chip / Disabled) ── */}
            <Box sx={{ height: "100px", display: "flex", justifyContent: "center", alignItems: "center", gap: 2 }}>
                {Object.keys(cart).length > 0 ? (
                    <Chip
                        icon={
                            <Badge badgeContent={totalCartItems} color="error">
                                <ShoppingCartIcon />
                            </Badge>
                        }
                        label={language === "TR" ? "Sepeti Gör" : "View Cart"}
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
                ) : (
                    <Button
                        startIcon={
                            <Badge badgeContent={totalCartItems} color="error">
                                <ShoppingCartIcon />
                            </Badge>
                        }
                        sx={{
                            backgroundColor: "#3A312A",
                            textTransform: "none",
                            fontWeight: "bold",
                            color: "#BFC6C4",
                            fontSize: "16px",
                            width: "350px",
                            height: "58px",
                            borderRadius: "24px",
                        }}
                    >
                        {language === "TR" ? "Sepet boş." : "Cart is empty."}
                    </Button>
                )}
            </Box>

            {/* ── Sepet Drawer ── */}
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
                        flexDirection: "column",
                    },
                }}
            >
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, p: 1 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <ShoppingCartIcon sx={{ color: "#DEC39B" }} />
                        <Typography fontSize={20} fontWeight="bold" color="#DEC39B">{language === "EN" ? "Cart" : "Sepet"}</Typography>
                    </Box>
                    <IconButton onClick={() => setCartOpen(false)} sx={{ color: "#DEC39B" }}>
                        <CloseIcon />
                    </IconButton>
                </Box>

                <Divider sx={{ borderColor: "rgba(222,195,155,0.3)", mb: 2 }} />

                <Box sx={{ flex: 1, overflowY: "auto", p: 1 }}>
                    {Object.keys(cart).length === 0 ? (
                        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mt: 6, gap: 2, opacity: 0.5 }}>
                            <ShoppingCartIcon sx={{ fontSize: 60, color: "#DEC39B" }} />
                            <Typography>{language === "EN" ? "Cart is empty" : "Sepet boş"}</Typography>
                        </Box>
                    ) : (
                        Object.values(cart).map((item) => (
                            <Box
                                key={item.cartKey}
                                sx={{
                                    py: 1.5, px: 1.5, mb: 1.5, borderRadius: 2,
                                    backgroundColor: "#3a312a",
                                    boxShadow: "0 1px 4px rgba(222,195,155,0.2)",
                                }}
                            >
                                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                                    <img src={item?.image} alt={getName(item, language)} style={{ width: "60px", height: "48px", objectFit: "contain" }} />

                                    <Box sx={{ flex: 1, px: 1.5 }}>
                                        <Typography fontSize={15} fontWeight="bold" color="#E7D9CF">{getName(item, language)}</Typography>
                                        <Typography fontSize={13} color="#FFB74D">
                                            {item.price} {currency} × {item.qty}
                                        </Typography>
                                    </Box>

                                    <Box sx={{ display: "flex", alignItems: "center", gap: 2, mr: 5 }}>
                                        <IconButton
                                            size="small"
                                            onClick={removeFromCart}
                                            sx={{ color: "#DEC39B", p: 0.5, border: "1px solid #DEC39B", borderRadius: 1 }}
                                        >
                                            <RemoveIcon fontSize="small" />
                                        </IconButton>
                                        <Typography sx={{
                                            minWidth: "24px", textAlign: "center",
                                            fontWeight: "bold", color: "#DEC39B", fontSize: 15,
                                        }}>
                                            {item.qty}
                                        </Typography>
                                        <IconButton
                                            size="small"
                                            onClick={() => {
                                                // qty artırma — aynı ürünün miktarını 1 artır
                                                if (item.qty < MAX_QTY) {
                                                    setCart((prev) => ({
                                                        [SINGLE_CART_KEY]: {
                                                            ...prev[SINGLE_CART_KEY],
                                                            qty: prev[SINGLE_CART_KEY].qty + 1,
                                                        },
                                                    }));
                                                }
                                            }}
                                            disabled={item.qty >= MAX_QTY}
                                            sx={{ color: "#DEC39B", p: 0.5, border: "1px solid #DEC39B", borderRadius: 1 }}
                                        >
                                            <AddIcon fontSize="small" />
                                        </IconButton>
                                    </Box>

                                    <IconButton
                                        size="small"
                                        onClick={deleteFromCart}
                                        sx={{ color: "#c0392b", ml: 1, border: "1px solid #c0392b", borderRadius: 1, p: 0.5 }}
                                    >
                                        <DeleteOutlineIcon fontSize="small" />
                                    </IconButton>
                                </Box>

                                {item.customize && item.customize.length > 0 && (
                                    <Box sx={{ mt: 1, pl: 1, borderTop: "1px solid rgba(222,195,155,0.1)", pt: 1 }}>
                                        <Typography fontSize={12} color="#a08060" mb={0.5}>{language === "EN" ? "Add-ons:" : "İlaveler:"}</Typography>
                                        {item.customize.map((name) => {
                                            const allExtras = [...(souces ?? []), ...(syrups ?? [])];
                                            const found = allExtras.find((e) => e.name === name);
                                            return (
                                                <Box key={name} sx={{
                                                    display: "flex", justifyContent: "space-between",
                                                    alignItems: "center", py: 0.3,
                                                }}>
                                                    <Typography fontSize={13} color="#E7D9CF">+ {found ? (found[`name_${language}`] ?? found.name) : name}</Typography>
                                                    <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                                                        <Typography fontSize={14} color={found?.price === "0,00" ? "#6b9e6b" : "#FFB74D"}>
                                                            {`${found?.price} ${currency}`}
                                                        </Typography>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => removeCustomizeFromCart(item, name)}
                                                            sx={{
                                                                p: 0.3, color: "#c0392b",
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
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>{language === "EN" ? "Total Items" : "Toplam Ürün"}</Typography>
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>{totalCartItems}</Typography>
                            </Box>
                            <Box sx={{ display: "flex", justifyContent: "space-between", p: 1 }}>
                                <Typography color="#DEC39B" fontWeight="bold" fontSize={18}>{language === "EN" ? "Total Price" : "Toplam Fiyat"}</Typography>
                                <Typography color="#FFB74D" fontWeight="bold" fontSize={20}>
                                    {totalCartPrice.toFixed(2).replace(".", ",")} {currency}
                                </Typography>
                            </Box>
                        </>
                    )}
                </Box>

                {/* Sipariş Ver butonu — backend processQueue tetiklenir */}
                <Box sx={{ pt: 2, borderTop: "1px solid rgba(222,195,155,0.3)" }}>
                    {!canOrder && Object.keys(cart).length > 0 && (
                        <Box sx={{
                            mb: 1.5, p: 1.25, borderRadius: 1.5,
                            bgcolor: "rgba(192,57,43,0.15)", border: "1px solid rgba(192,57,43,0.4)",
                        }}>
                            <Typography fontSize={11} color="#c0392b">
                                {allDisabled ? (language === "EN" ? "Insufficient stock." : "Stok yetersiz.")
                                    : !robotStatus.can_order
                                        ? robotStatus.mode_label === "manual" ? (language === "EN" ? "Robot in manual mode." : "Robot manuel modda.") : (language === "EN" ? "Robot not ready." : "Robot hazır değil.")
                                        : (language === "EN" ? "Machine not ready." : "Makine hazır değil.")}
                            </Typography>
                        </Box>
                    )}

                    <Button
                        fullWidth
                        onClick={handlePlaceOrder}
                        disabled={!canOrder || Object.keys(cart).length === 0 || isProcessingRef.current}
                        sx={{
                            textTransform: "none",
                            letterSpacing: 3,
                            height: "50px",
                            fontSize: "24px",
                            fontWeight: "bold",
                            backgroundColor: (!canOrder || Object.keys(cart).length === 0) ? "#3a312a" : "#F57C00",
                            color: (!canOrder || Object.keys(cart).length === 0) ? "#a08060" : "#FFF8E1",
                            borderRadius: 2,
                            "&:hover": { backgroundColor: "#E65100" },
                        }}
                    >
                        {language === "EN" ? `Place Order · ${totalCartItems} items` : `Sipariş Ver · ${totalCartItems} içecek`}
                    </Button>
                </Box>
            </Drawer>

            {/* ── Ürün Detay & Customize Modal ── */}
            <ProductDetail
                key={productModal.item ? `${productModal.item.type}_${productModal.item.ButtonNumber ?? productModal.item.Name}` : "closed"}
                productModal={productModal}
                setProductModal={setProductModal}
                addToCart={addToCart}
                cart={cart}
                currency={currency}
            />

            {/* ── PreparingCoffee Modal (Hazırlanıyor) ── */}
            {/* <PreparingCoffee
                open={preparingOpen}
                handleClose={handlePreparingClose}
                rcpState={progress.rcpState}
                status={progress.status}
                phase={progress.phase}
                error={progress.error}
                queue={orderQueue}
                currentIndex={currentIndex}
                totalItems={totalItems}
            /> */}

            {/* ── Alert Modal (Hata) ── */}
            {/* <Alert
                openAlert={alertOpen}
                handleCloseAlert={() => setAlertOpen(false)}
                alertData={alertData}
                setAlertData={setAlertData}
            /> */}

        </Box>
    );
};

export default Home;
