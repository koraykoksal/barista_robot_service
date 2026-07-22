import { Route, Routes } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import Home from "./pages/Home";
import StockManagement from "./pages/StockManagement";

/**
 * App.jsx
 *
 * DEĞİŞENLER:
 *   • /test rotası kaldırıldı — Test.jsx arşive taşındı
 *   • Kullanılmayan useState importu ve App.css kaldırıldı
 *   • Toast'lar açık temaya göre ayarlandı ve dokunmatik için
 *     büyütüldü
 *
 * ROTALAR:
 *   /       → kiosk ekranı (müşteri, dokunmatik)
 *   /stock  → stok yönetimi (personel)
 */

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/stock" element={<StockManagement />} />
      </Routes>

      <ToastContainer
        position="top-center"
        autoClose={2200}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        pauseOnHover={false}
        draggable={false}
        theme="light"
        limit={2}
      />
    </>
  );
}

export default App;
