# Syrup sistemi — manuel test rehberi

> **Postman kullanıcıları:** Aynı klasördeki
> `Syrup.postman_collection.json` dosyasını Postman'da **Import** edin —
> tüm uçlar hazır örnek body'lerle gelir. İçe aktardıktan sonra
> collection değişkenlerini kontrol edin:
> - `baseUrl` → sunucu adresi (varsayılan `http://127.0.0.1:8000`, sonda `/` olmadan)
> - `adminToken` → backend `.env` içindeki `ADMIN_TOKEN` ile aynı olmalı
>   (yalnızca "Stok — Kanal Güncelle" isteği kullanır)


LogoSurup dispenser uçlarını elle denemek için. Fiziksel cihaz olsun
olmasın çalışır; cihaz yoksa uçlar `ok:false` veya `503` döner, sunucu
çökmez.

---

## 1. Sunucuyu çalıştır

Çalıştırılacak dosya `app.py`. Klasör: `backend/wmf/`.

```bash
cd backend/wmf

# bağımlılıklar (bir kez)
pip install -r requirements.txt

# sunucu
uvicorn app:app --host 0.0.0.0 --port 8000
```

Geliştirirken otomatik yeniden başlatma için:

```bash
uvicorn app:app --reload --port 8000
```

### Yalnızca syrup'ı test edeceksen

`app.py` açılışta robota ve kahve makinesine de bağlanmaya çalışır;
bunlar yoksa loglar bağlantı denemeleriyle dolar (işlevi engellemez).
Sadece syrup ile ilgileniyorsan `.env` içinde şunları vererek gürültüyü
kısabilirsin:

```dotenv
MONGO_ENABLED=false
LOG_LEVEL=WARNING
SYRUP_HOST=192.168.1.155   # cihazın gerçek IP'si
SYRUP_PORT=5000
```

---

## 2. En kolay yol — Swagger

Tarayıcıda:

```
http://localhost:8000/docs
```

Bütün `/syrup/*` uçları formlarla listeli. "Try it out" → değerleri
gir → "Execute". curl bilmeye gerek yok.

---

## 3. curl ile

Aşağıdaki örneklerde sunucu `localhost:8000` varsayılıyor.

### Bağlantı testi — cihaz ayakta mı

```bash
curl http://localhost:8000/syrup/ping
```

Cihaz varsa:
```json
{ "ok": true, "pong": true, "host": "192.168.1.155", "port": 5000 }
```

Cihaz yoksa (200 döner, `ok:false` ile bildirir):
```json
{ "ok": false, "pong": false, "error": "Syrup bağlantı reddedildi (...)" }
```

### Motorların bağlantı durumu

```bash
curl http://localhost:8000/syrup/motors
```

Hangi kanalda şişe takılı olduğunu `EVT:IO:PRESENCE` üzerinden okur.
Cihaz kapalıysa `503` döner.

### Şurup akıt — asıl test

`motor` (veya `channel`) 1–8, `ml` > 0.

```bash
curl -X POST http://localhost:8000/syrup/dispense \
  -H "Content-Type: application/json" \
  -d '{"motor": 1, "ml": 5}'
```

Alan adları esnek — şu ikisi aynı şeyi yapar:

```bash
curl -X POST http://localhost:8000/syrup/dispense \
  -H "Content-Type: application/json" \
  -d '{"channel": 3, "qty_ml": 12.5, "timeout": 20}'
```

Başarılı:
```json
{ "ok": true, "channel": "01", "qty_ml": 5.0, "duration_ms": 700,
  "motor": 1, "channel_name": "Vanilya" }
```

### Kanal yapılandırması

```bash
curl http://localhost:8000/syrup/config

curl -X PUT http://localhost:8000/syrup/config/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Vanilya", "description": "Şişe 1", "color": "#FFD700"}'
```

### İçecek → şurup tarifi

`button_number` içeceğin buton numarası (ör. Latte = 3).

```bash
curl http://localhost:8000/syrup/recipes

# Latte'ye 1. kanaldan 8 mL vanilya
curl -X PUT http://localhost:8000/syrup/recipes/3 \
  -H "Content-Type: application/json" \
  -d '{"channel": 1, "ml": 8, "note": "Latte vanilya"}'

curl -X DELETE http://localhost:8000/syrup/recipes/3
```

### Anlık takılma/çıkarma akışı (SSE)

Şişe takıp çıkardıkça olayları canlı yayınlar:

```bash
curl -N http://localhost:8000/syrup/presence/stream
```

`-N` tamponlamayı kapatır; olaylar geldikçe akar. Durdurmak için
Ctrl-C.

---

## 4. Hata kodları

| Kod | Anlamı |
|-----|--------|
| 200 | Başarılı (ping cihaz kapalıyken de 200 + `ok:false`) |
| 422 | Geçersiz istek — eksik `motor`/`ml`, ya da motor 1–8 dışında |
| 503 | Cihaza ulaşılamıyor (`/motors`, `/dispense`) |
| 504 | Cihaz yanıt verdi ama zaman aşımına uğradı |

Cihaz protokol düzeyinde hata dönerse (`RSP:...:ERR:...`) yanıt
gövdesinde `source: "syrup_device"`, `error_code` ve `description`
bulunur.

---

## 5. Hızlı duman testi

Cihaz bağlıyken sırasıyla:

```bash
curl http://localhost:8000/syrup/ping          # ok:true olmalı
curl http://localhost:8000/syrup/motors         # takılı şişeler
curl -X POST http://localhost:8000/syrup/dispense \
  -H "Content-Type: application/json" -d '{"motor":1,"ml":3}'
```

Üçüncüsü fiziksel olarak 3 mL akıtmalı. Akmadıysa: `motors` çıktısında
o kanal `connected:true` mi, `ml` değeri makul mü, cihaz log'unda hata
var mı diye bak.

---

## Hortum bakımı — PRIME / RETRACT

```bash
# Vardiya başı — hortum uçlarına şurup getir
curl -X POST http://localhost:8000/syrup/prime

# Vardiya sonu — hortumdaki şurubu kaba geri çek
curl -X POST http://localhost:8000/syrup/retract
```

Yalnızca süresi>0, takılı ve kalibre kanallar dahil edilir. Uygun kanal
yoksa cihaz E502 (422) döner. Yanıt `channel_count` ve `done_channels`
içerir.

---

## Hortum temizliği — CLEAN (çok adımlı)

Temizlik operatör müdahalesi gerektirir; adımlar arasında cihaz durup
hortumun ilgili kaba daldırılmasını bekler. Sıra:

```bash
# 0) (opsiyonel) önceki temizlik yarıda kalmış mı — dozaj kilidi kontrolü
curl http://localhost:8000/syrup/clean/lastresult

# 1) başlat → cihaz WAIT_SOAP durumuna gelir
curl -X POST http://localhost:8000/syrup/clean/start

# 2) hortumu DETERJANLI suya daldır, sonra onayla → yıkama, WAIT_WATER
curl -X POST http://localhost:8000/syrup/clean/ack-soap

# 3) hortumu TEMİZ suya daldır, sonra onayla → durulama, COMPLETE
curl -X POST http://localhost:8000/syrup/clean/ack-water

# durum sorgulama (bağlantı koptuysa kaldığın yeri öğren)
curl http://localhost:8000/syrup/clean/status

# iptal (bekleme sırasında istediğin an)
curl -X POST http://localhost:8000/syrup/clean/abort
```

**Dozaj kilidi:** Temizlik yarıda kalırsa (elektrik kesintisi vb.)
hatlarda deterjan kalabilir. Cihaz `blocked=1` bildirir ve her dozajı
E506 (HTTP 423) ile reddeder. Kilit, yeni bir temizliğin başarıyla
tamamlanmasıyla kalkar.
