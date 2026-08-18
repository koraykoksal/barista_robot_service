# ══════════════════════════════════════════════════════════════
# Kiosk arayüzü imajı
#
# DEĞİŞENLER:
#   • "FROM node as build" sabitlenmemişti — build makinesindeki node
#     sürümüne göre farklı çıktı üretiyordu. node:20-alpine'e sabitlendi.
#   • nginx.conf eklendi (SPA geri düşüşü; /stock yenilendiğinde 404
#     veriyordu)
#   • VITE_ değişkenleri build argümanı olarak alınıyor — Vite bunları
#     derleme anında gömer, çalışma anında okuyamaz
# ══════════════════════════════════════════════════════════════

# ── 1) Derleme ────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Bağımlılıklar ayrı katmanda — kod değişince npm ci tekrar çalışmaz
COPY package*.json ./
RUN npm ci

COPY . .

# Vite ortam değişkenlerini DERLEME anında okur.
# docker build --build-arg VITE_API_URL=http://192.168.1.44:8000 ...
ARG VITE_API_URL=http://127.0.0.1:8000
ARG VITE_ADMIN_TOKEN=
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_ADMIN_TOKEN=$VITE_ADMIN_TOKEN

RUN npm run build

# ── 2) Servis ─────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
