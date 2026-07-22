import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";

import App from "./App.jsx";
import theme from "./theme.js";
import "./index.css";

/**
 * main.jsx
 *
 * DEĞİŞENLER:
 *   • ThemeProvider eklendi — açık tema artık uygulama geneline uygulanıyor
 *   • CssBaseline eklendi — tarayıcı varsayılanlarını temizler ve
 *     tema zeminini <body>'ye yazar
 *   • main.jsx içindeki kullanılmayan Route/Routes importları kaldırıldı
 */

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </BrowserRouter>
);
