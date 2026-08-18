# Docker ile çalıştırma

Backend (FastAPI) ve frontend (nginx) tek komutla ayağa kalkar.

## Gereksinimler

- Docker Engine 20.10+
- Docker Compose v2 (`docker compose`, tire ile değil)

## Kurulum (3 adım)

### 1. Backend ayarları

```bash
cd backend/wmf
cp .env.example .env
```

`.env` içinde en az şunları düzenleyin:

```dotenv
ROBOT_IP=192.168.1.50            # robotun IP'si
COFFEE_MACHINE_IP=192.168.1.111  # kahve makinesi
SYRUP_HOST=192.168.1.155         # syrup dispenser
MONGO_URI=mongodb+srv://...      # kullanmıyorsanız MONGO_ENABLED=false
ADMIN_TOKEN=uzun-gizli-bir-deger # /stock koruması
CORS_ORIGINS=http://192.168.1.44:8080,http://localhost:8080
```

> **CORS önemli:** `CORS_ORIGINS`, arayüzün açıldığı adresi içermeli.
> Docker'da arayüz **8080** portunda; adresi buraya ekleyin.

### 2. Compose ayarları

```bash
# proje kök dizininde
cp .env.docker.example .env
```

`.env` içinde kiosk'un backend'e erişeceği adresi ayarlayın:

```dotenv
KIOSK_API_URL=http://192.168.1.44:8000   # host'un LAN IP'si
KIOSK_ADMIN_TOKEN=uzun-gizli-bir-deger   # backend'deki ADMIN_TOKEN ile aynı
```

### 3. Başlat

```bash
docker compose up -d --build
```

- Arayüz: `http://<host-ip>:8080`
- API: `http://<host-ip>:8000`
- API dokümanı: `http://<host-ip>:8000/docs`

## Günlük kullanım

```bash
docker compose ps                 # durum
docker compose logs -f backend    # backend logları (canlı)
docker compose logs -f frontend   # frontend logları
docker compose restart backend    # yalnızca backend'i yeniden başlat
docker compose down               # durdur
docker compose up -d --build      # koddan sonra yeniden kur
```

## Önemli noktalar

### Frontend'in API adresi derlemede gömülür

Vite, `VITE_API_URL`'i **derleme anında** pakete yazar. `KIOSK_API_URL`'i
değiştirdiyseniz frontend'i yeniden derleyin:

```bash
docker compose up -d --build frontend
```

Yeniden derlemeden değiştirmek isterseniz: `frontend/public/config.js`
dosyasını düzenleyip nginx'i yeniden başlatın (bkz. README — çalışma
zamanı yapılandırması). Ama Docker'da en temizi `--build`.

### Donanıma erişim (robot / makine / syrup)

Varsayılan **bridge** ağı, cihazlara **IP ile** erişildiği sürece
çalışır — `.env`'deki `ROBOT_IP`, `SYRUP_HOST` vb. doğruysa yeterli.

Cihaz keşfi (broadcast/mDNS) gerekiyorsa veya bağlantı kurulamıyorsa,
`docker-compose.yml` içinde backend servisini **host ağına** alın:

```yaml
  backend:
    # networks ve ports satırlarını silin, yerine:
    network_mode: host
```

Host modunda backend doğrudan host'un `:8000` portunda açılır, port
eşlemesi olmaz.

### Veri kalıcılığı

SQLite veritabanı ve loglar adlandırılmış hacimlerde tutulur
(`backend-data`, `backend-logs`). `docker compose down` bunları
**silmez**; veri korunur. Tamamen sıfırlamak için:

```bash
docker compose down -v            # ⚠️ hacimleri de siler
```

### MongoDB olmadan çalıştırma

Buluta bağlanmak istemiyorsanız `backend/wmf/.env` içinde:

```dotenv
MONGO_ENABLED=false
```

Sistem yalnızca yerel SQLite ile çalışır; hiçbir şey buluta gitmez.

## Sık karşılaşılan sorunlar

| Belirti | Sebep / çözüm |
|---|---|
| Arayüz açılıyor ama "Stok verisi alınamadı" | `KIOSK_API_URL` yanlış veya CORS. `.env`'deki `CORS_ORIGINS` arayüz adresini (8080) içeriyor mu? |
| `/stock` yenileyince 404 | nginx.conf SPA fallback ile bunu çözüyor; imaj güncel mi kontrol edin (`--build`) |
| Backend açılışta çöküyor | `.env` eksik olabilir. `backend/wmf/.env` var mı? |
| Robot/syrup bağlanmıyor | Cihaz IP'leri `.env`'de doğru mu? Değilse `network_mode: host` deneyin |
| Değişiklik görünmüyor | `docker compose up -d --build` ile yeniden derleyin |
