/* ══════════════════════════════════════════════════════════════
   ÇALIŞMA ZAMANI YAPILANDIRMASI

   Bu dosya derlemeye DAHİL EDİLMEZ. index.html tarafından düz bir
   script olarak yüklenir ve .env değerlerini ezer.

   NEDEN VAR:
     Vite, VITE_ önekli değişkenleri DERLEME ANINDA pakete gömer.
     Bunun iki sonucu var:

       1. Dev sunucusu .env'i yalnızca açılışta okur — dosyayı
          düzenleyip sayfayı yenilemek yetmez, sunucuyu yeniden
          başlatmak gerekir.

       2. Sahaya çıkan dist/ klasöründe değerler donmuştur. Kiosk'ta
          dondurmayı kapatmak veya backend adresini değiştirmek için
          projeyi yeniden derlemek gerekir.

     Bu dosya ikisini de çözer: sunucudaki dosyayı düzenleyip sayfayı
     yenilemeniz yeterli. Derleme, yeniden başlatma yok.

   ÖNCELİK SIRASI:
     1. URL sorgu parametresi   (?categories=coffee)
     2. BU DOSYA
     3. .env dosyası

   KULLANIM:
     Değiştirmek istediğiniz satırın başındaki // işaretini kaldırın.
     Tüm değerler METİN olarak yazılır — true/false dahil.

   ⚠️  Değerler tarayıcıya gönderilir. Buraya gerçek sır koymayın.
   ══════════════════════════════════════════════════════════════ */

window.__KIOSK_CONFIG__ = {

  // ── Backend adresi ──────────────────────────
  // VITE_API_URL: "http://192.168.1.40:8000",

  // ── Menü kategorileri ───────────────────────
  // Dondurma ünitesi olmayan kurulumda:
  // VITE_CATEGORY_COFFEE:   "true",
  // VITE_CATEGORY_ICECREAM: "false",

  // ── Çevrimdışı test modu ────────────────────
  // VITE_OFFLINE: "true",
  // VITE_OFFLINE_SCENARIO: "ok",
  // VITE_OFFLINE_SPEED: "1",

  // ── Servis bazlı çevrimdışı ─────────────────
  // VITE_OFFLINE_MACHINE: "true",
  // VITE_OFFLINE_ROBOT:   "true",
  // VITE_OFFLINE_STOCK:   "false",

  // ── Yönetici ────────────────────────────────
  // VITE_ADMIN_TOKEN: "...",

  // ── Yoklama aralıkları (ms) ─────────────────
  // VITE_MACHINE_POLL_MS: "1000",
  // VITE_STOCK_POLL_MS:   "5000",
};
