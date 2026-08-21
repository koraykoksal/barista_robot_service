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
CORS_ORIGINS=http://192.168.1.44:8088,http://localhost:8088
```

> **CORS önemli:** `CORS_ORIGINS`, arayüzün açıldığı adresi TAM olarak
> içermeli — şema, IP ve port. Docker'da arayüz varsayılan olarak
> **8088** portunda (`FRONTEND_PORT`). Eksikse tarayıcı isteği CORS'a
> takılır ve ekranda "Servise bağlanılamıyor" görürsünüz.

### 2. Compose ayarları

```bash
# proje kök dizininde
cp .env.docker.example .env
```

`.env` içinde kiosk'un backend'e erişeceği adresi ayarlayın:

```dotenv
KIOSK_API_URL=http://192.168.1.44:8000   # ⚠️ sunucunun LAN IP'si — localhost DEĞİL
BACKEND_PORT=8000
FRONTEND_PORT=8088
KIOSK_ADMIN_TOKEN=uzun-gizli-bir-deger   # backend'deki ADMIN_TOKEN ile aynı
KIOSK_ADMIN_PASSWORD=personel-parolasi   # /stock giriş parolası
TZ=Europe/Istanbul
```

### 3. Başlat

```bash
docker compose up -d --build
```

- Arayüz: `http://<sunucu-ip>:8088`
- API: `http://<sunucu-ip>:8000`
- API dokümanı: `http://<sunucu-ip>:8000/docs`

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

## Sunucu yeniden başladığında otomatik açılma

İki koşulun İKİSİ birden gerekli — biri eksikse konteynerler kalkmaz.

**1. Konteynerlerde yeniden başlatma politikası** (compose'da hazır):

```yaml
restart: unless-stopped
```

**2. Docker servisi açılışta etkin olmalı** — bunu bir kez elle yapın:

```bash
sudo systemctl enable docker
sudo systemctl is-enabled docker      # "enabled" yazmalı
```

Çoğu dağıtımda Docker kurulunca zaten etkinleşir, ama doğrulamadan
güvenmeyin: `is-enabled` "disabled" derse sunucu açıldığında Docker
daemon hiç başlamaz ve `restart` politikasının bir anlamı kalmaz.

### `unless-stopped` ile `always` farkı

| Politika | Sunucu yeniden başlarsa | `docker compose stop` sonrası yeniden başlatmada |
|---|---|---|
| `unless-stopped` | kalkar | **kalkmaz** (bilinçli durdurulmuş sayılır) |
| `always` | kalkar | kalkar |

`unless-stopped` daha doğru seçim: bakım için elle durdurduğunuz bir
konteyneri sunucu her açıldığında geri getirmez.

### Doğrulama

Sunucuyu gerçekten yeniden başlatmadan test edin:

```bash
sudo systemctl restart docker
sleep 20
docker compose ps                     # ikisi de "Up" olmalı
```

Gerçek sınama ise yeniden başlatmanın kendisidir:

```bash
sudo reboot
# tekrar bağlanınca:
docker compose ps
docker compose logs --since 5m backend | head -40
```

### Açılış sırası

`depends_on` yalnızca **başlatma sırasını** belirler; frontend backend'in
sağlıklı olmasını beklemez. Bu bilinçli: arayüz backend'e ulaşamadığında
ekranı açıp kırmızı uyarı şeridi göstermek üzere tasarlandı. Sağlık
koşulu olsaydı backend bozukken kiosk ekranı hiç açılmaz, personel siyah
ekranla kalırdı.

---

## Sık karşılaşılan sorunlar

| Belirti | Sebep / çözüm |
|---|---|
| Arayüz açılıyor ama "Servise bağlanılamıyor" | `KIOSK_API_URL` `localhost` kalmış olabilir — sunucunun LAN IP'si olmalı. Ya da `CORS_ORIGINS` arayüz adresini (`:8088`) içermiyordur. |
| `/stock` yenileyince 404 | nginx.conf SPA fallback ile bunu çözüyor; imaj güncel mi kontrol edin (`--build`) |
| Backend açılışta çöküyor | `.env` eksik olabilir. `backend/wmf/.env` var mı? |
| Robot/syrup bağlanmıyor | Cihaz IP'leri `.env`'de doğru mu? Değilse `network_mode: host` deneyin |
| Değişiklik görünmüyor | `docker compose up -d --build` ile yeniden derleyin |
