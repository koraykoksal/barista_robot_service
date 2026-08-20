import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge, Box, Button, Chip, Divider, Drawer,
  IconButton, Stack, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ShoppingCartIcon from "@mui/icons-material/ShoppingCart";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import AcUnitIcon from "@mui/icons-material/AcUnit";

import {
  api, ENDPOINTS, POLL, errorText,
  OFFLINE_SCENARIO, OFFLINE_SERVICES, ANY_MOCKED, ALL_MOCKED, MOCKED_LABEL,
} from "../api/client";
import { BASE_URL } from "../api/client";
import { DEBUG, CATEGORIES, ENABLED_CATEGORIES } from "../api/env";
import DebugOverlay from "../components/DebugOverlay";
import {
  beverages, buildCheckBeverageMessage, getName, findExtra, extraName,
  extraChannel,
} from "../helper/Beverages";
import SystemBanner from "../components/SystemBanner";
import ProductDetail from "../components/modal/ProductDetail";
import PreparingCoffee from "../components/modal/PreparingCoffee";
import Alert from "../components/modal/Alert";
import { palette, TOUCH_MIN } from "../theme";

import coffeeCategoryImg from "../assets/hot_cup.webp";
import iceCreamCategoryImg from "../assets/ice_cream.webp";
import logo from "../assets/logorob_logo.png";
import trFlag from "../assets/tr_flag.png";
import enFlag from "../assets/uk_flag.png";

/**
 * Home — kiosk ekranı
 *
 * DEĞİŞENLER (Aşama 1):
 *   • Açık temaya taşındı; ~300 hex literal yerine tema renkleri
 *   • PreparingCoffee ve Alert YORUM SATIRINDAYDI → geri açıldı.
 *     Bu yüzden sipariş sonrası hiçbir geri bildirim görünmüyordu.
 *   • Backend adresi sabit yazılıydı → api/client.js
 *   • Sepet artık siparişin BAŞINDA değil, BAŞARILI olduğunda
 *     temizleniyor. Önceden hata alınca müşterinin seçimi de siliniyordu.
 *   • Ölü kod temizlendi: handleTouchStart/End hiçbir elemana bağlı
 *     değildi, coffeeIndex/itemsPerPage kullanılmıyordu, StockAlertModal
 *     hiç render edilmiyordu
 *   • Dokunma hedefleri büyütüldü (40px → 56px+)
 *   • Sipariş tamamlanınca ekran kendiliğinden yeni siparişe hazır hale
 *     geliyor (ORDER_STATE makinesi)
 *
 * NOT: Stok çubuğu müşteri ekranında gösterilmiyor. Kalan malzeme
 * bilgisi personelin işi; /stock sayfasında.
 */

// Sepette adet artırma KAPALI.
//
// Neden: stok kontrolü ve düşümü içecek hazırlandıktan SONRA yapılıyor
// (order_service ADIM 8). Yani 3 fincan sipariş verilirken üçünü de
// karşılayacak kahve/bardak var mı önceden bilinmiyor; ikinci fincanda
// bardak bitse akış yarıda kalır ve robot boşa çalışır.
//
// Aşama 3'te sunucu tarafına rezerve/kesinleştir/iade eklenince
// (stok siparişin BAŞINDA ayrılacak) bu sınır kaldırılabilir:
// MAX_QTY değerini artırıp aşağıdaki adet kontrolünü geri açmak yeterli.
const MAX_QTY = 1;
const QTY_ENABLED = MAX_QTY > 1;
const CART_KEY = "current_order";
const CURRENCY = "₺";

/** Sipariş durum makinesi */
const ORDER_STATE = {
  IDLE:     "idle",
  ORDERING: "ordering",
  DONE:     "done",
};

const T = {
  TR: {
    menu: "Menü", back: "Geri", cartEmpty: "Sepet boş",
    viewCart: "Sepeti gör", cart: "Sepet", total: "Toplam",
    totalItems: "Toplam ürün", totalPrice: "Toplam tutar",
    placeOrder: "Siparişi ver", addons: "İlaveler",
    coffeeList: "Kahve", iceCreamList: "Dondurma",
    hot: "Sıcak", iced: "Soğuk", noDrinks: "Bu grupta içecek yok.",
    outOfStock: "Tükendi", pickDrink: "Bir içecek seçin",
    connecting: "Bağlanıyor…",
    noService: "Servise bağlanılamıyor",
    offline: "Kahve makinesi çevrimdışı.",
    unavailable: "Kahve makinesi kullanılamıyor.",
    cleaning: "Kahve makinesi temizlik modunda.",
    milkLow: "Süt azaldı — sütlü içecekler geçici olarak kapalı",
    chocLow: "Çikolata azaldı — çikolatalı içecekler geçici olarak kapalı",
    stockOut: "Stok yetersiz.",
    robotManual: "Robot manuel modda.",
    robotNotReady: "Robot hazır değil.",
    machineNotReady: "Makine hazır değil.",
    withMilk: "Sütlü", noMilk: "Sütsüz",
  },
  EN: {
    menu: "Menu", back: "Back", cartEmpty: "Cart is empty",
    viewCart: "View cart", cart: "Cart", total: "Total",
    totalItems: "Total items", totalPrice: "Total price",
    placeOrder: "Place order", addons: "Add-ons",
    coffeeList: "Coffee", iceCreamList: "Ice cream",
    hot: "Hot", iced: "Iced", noDrinks: "No drinks in this group.",
    outOfStock: "Sold out", pickDrink: "Choose a drink",
    connecting: "Connecting…",
    noService: "Cannot reach the service",
    offline: "Coffee machine is offline.",
    unavailable: "Coffee machine is unavailable.",
    cleaning: "Coffee machine is in cleaning mode.",
    milkLow: "Milk is low — milk drinks temporarily disabled",
    chocLow: "Chocolate is low — chocolate drinks temporarily disabled",
    stockOut: "Not enough stock.",
    robotManual: "Robot is in manual mode.",
    robotNotReady: "Robot is not ready.",
    machineNotReady: "Machine is not ready.",
    withMilk: "With milk", noMilk: "No milk",
  },
};

const buildStartMessage = (b) => ({
  function: "startBeverage",
  a_iBtnNbr: String(b.ButtonNumber),
  a_iBarista: "1", a_iDecaf: "0", a_iSML: "1",
  a_iMilktype: "-1", a_iSirupType: "0", a_iSirupSML: "1",
  a_iBeanPortioner: "0", a_iCupSizeAdj: "100",
});

const buildCheckMessage = (b) => ({
  function: "checkBeverage",
  a_iBtnNbr: String(b.ButtonNumber),
  a_iBarista: "1", a_iDecaf: "0", a_iSML: "1",
  a_iMilktype: "-1", a_iSirupType: "0", a_iSirupSML: "1",
});

/**
 * ROBOT ROTASI — makineye gitmeyen, siparişin tipini belirleyen alanlar.
 *
 * Backend bunlara bakarak robotun hangi istasyonlara uğrayacağına karar
 * verir (SysVar) ve akışı Tip 1–4 arasından seçer:
 *
 *   ice       : içeceğin temperature alanından türetilir. Ayrı bir
 *               kullanıcı adımı yok — "Iced Latte" seçmek buz
 *               istasyonunu açar.
 *   ice_water : buz haznesinden su da alınsın mı. Robot bunu kendi
 *               bilemez; içecek kaydındaki ice_water alanından gelir.
 *               Yalnızca ice true iken anlamlıdır.
 *   syrups    : sepetteki ilavelerden yalnızca ŞURUP olanların kanal
 *               numaraları. Soslar/süsler (dondurma ilaveleri) kanal
 *               taşımaz, elenirler.
 *
 * Kaç mL akacağı BURADA belirlenmez: backend her kanalın kendi dose_ml
 * değerini okur. Böylece personel dozu /stock sayfasından değiştirince
 * arayüzde hiçbir şey güncellenmesi gerekmez.
 */
const buildRoute = (b) => ({
  ice: (b.temperature ?? "hot") === "iced",
  ice_water: Boolean(b.ice_water),
  syrups: (b.customize ?? [])
    .map((id) => extraChannel(id))
    .filter((ch) => ch != null),
});

const parsePrice = (s) => parseFloat(String(s ?? "0").replace(",", ".")) || 0;

/* ═══════════════════════════════════════════════════════════ */

const Home = () => {
  const [language, setLanguage] = useState("TR");
  const t = T[language];

  /* ── Gezinme ─────────────────────────────── */
  // Yalnızca tek kategori açıksa seçim ekranını göstermenin anlamı
  // yok — doğrudan o listeye girilir ve geri butonu gizlenir.
  const singleCategory = ENABLED_CATEGORIES.length === 1 ? ENABLED_CATEGORIES[0] : null;

  const [category, setCategory] = useState(singleCategory);   // null | "coffee" | "ice_cream"
  const [temperature, setTemperature] = useState("hot");   // "hot" | "iced"

  /* ── Sepet ───────────────────────────────── */
  const [cart, setCart] = useState({});
  const [cartOpen, setCartOpen] = useState(false);
  const [productModal, setProductModal] = useState({ open: false, item: null });

  /* ── Backend durumları ───────────────────── */
  const [machine, setMachine] = useState({ online: false, has_blocking_error: false, cleaning: null });
  const [machineLoading, setMachineLoading] = useState(true);
  const [machineErr, setMachineErr] = useState(null);

  const [robotStatus, setRobotStatus] = useState({ can_order: false, mode_label: "disconnected" });
  const [robotLoading, setRobotLoading] = useState(true);

  const [stockStatus, setStockStatus] = useState({
    status: { all_disabled: false, milk_disabled: false, choc_disabled: false },
    alerts: [],
  });

  /* ── Sipariş akışı ───────────────────────── */
  const [orderState, setOrderState] = useState(ORDER_STATE.IDLE);
  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [progress, setProgress] = useState({ jobId: null, status: null, phase: null, rcpState: null, error: null });
  const [preparingOpen, setPreparingOpen] = useState(false);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertData, setAlertData] = useState({ title: "", message: "" });

  const pollRef = useRef(null);
  const busyRef = useRef(false);

  /* ─────────────────────────────────────────
     YOKLAMA
     ───────────────────────────────────────── */

  const fetchMachine = useCallback(async () => {
    try {
      const { data } = await api.get(ENDPOINTS.machineStatus, { timeout: 4000 });
      setMachine(data);
      setMachineErr(null);
    } catch (err) {
      setMachineErr(errorText(err, "Makine durumu alınamadı."));
    } finally {
      setMachineLoading(false);
    }
  }, []);

  const fetchRobot = useCallback(async () => {
    try {
      const { data } = await api.get(ENDPOINTS.robotStatus, { timeout: 3000 });
      setRobotStatus(data);
    } catch {
      setRobotStatus((p) => ({ ...p, can_order: false }));
    } finally {
      setRobotLoading(false);
    }
  }, []);

  const fetchStock = useCallback(async () => {
    try {
      const { data } = await api.get(ENDPOINTS.stockStatus, { timeout: 4000 });
      setStockStatus(data);
    } catch {
      /* stok okunamazsa mevcut durumu koru — ekranı boşuna kilitleme */
    }
  }, []);

  useEffect(() => {
    fetchMachine();
    const id = setInterval(fetchMachine, POLL.machine);
    return () => clearInterval(id);
  }, [fetchMachine]);

  useEffect(() => {
    fetchRobot();
    const id = setInterval(fetchRobot, POLL.robot);
    return () => clearInterval(id);
  }, [fetchRobot]);

  useEffect(() => {
    fetchStock();
    const id = setInterval(fetchStock, POLL.stock);
    return () => clearInterval(id);
  }, [fetchStock]);

  // Bileşen sökülürken sipariş yoklamasını durdur
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  /* ─────────────────────────────────────────
     SİPARİŞ VERİLEBİLİR Mİ
     ───────────────────────────────────────── */

  const { all_disabled: allDisabled, milk_disabled: milkDisabled, choc_disabled: chocDisabled } =
    stockStatus.status ?? {};

  const canOrder =
    machine.online &&
    !machine.has_blocking_error &&
    !machine.cleaning &&
    !allDisabled &&
    Boolean(robotStatus.can_order);

  const isDisabled = (item) => {
    if (allDisabled) return true;
    if (milkDisabled && item?.milk) return true;
    if (chocDisabled && item?.milkChocolate) return true;
    return false;
  };

  const blockReason = () => {
    if (allDisabled) return t.stockOut;
    if (!robotStatus.can_order)
      return robotStatus.mode_label === "manual" ? t.robotManual : t.robotNotReady;
    return t.machineNotReady;
  };

  /* ─────────────────────────────────────────
     SEPET
     ───────────────────────────────────────── */

  const cartItem = cart[CART_KEY];
  const totalItems = cartItem?.qty ?? 0;

  // İlaveler dile bağlı olmayan id ile tutulur. Önceki sürüm
  // e.name === name karşılaştırması yapıyordu; `name` alanı kayıtlarda
  // hiç olmadığı için her aramada dizinin ilk elemanı ("Renkli Süsler")
  // dönüyor, sepette yanlış ilave ve yanlış fiyat görünüyordu.
  const itemTotal = useCallback((item) => {
    if (!item) return 0;
    const addOns = (item.customize ?? []).reduce(
      (sum, id) => sum + parsePrice(findExtra(id)?.price),
      0
    );
    return (parsePrice(item.price) + addOns) * item.qty;
  }, []);

  const totalPrice = itemTotal(cartItem);

  const addToCart = (item) => {
    setCart((prev) => {
      const existing = prev[CART_KEY];
      const same =
        existing &&
        existing.type === item.type &&
        (existing.ButtonNumber ?? existing.Name_TR) === (item.ButtonNumber ?? item.Name_TR);

      if (same) {
        return { [CART_KEY]: { ...existing, customize: item.customize ?? [] } };
      }
      return {
        [CART_KEY]: { ...item, qty: 1, customize: item.customize ?? [], cartKey: CART_KEY },
      };
    });
  };

  const changeQty = (delta) => {
    setCart((prev) => {
      const item = prev[CART_KEY];
      if (!item) return prev;
      const next = item.qty + delta;
      if (next < 1) return {};
      if (next > MAX_QTY) return prev;
      return { [CART_KEY]: { ...item, qty: next } };
    });
  };

  const clearCart = () => { setCart({}); setCartOpen(false); };

  const removeCustomize = (id) => {
    setCart((prev) => {
      const item = prev[CART_KEY];
      if (!item) return prev;
      return {
        [CART_KEY]: { ...item, customize: (item.customize ?? []).filter((x) => x !== id) },
      };
    });
  };

  /* ─────────────────────────────────────────
     SİPARİŞ AKIŞI
     ───────────────────────────────────────── */

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const pollJob = (jobId) =>
    new Promise((resolve, reject) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get(ENDPOINTS.orderStatus(jobId));
          const { status, rcp_state, phase, error } = data;

          setProgress((prev) => ({
            ...prev,
            jobId,
            status,
            phase: phase ?? prev.phase,
            rcpState: rcp_state ?? prev.rcpState,
            error: error ?? null,
          }));

          if (status === "done" || phase === "robot_delivered") {
            stopPolling();
            resolve();
          } else if (status === "error" || status === "timeout") {
            stopPolling();
            reject(error || "Bilinmeyen hata");
          }
        } catch (err) {
          stopPolling();
          reject(errorText(err, "Sipariş durumu okunamadı."));
        }
      }, POLL.order);
    });

  const orderOne = async (beverage) => {
    // Rota bilgisi hem kontrolde hem siparişte AYNI olmalı — yoksa
    // kontrol şurupsuz geçer, sipariş şuruplu başlar ve stok kapısı
    // devreye girmemiş olur.
    const route = buildRoute(beverage);

    // 1) Makine bu içeceği hazırlayabilir mi? (+ şurup stok kapısı)
    const { data: check } = await api.post(ENDPOINTS.checkBeverage, {
      message: buildCheckMessage(beverage),
      ...route,
    });

    const result = check?.result;
    if (!result || result.returnvalue !== 0) {
      // Şurup kapısı kendi açıklamasını taşır ("Karamel şurubu yetersiz…");
      // ham returnvalue metninden ("Başlatma başarısız") çok daha anlaşılır.
      if (check?.syrup_block?.message) throw check.syrup_block.message;

      const detail = check?.machine_error_detail;
      throw detail
        ? `${buildCheckBeverageMessage(result)}\n${detail}`
        : buildCheckBeverageMessage(result);
    }

    // 2) Siparişi başlat. 409 = başka bir sipariş işleniyor → kısa aralıkla yeniden dene
    let response;
    for (let attempt = 0; attempt <= 3; attempt += 1) {
      try {
        response = await api.post(ENDPOINTS.orderStandart, {
          message: buildStartMessage(beverage),
          ...route,
        });
        break;
      } catch (err) {
        if (err?.response?.status === 409 && attempt < 3) {
          await new Promise((r) => setTimeout(r, 2000));
        } else {
          throw errorText(err);
        }
      }
    }

    const jobId = response?.data?.job_id;
    if (!jobId) throw "Backend job_id döndürmedi.";

    setProgress({ jobId, status: "running", phase: "created", rcpState: null, error: null });
    await pollJob(jobId);
  };

  const placeOrder = async () => {
    if (!canOrder || !cartItem || busyRef.current) return;

    busyRef.current = true;
    setOrderState(ORDER_STATE.ORDERING);
    setCartOpen(false);
    setPreparingOpen(true);

    // Aynı ürünün qty adedi sırayla hazırlanır
    const flat = Array.from({ length: cartItem.qty }, () => cartItem);
    setQueue(flat);
    setCurrentIndex(0);

    try {
      for (let i = 0; i < flat.length; i += 1) {
        setCurrentIndex(i);
        setProgress({ jobId: null, status: "running", phase: "created", rcpState: null, error: null });
        await orderOne(flat[i]);
        fetchStock();
      }

      setOrderState(ORDER_STATE.DONE);
      setProgress((p) => ({ ...p, status: "done", phase: "robot_delivered" }));
      // Sepet YALNIZCA başarıda temizlenir
      clearCart();
    } catch (message) {
      setProgress((p) => ({ ...p, status: "error", error: String(message) }));
      setAlertData({ title: language === "EN" ? "Order failed" : "Sipariş tamamlanamadı", message: String(message) });
      setAlertOpen(true);
      setPreparingOpen(false);
      setOrderState(ORDER_STATE.IDLE);
    } finally {
      busyRef.current = false;
      fetchStock();
    }
  };

  /** Hazırlanma ekranı kapanınca ekran yeni siparişe hazır hale gelir */
  const resetForNextOrder = () => {
    stopPolling();
    setPreparingOpen(false);
    setProgress({ jobId: null, status: null, phase: null, rcpState: null, error: null });
    setQueue([]);
    setCurrentIndex(0);
    setOrderState(ORDER_STATE.IDLE);
    setCategory(singleCategory);   // ana menüye dön (tek kategori varsa ona)
    setTemperature("hot");
  };

  /* ─────────────────────────────────────────
     SİSTEM DURUMU

     Önceki davranış: makineye/robota ulaşılamadığında tüm ekran tek
     bir mesajla değiştiriliyordu ve müşteri boş bir ekranla kalıyordu.

     Yeni davranış: ekran HER ZAMAN açılır. Sorun varsa üstte kırmızı
     şerit çıkar ve içerik etkileşime kapatılır. Müşteri menüyü görür,
     personel sorunun ne olduğunu okur.
     ───────────────────────────────────────── */

  const systemStatus = (() => {
    // Sipariş sürerken robot "meşgul" olduğu için can_order geçici olarak
    // false olabilir ve stok son bardağa inebilir. Bu geçici durumlar
    // gerçek bir arıza değil; hazırlanma ekranı zaten önde. Aksi halde
    // her siparişin sonunda kırmızı şerit bir an yanıp sönerdi.
    const ordering = orderState === ORDER_STATE.ORDERING;

    // Bir servis sahte DEĞİLKEN hata veriyorsa, bunu bilmek teşhisi
    // kısaltıyor: "makine çevrimdışı" mı yoksa "mock'u açmayı mı
    // unuttum" sorusunun cevabı burada.
    const source = (key) =>
      OFFLINE_SERVICES[key] ? "sahte servis" : `gerçek servis · ${BASE_URL}`;

    // İlk yükleme — henüz cevap gelmedi
    if (machineLoading) {
      return { blocked: true, severity: "info", message: t.connecting, pulse: true };
    }

    // Backend'e hiç ulaşılamıyor
    if (machineErr) {
      return { blocked: true, severity: "error", message: t.noService, detail: machineErr, pulse: true };
    }

    if (!machine.online) {
      return { blocked: true, severity: "error", message: t.offline, detail: source("machine") };
    }

    if (machine.has_blocking_error) {
      // Backend hata kodlarını okunabilir metne çeviriyor
      const detail = machine.error_description
        || (Array.isArray(machine.errors) && machine.errors.length
              ? `Hata kodu: ${machine.errors.join(", ")}`
              : null);
      return { blocked: true, severity: "error", message: t.unavailable, detail: detail || source("machine") };
    }

    if (machine.cleaning) {
      return { blocked: true, severity: "error", message: t.cleaning };
    }

    // Robot yoksa veya manuel moddaysa sipariş alınamaz
    if (!ordering && !robotLoading && !robotStatus.can_order) {
      return {
        blocked: true,
        severity: "error",
        message: robotStatus.mode_label === "manual" ? t.robotManual : t.robotNotReady,
        detail: source("robot"),
      };
    }

    // Stok tamamen bitti
    if (!ordering && allDisabled) {
      const alert = (stockStatus.alerts ?? []).find((a) => a.type === "critical");
      return { blocked: true, severity: "error", message: t.stockOut, detail: alert?.message };
    }

    // Kısmi kısıtlar — sipariş alınabilir, yalnızca uyarı
    if (milkDisabled) return { blocked: false, severity: "warning", message: t.milkLow };
    if (chocDisabled) return { blocked: false, severity: "warning", message: t.chocLow };

    return { blocked: false, severity: "info", message: null };
  })();

  const blocked = systemStatus.blocked;

  /** Etkileşime kapalı içerik için ortak stil */
  const blockedSx = blocked
    ? {
        pointerEvents: "none",
        opacity: 0.35,
        filter: "saturate(0.35)",
        transition: "opacity 0.3s, filter 0.3s",
      }
    : { transition: "opacity 0.3s, filter 0.3s" };

  /* ─────────────────────────────────────────
     LİSTELER
     ───────────────────────────────────────── */

  // Sıcak ve soğuk içeceklerin hepsi tek listede. Soğuk içecekler
  // eskiden ayrı bir demoIcedDrinks dizisindeydi ve YALNIZCA çevrimdışı
  // modda menüye ekleniyordu — çünkü o zaman buton numaraları
  // uydurmaydı (901–903). Artık gerçek numaralar kullanılıyor
  // (Iced Americano = 1, Iced Latte = 7) ve backend catalog.py ile
  // doğrulandı, dolayısıyla ayrı tutmanın anlamı kalmadı.
  const coffeeDrinks = (beverages?.drinks ?? []).filter((d) => d.type === "coffee");

  // Kahve grubunda sıcak/soğuk sekmesi. temperature alanı tanımsız
  // olan eski kayıtlar "hot" sayılır.
  const drinkList =
    category === "coffee"
      ? coffeeDrinks.filter((d) => (d.temperature ?? "hot") === temperature)
      : category === "ice_cream"
        ? (beverages?.iceCreams ?? []).filter((d) => d.type === "ice_cream")
        : [];

  /* ═════════════════════════════════════════
     RENDER
     ═════════════════════════════════════════ */

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>

      {/* ── Uyarı şeridi + üst çubuk (birlikte yapışkan) ──
          İkisi ayrı ayrı sticky olsaydı kaydırmada üst üste binerlerdi. */}
      <Box sx={{ position: "sticky", top: 0, zIndex: 30 }}>

        {/* Çevrimdışı test modu göstergesi.
            Kazara üretim derlemesine sızarsa hemen fark edilsin diye
            kalıcı ve dikkat çekici. */}
        {ANY_MOCKED && (
          <Box
            sx={{
              bgcolor: palette.machine,
              color: palette.lime,
              px: { xs: 2, md: 4 },
              py: 0.75,
              fontFamily: "var(--mono)",
              fontSize: 11,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              display: "flex",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 1,
            }}
          >
            <span>
              ⚠ Test modu — sahte: {MOCKED_LABEL}
              {!ALL_MOCKED && " (kalanı gerçek)"}
            </span>
            <span>senaryo: {OFFLINE_SCENARIO}</span>
          </Box>
        )}

        <SystemBanner
          severity={systemStatus.severity}
          message={systemStatus.message}
          detail={systemStatus.detail}
          pulse={systemStatus.pulse}
        />

        {/* Başlık bloke durumda da etkileşimli kalır — dil değiştirmek
            zararsız ve müşteri beklerken faydalı. */}
        <Box
          component="header"
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
            px: { xs: 2, md: 4 },
            py: 2,
            bgcolor: palette.ink,
            color: palette.paper,
          }}
        >
          <Box
            component="img"
            src={logo}
            alt="Logorob"
            sx={{ height: 52, objectFit: "contain" }}
          />

          {/* Geri butonu — yalnızca liste görünümünde */}
          {category && !singleCategory ? (
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => { setCategory(null); setTemperature("hot"); }}
              sx={{ color: palette.paper, borderColor: "rgba(231,225,213,0.3)" }}
              variant="outlined"
            >
              {t.back}
            </Button>
          ) : (
            <Typography variant="overline" sx={{ color: palette.lime }}>
              {t.pickDrink}
            </Typography>
          )}

          <Stack direction="row" spacing={1}>
            {[["TR", trFlag], ["EN", enFlag]].map(([code, flag]) => (
              <Box
                key={code}
                role="button"
                tabIndex={0}
                onClick={() => setLanguage(code)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setLanguage(code)}
                sx={{
                  display: "grid",
                  placeItems: "center",
                  width: 64,
                  height: TOUCH_MIN,
                  borderRadius: 1,
                  cursor: "pointer",
                  border: `2px solid ${language === code ? palette.lime : "transparent"}`,
                  bgcolor: "rgba(255,255,255,0.06)",
                }}
              >
                <Box component="img" src={flag} alt={code} sx={{ width: 38, height: 26, objectFit: "cover" }} />
              </Box>
            ))}
          </Stack>
        </Box>
      </Box>

      {/* ── İçerik — sistem blokeliyken etkileşime kapalı ── */}
      <Box
        aria-hidden={blocked}
        sx={{
          ...blockedSx,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: category ? "flex-start" : "center",
          px: { xs: 2, sm: 3, md: 4 },
          py: 4,
          overflowY: "auto",
        }}
      >
        {/* Kategori seçimi */}
        {!category && (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={3}>
            {(beverages?.categories ?? [])
              .filter((cat) => CATEGORIES[cat.type])
              .map((cat) => (
              <Box
                key={cat.id}
                role="button"
                tabIndex={0}
                onClick={() => setCategory(cat.type)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setCategory(cat.type)}
                sx={{
                  width: { xs: 280, sm: 300, md: 340 },
                  bgcolor: "background.paper",
                  borderRadius: 1,
                  overflow: "hidden",
                  cursor: "pointer",
                  position: "relative",
                  transition: "transform 0.18s, box-shadow 0.18s",
                  "&:hover": { transform: "translateY(-3px)", boxShadow: "0 12px 26px rgba(23,22,15,0.16)" },
                  "&::after": {
                    content: '""',
                    position: "absolute",
                    inset: "auto 0 0 0",
                    height: 4,
                    bgcolor: cat.type === "coffee" ? palette.lime : palette.red,
                  },
                }}
              >
                <Box
                  component="img"
                  src={cat.type === "coffee" ? coffeeCategoryImg : iceCreamCategoryImg}
                  alt=""
                  sx={{ width: "100%", height: 190, objectFit: "contain", p: 2 }}
                />
                <Typography variant="h2" sx={{ px: 2.5, pb: 3 }}>
                  {cat[`name_${language}`] ?? cat.name}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}

        {/* İçecek listesi */}
        {category && (
          <Box sx={{ width: "100%", maxWidth: 1200 }}>
            <Typography variant="h1" mb={category === "coffee" ? 2 : 3}>
              {category === "coffee" ? t.coffeeList : t.iceCreamList}
            </Typography>

            {/* Sıcak / Soğuk sekmesi — yalnızca kahve grubunda.
                Ambalaj aksanı korunuyor: sıcak fıstık yeşili,
                soğuk kırmızı. */}
            {category === "coffee" && (
              <Stack direction="row" spacing={1.5} mb={3} role="tablist">
                {[
                  { key: "hot",  label: t.hot,  Icon: LocalFireDepartmentIcon, accent: palette.lime },
                  { key: "iced", label: t.iced, Icon: AcUnitIcon,              accent: palette.red },
                ].map(({ key, label, Icon, accent }) => {
                  const active = temperature === key;
                  // Bileşeni yerel bir değişkene al: lint, dizi/nesne
                  // destructuring'ini fonksiyon parametresi saydığı için
                  // JSX içindeki kullanımı göremiyor.
                  const TabIcon = Icon;
                  return (
                    <Box
                      key={key}
                      role="tab"
                      tabIndex={0}
                      aria-selected={active}
                      onClick={() => setTemperature(key)}
                      onKeyDown={(e) =>
                        (e.key === "Enter" || e.key === " ") && setTemperature(key)
                      }
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1.25,
                        px: 2.5,
                        py: 0.75,
                        minHeight: TOUCH_MIN,
                        borderRadius: 1,
                        cursor: "pointer",
                        bgcolor: active ? palette.ink : "transparent",
                        color: active ? palette.paper : "text.primary",
                        border: `2px solid ${active ? palette.ink : palette.rule}`,
                        transition: "background-color 0.18s, color 0.18s",
                        position: "relative",
                        overflow: "hidden",
                        "&::after": {
                          content: '""',
                          position: "absolute",
                          inset: "auto 0 0 0",
                          height: 3,
                          bgcolor: accent,
                          opacity: active ? 1 : 0.45,
                        },
                      }}
                    >
                      <TabIcon
                        sx={{
                          fontSize: 22,
                          // İkon rengi aksanı taşır; seçili değilken de
                          // sıcak/soğuk ayrımı okunur kalsın.
                          color: active ? accent : palette.ink2,
                        }}
                      />
                      <Typography
                        sx={{
                          fontFamily: "var(--mono)",
                          fontSize: 13,
                          fontWeight: 700,
                          letterSpacing: "0.1em",
                          textTransform: "uppercase",
                        }}
                      >
                        {label}
                      </Typography>
                    </Box>
                  );
                })}
              </Stack>
            )}

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
                gap: 2,
              }}
            >
              {drinkList.length === 0 && (
                <Typography variant="overline" color="text.secondary" sx={{ gridColumn: "1/-1", py: 4 }}>
                  {t.noDrinks}
                </Typography>
              )}

              {drinkList.map((item) => {
                const key = `${item.type}_${item.ButtonNumber ?? item.Name_TR}`;
                const selected =
                  cartItem &&
                  `${cartItem.type}_${cartItem.ButtonNumber ?? cartItem.Name_TR}` === key;
                const disabled = isDisabled(item);

                return (
                  <Box
                    key={key}
                    role="button"
                    tabIndex={disabled ? -1 : 0}
                    onClick={() => {
                      if (disabled) return;
                      setProductModal({
                        open: true,
                        item: { ...item, customize: selected ? (cartItem.customize ?? []) : [] },
                      });
                    }}
                    sx={{
                      position: "relative",
                      bgcolor: "background.paper",
                      borderRadius: 1,
                      overflow: "hidden",
                      cursor: disabled ? "not-allowed" : "pointer",
                      opacity: disabled ? 0.45 : 1,
                      outline: selected ? `2px solid ${palette.red}` : "none",
                      transition: "transform 0.18s, box-shadow 0.18s",
                      "&:hover": !disabled && {
                        transform: "translateY(-3px)",
                        boxShadow: "0 10px 22px rgba(23,22,15,0.14)",
                      },
                      "&::after": {
                        content: '""',
                        position: "absolute",
                        inset: "auto 0 0 0",
                        height: 4,
                        // Ambalajdan gelen aksan: sıcak fıstık yeşili, soğuk kırmızı
                        bgcolor: item.temperature === "iced" ? palette.red : palette.lime,
                      },
                    }}
                  >
                    {disabled && (
                      <Chip
                        label={t.outOfStock}
                        size="small"
                        sx={{
                          position: "absolute", top: 8, right: 8, zIndex: 2,
                          bgcolor: palette.red, color: "#fff", fontWeight: 700,
                        }}
                      />
                    )}

                    {selected && QTY_ENABLED && (
                      <Badge
                        badgeContent={cartItem.qty}
                        color="primary"
                        sx={{ position: "absolute", top: 18, left: 22, zIndex: 2 }}
                      />
                    )}

                    <Box
                      component="img"
                      src={item.image}
                      alt={getName(item, language)}
                      sx={{ width: "100%", height: 160, objectFit: "contain", p: 2 }}
                    />

                    <Box sx={{ px: 2, pb: 2.5 }}>
                      <Typography variant="h4" mb={0.5}>{getName(item, language)}</Typography>
                      <Typography variant="overline" color="text.secondary" display="block">
                        {item.milk ? t.withMilk : t.noMilk}
                      </Typography>
                      <Typography variant="h4" color="primary.main" mt={1}>
                        {item.price} {CURRENCY}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          </Box>
        )}
      </Box>

      {/* ── Alt sepet çubuğu ── */}
      <Box
        aria-hidden={blocked}
        sx={{
          ...blockedSx,
          position: "sticky", bottom: 0, zIndex: 15,
          display: "grid", placeItems: "center",
          py: 2, px: 2,
          bgcolor: "background.default",
          borderTop: `1px solid ${palette.rule}`,
        }}
      >
        <Button
          variant={totalItems ? "contained" : "outlined"}
          color={totalItems ? "primary" : "secondary"}
          disabled={!totalItems}
          onClick={() => setCartOpen(true)}
          startIcon={
            <Badge badgeContent={totalItems} color="secondary">
              <ShoppingCartIcon />
            </Badge>
          }
          sx={{ width: { xs: "100%", sm: 380 }, height: 62 }}
        >
          {totalItems ? t.viewCart : t.cartEmpty}
        </Button>
      </Box>

      {/* ── Sepet çekmecesi ── */}
      <Drawer
        anchor="right"
        open={cartOpen}
        onClose={() => setCartOpen(false)}
        PaperProps={{
          sx: {
            width: { xs: "92vw", sm: 460 },
            bgcolor: "background.default",
            p: 2.5,
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h2">{t.cart}</Typography>
          <IconButton onClick={() => setCartOpen(false)}><CloseIcon /></IconButton>
        </Stack>

        <Divider sx={{ mb: 2 }} />

        <Box sx={{ flex: 1, overflowY: "auto" }}>
          {!cartItem ? (
            <Stack alignItems="center" spacing={2} mt={8} sx={{ opacity: 0.45 }}>
              <ShoppingCartIcon sx={{ fontSize: 56 }} />
              <Typography>{t.cartEmpty}</Typography>
            </Stack>
          ) : (
            <Box sx={{ bgcolor: "background.paper", borderRadius: 1, p: 2 }}>
              <Stack direction="row" alignItems="center" spacing={2}>
                <Box
                  component="img"
                  src={cartItem.image}
                  alt=""
                  sx={{ width: 70, height: 60, objectFit: "contain" }}
                />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h4">{getName(cartItem, language)}</Typography>
                  <Typography variant="overline" color="text.secondary">
                    {cartItem.price} {CURRENCY} × {cartItem.qty}
                  </Typography>
                </Box>
                <IconButton onClick={() => setCart({})} sx={{ color: palette.red }}>
                  <DeleteOutlineIcon />
                </IconButton>
              </Stack>

              {/* Adet — MAX_QTY 1 iken gösterilmez.
                  Tek fincanda kontrolün anlamı yok ve boş bir
                  artı/eksi çifti kullanıcıyı yanıltırdı. */}
              {QTY_ENABLED && (
                <Stack direction="row" alignItems="center" justifyContent="center" spacing={3} mt={2}>
                  <IconButton
                    onClick={() => changeQty(-1)}
                    sx={{ border: `1px solid ${palette.rule}`, borderRadius: 1 }}
                  >
                    <RemoveIcon />
                  </IconButton>
                  <Typography variant="h3" sx={{ minWidth: 32, textAlign: "center" }}>
                    {cartItem.qty}
                  </Typography>
                  <IconButton
                    onClick={() => changeQty(1)}
                    disabled={cartItem.qty >= MAX_QTY}
                    sx={{ border: `1px solid ${palette.rule}`, borderRadius: 1 }}
                  >
                    <AddIcon />
                  </IconButton>
                </Stack>
              )}

              {/* İlaveler */}
              {cartItem.customize?.length > 0 && (
                <Box mt={2} pt={2} sx={{ borderTop: `1px solid ${palette.rule}` }}>
                  <Typography variant="overline" color="text.secondary" display="block" mb={1}>
                    {t.addons}
                  </Typography>
                  {cartItem.customize.map((id) => {
                    const found = findExtra(id);
                    return (
                      <Stack
                        key={id}
                        direction="row"
                        alignItems="center"
                        justifyContent="space-between"
                        py={0.5}
                      >
                        <Typography fontSize={14}>
                          + {extraName(id, language)}
                        </Typography>
                        <Stack direction="row" alignItems="center" spacing={1.5}>
                          <Typography variant="overline">{found?.price} {CURRENCY}</Typography>
                          <IconButton size="small" onClick={() => removeCustomize(id)} sx={{ color: palette.red }}>
                            <CloseIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        </Stack>
                      </Stack>
                    );
                  })}
                </Box>
              )}
            </Box>
          )}
        </Box>

        {/* Toplam + sipariş butonu */}
        {cartItem && (
          <Box sx={{ pt: 2, mt: 2, borderTop: `1px solid ${palette.rule}` }}>
            {QTY_ENABLED && (
              <Stack direction="row" justifyContent="space-between" mb={0.5}>
                <Typography variant="overline">{t.totalItems}</Typography>
                <Typography variant="overline">{totalItems}</Typography>
              </Stack>
            )}
            <Stack direction="row" justifyContent="space-between" mb={2}>
              <Typography variant="h4">{t.totalPrice}</Typography>
              <Typography variant="h4" color="primary.main">
                {totalPrice.toFixed(2).replace(".", ",")} {CURRENCY}
              </Typography>
            </Stack>

            {!canOrder && (
              <Box sx={{ mb: 1.5, p: 1.5, borderRadius: 1, bgcolor: "rgba(229,53,42,0.1)" }}>
                <Typography variant="overline" sx={{ color: palette.red }}>
                  {blockReason()}
                </Typography>
              </Box>
            )}

            <Button
              fullWidth
              variant="contained"
              color="primary"
              disabled={!canOrder || orderState === ORDER_STATE.ORDERING}
              onClick={placeOrder}
              sx={{ height: 62 }}
            >
              {t.placeOrder}
            </Button>
          </Box>
        )}
      </Drawer>

      {/* ── Modallar ── */}
      <ProductDetail
        productModal={productModal}
        setProductModal={setProductModal}
        addToCart={addToCart}
        cart={cart}
        currency={CURRENCY}
        language={language}
        disabledSyrupChannels={stockStatus?.disabled_syrup_channels ?? []}
      />

      <PreparingCoffee
        open={preparingOpen}
        handleClose={resetForNextOrder}
        phase={progress.phase}
        status={progress.status}
        rcpState={progress.rcpState}
        error={progress.error}
        item={queue[currentIndex]}
        language={language}
        currentIndex={currentIndex}
        totalItems={queue.length}
      />

      {DEBUG && (
        <DebugOverlay
          machine={machine}
          robotStatus={robotStatus}
          stockStatus={stockStatus}
          blocked={blocked}
          bannerMessage={systemStatus.message}
        />
      )}

      <Alert
        openAlert={alertOpen}
        handleCloseAlert={() => setAlertOpen(false)}
        alertData={alertData}
        setAlertData={setAlertData}
        language={language}
      />
    </Box>
  );
};

export default Home;
