# Barista Robot Service — tam paket (temizlenmiş)

Çalışan uygulamanın **tamamı**, fazlası olmadan. `backend/` ve
`frontend/` klasörlerini repodaki karşılıklarıyla doğrudan
değiştirebilirsiniz.

İçerik: Aşama 0 (güvenlik/derleme) + Aşama 1 (açık tema) + modüler
backend yapısı + blokeli ekran davranışı.

**Doğrulandı:** `python -c "import app"` → 37 uç ·
`npm install && npm run build` → başarılı · `npx eslint src/` → temiz

---

## Kurulum

```bash
cp -r backend/  /repo/yolu/barista_robot_service/
cp -r frontend/ /repo/yolu/barista_robot_service/

# Backend
cd /repo/yolu/barista_robot_service/backend/wmf
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"   # ADMIN_TOKEN
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000

# Frontend
cd ../../frontend
cp .env.example .env          # VITE_API_URL
npm install
npm run dev -- --host
```

### Repodan silinecek eski dosyalar

```bash
cd backend/wmf
rm -f services.py helper.py order_utils.py __version__.py \
      config.py catalog.py database.py security.py \
      robot_manager.py connect_robot.py coffee_service.py \
      machine_monitor.py machine_info_service.py syrup_service.py \
      stock_service.py order_service.py
rm -rf routers/

cd ../../frontend
rm -f yarn.lock src/App.css src/styles/GlobalStyle.js
rm -f src/pages/Home_1.jsx src/pages/Home_2.jsx src/pages/Home_3.jsx \
      src/pages/Test.jsx src/components/modal/Processing.jsx \
      src/helper/Beverages_2.js
```

---

## ⚠️ Hâlâ bekleyen iş

`database.py` içindeki Atlas kullanıcı adı + parolası public repoya
commit edilmişti. Kod artık `.env`'den okuyor ama **eski parola git
geçmişinde duruyor.** Atlas → Database Access → parolayı değiştirin.

---

## Bu sürümde temizlenenler

### Silinen dosyalar (~4600 satır ölü kod)

| Dosya | Neden |
|---|---|
| `Home_1.jsx`, `Home_2.jsx`, `Home_3.jsx` | `Home.jsx`'in mükerrer kopyaları, ~1120 satır ×3 |
| `Test.jsx` | kategori/sayfalama denemesi, mantığı `Home.jsx`'e alındı |
| `Processing.jsx` | kullanılmayan modal, yerini `PreparingCoffee.jsx` aldı |
| `Beverages_2.js` | `Beverages.js`'in eski kopyası |
| `App.css` | tamamı yorum satırıydı |
| `styles/GlobalStyle.js` | boş dosya |
| `yarn.lock` | `package-lock.json` ile çakışıyordu |

Bunlar git geçmişinizde duruyor; gerekirse
`git show HEAD:frontend/src/pages/Home_1.jsx` ile geri alabilirsiniz.

### Silinen görseller (2.4 MB)

Hiçbir yerden referans verilmiyorlardı:

| Dosya | Boyut |
|---|---|
| `coffee_beans_pattern.jpg` | **2.0 MB** |
| `CoffeeTea.json` | 252 KB (Lottie — artık kullanılmıyor) |
| `hot_chocolate.webp` | 40 KB |
| `Correct.json` | 24 KB (Lottie) |
| `coffee-beans.png` | 16 KB |
| `beverage_list_icon.png`, `chocolate.png`, `milk.png` | 8 KB ×3 |

`src/assets/` 4.5 MB → **2.1 MB**.

### Kaldırılan npm paketleri

`@reduxjs/toolkit`, `react-redux`, `react-i18next`, `react-icons`,
`react-slick`, `lottie-react`, `date-fns`, `yup`, `uid`, `version`

Hiçbiri koddan import edilmiyordu. `version` paketi muhtemelen
yanlışlıkla kurulmuştu.

`@emotion/react` ve `@emotion/styled` **kaldırılmadı** — doğrudan import
edilmiyorlar ama MUI'nin stil motoru, onlarsız derleme çalışmaz.

Kalan bağımlılıklar: `@mui/material`, `@mui/icons-material`,
`@emotion/*`, `axios`, `react`, `react-dom`, `react-router-dom`,
`react-toastify`.

---

## Temizlik sırasında çıkan hatalar

Bağımlılıklar yeniden kurulunca daha sıkı bir `react-hooks` sürümü geldi
ve `StockManagement.jsx`'te dört eski sorun ortaya çıktı:

**1. Render sırasında bileşen tanımlanıyordu.**

```jsx
const OverallPill = () => (<span className={...}>...</span>);
```

Her render'da yeni bir bileşen tipi doğuyor, React eskisini söküp
yenisini takıyordu. Düz JSX ifadesine çevrildi.

**2. Fonksiyon tanımlanmadan önce çağrılıyordu.** Oturum geri yükleme
effect'i `startSessionTimer`'ı, tanımından 20 satır önce çağırıyordu.
Effect'ler render sonrası çalıştığı için kazara işliyordu, ama kod biraz
yer değiştirse çalışma anında hata verirdi.

**3. Oturum geri yükleme fazladan render turu doğuruyordu.** Giriş ekranı
bir kare boyunca yanıp sönüyordu. `useState` başlangıç fonksiyonuna
taşındı.

**4. Render sırasında ref'e yazılıyordu.** Başlangıç fonksiyonu artık
sadece değer döndürüyor.

---

## Yapı

```
backend/wmf/
├── app.py
├── core/       config, catalog, database, security, version,
│               logging, machine_errors, ws_utils
├── service/    registry, robot_manager, connect_robot, coffee_service,
│               machine_monitor, machine_info_service, syrup_service,
│               syrup_recipes, stock_service, order_service
├── route/      order, machine, stock, syrup
└── sdk/        Fairino SDK (satıcı kodu, dokunulmadı)

frontend/
├── index.html, vite.config.js, package.json, eslint.config.js
├── Dockerfile, nginx.conf, .env.example
└── src/
    ├── theme.js              açık tema paleti — tek renk kaynağı
    ├── api/client.js         backend adresi, uçlar, hata metinleri
    ├── components/
    │   ├── CupFill.jsx       ürün görseli üzerinde dolum
    │   ├── SystemBanner.jsx  üst uyarı şeridi
    │   └── modal/            PreparingCoffee, ProductDetail, Alert
    ├── pages/                Home.jsx, StockManagement.jsx
    └── helper/               Beverages.js, toastify.js
```

Bağımlılık yönü tek yönlüdür: `route → service → core`

---

## Blokeli ekran

Makineye veya robota ulaşılamadığında ekran artık boş kalmıyor. Menü
görünür kalıyor, üstte kırmızı şerit çıkıyor ve içerik %35 opaklığa inip
dokunmaya kapanıyor.

| Durum | Şerit | Ekran |
|---|---|---|
| İlk yükleme | koyu, yanıp sönen nokta | bloke |
| Backend'e ulaşılamıyor | **kırmızı** + teknik detay | bloke |
| Makine çevrimdışı / hatalı / temizlikte | **kırmızı** + hata açıklaması | bloke |
| Robot manuel veya hazır değil | **kırmızı** | bloke |
| Stok tükendi | **kırmızı** + hangi malzeme | bloke |
| Süt/çikolata azaldı | kehribar | **açık** |

Üst çubuk (logo, dil) bloke durumda da çalışır. Sipariş sürerken şerit
bastırılır — robot o sırada meşgul olduğu için `can_order` geçici olarak
`false` dönüyor ve bu önlem olmasa her siparişin sonunda şerit bir an
yanıp sönerdi.

---

## Hazırlanma göstergesi

Ürün görselleri **değiştirilmedi**. `CupFill` aynı görseli iki kez render
eder: alttaki gri ve soluk, üstteki tam renkli ve `clip-path` ile alttan
yukarı açılıyor.

Saniye sayacı ve robot günlüğü yok — ilerleme yalnızca dolumla
anlatılıyor. Backend'in `timer_38s` fazındaki süre ekranda gösterilmez,
sadece animasyonun o süreye yayılması için kullanılır.

---

## Çevrimdışı test modu

Backend, kahve makinesi ve robot olmadan tasarımı denemek için.
**Sahteye alınan servisler için hiçbir ağ isteği yapılmaz** — yanıtları
`src/api/mock.js` üretir.

### En hızlı yol — URL parametresi

```
http://localhost:5173/?offline=1
http://localhost:5173/?offline=1&scenario=machine-error
http://localhost:5173/?offline=1&speed=0.2
```

`.env` düzenlemeye ve sunucuyu yeniden başlatmaya gerek yok.

### Kalıcı yol — .env

```dotenv
VITE_OFFLINE=true
VITE_OFFLINE_SCENARIO=ok
VITE_OFFLINE_SPEED=1
```

⚠️ **Dev sunucusunu yeniden başlatın.** Vite `.env` dosyasını yalnızca
sunucu açılırken okur.

### Servis bazlı anahtarlar

Her servis ayrı ayrı sahteye veya gerçeğe alınabilir. Genel anahtar
varsayılandır; servis bazlı ayar onu ezer.

```dotenv
# Makine ve robot masanızda yok, backend + MongoDB çalışıyor
VITE_OFFLINE=false
VITE_OFFLINE_MACHINE=true
VITE_OFFLINE_ROBOT=true

# Her şey sahte olsun ama gerçek stok verisiyle çalışayım
VITE_OFFLINE=true
VITE_OFFLINE_STOCK=false
```

URL karşılıkları — `mock` listesi `live` listesinden önceliklidir:

```
?offline=1&live=stock            stok gerçek, kalanı sahte
?mock=machine,robot              yalnızca makine ve robot sahte
```

| Servis | Kapsadığı uçlar |
|---|---|
| `machine` | `/machine/*` |
| `robot` | `/robot/*` |
| `stock` | `/stock/*` |
| `syrup` | `/syrup/*` |
| `order` | `/order_standart`, `/order/status/*`, `/check_beverage` |

Ekranın üstündeki şerit hangi servislerin sahte olduğunu yazar; hepsi
sahteyse "hiç ağ isteği yapılmıyor" der. Konsola da çözümlenmiş ayarlar
basılır.

### Senaryolar

| Değer | Ne denenir |
|---|---|
| `ok` | normal akış (varsayılan) |
| `no-service` | backend'e hiç ulaşılamıyor → kırmızı şerit |
| `machine-offline` | kahve makinesi çevrimdışı |
| `machine-error` | engelleyici hata (kod 68 + 80), açıklamasıyla |
| `cleaning` | makine temizlik modunda |
| `robot-manual` | robot manuel modda |
| `low-stock` | süt + çikolata eşiğin altında → kehribar şerit, kısmi kilit |
| `out-of-stock` | bardak bitti → tam kilit |
| `order-error` | sipariş demleme ortasında hata veriyor |

`speed=0.2` beş kat hızlandırır.

### Nasıl çalışıyor

`api/client.js` bir **istek interceptor**'ı kurar: her istekte yolun
hangi servise ait olduğuna bakar ve yalnızca o servis sahteye
alınmışsa `config.adapter`'ı mock'a çevirir. Atanmayan istekler
axios'un normal adapter'ıyla gerçek backend'e gider.

Adapter'ı global olarak değiştirmek yerine bu yolun seçilmesinin
sebebi karma çalışmayı mümkün kılmak. **`Home.jsx` ve
`StockManagement.jsx`'te tek satır değişmez** — normal isteklerini
atmaya devam ederler.

Sipariş, backend'in ürettiği sekiz fazın hepsinden gerçek sürelerle
geçer: `created → set_do0_true → wait_di1_robot_ready →
coffee_task_start → timer_23s → set_do2_true → wait_di3_robot_done →
robot_delivered`. Stok gerçekten düşer, `/stock/refill` ile geri dolar.

Doğrulandı: bayrak okuma (7 yazım), URL geçersiz kılma (6 kombinasyon),
servis yönlendirmesi (env + URL) ve gerçek axios ile uçtan uca karma
mod — makine/robot mock'tan dönerken stok isteği ağa çıkıp
`ECONNREFUSED` aldı.

### Çalışmıyorsa — teşhis

Adrese `?debug=1` ekleyin. Ekranın sağ altında uygulamanın **o anda
kullandığı** değerleri gösteren bir panel açılır:

```
TEŞHİS · ?debug=1
API adresi     http://10.34.2.121:8000
çevrimdışı     hepsi sahte        <- "KAPALI" yazıyorsa ayar okunmamış
makine         sahte
robot          sahte
ekran          açık
```

Kiosk dokunmatik panelde geliştirici araçlarını açmak zahmetli olduğu
için bu panel var.

**Panel "çevrimdışı KAPALI" diyorsa** ayar uygulamaya ulaşmamış demektir.
Sırayla kontrol edin:

1. **`?offline=1` ile deneyin.** Çalışıyorsa sorun kesinlikle `.env`
   yüklenmesinde, kodda değil.
2. **`.env` dosyası `frontend/` klasöründe mi?** Repo kökünde veya
   `src/` içindeyse Vite görmez. `.env.example` düzenlemek de işe
   yaramaz — dosyanın adı tam olarak `.env` olmalı.
3. **Dev sunucusunu yeniden başlattınız mı?** Vite `.env`'i yalnızca
   açılışta okur.
4. **Derlenmiş `dist/` mi servis ediliyor?** Vite değerleri *derleme
   anında* gömer; sonradan `.env` değiştirmek etkilemez. Yeniden
   `npm run build` gerekir.
5. **BOM'lu dosyada ilk satır değişkense** o değişken okunmaz. Dosyayı
   yorum satırıyla başlatın veya BOM'suz UTF-8 kaydedin.

Bloke şeridi artık kaynağı da yazıyor: bir servis sahte değilken hata
veriyorsa `gerçek servis · http://10.34.2.121:8000` satırı çıkar.
"Makine gerçekten kapalı mı, yoksa mock'u açmayı mı unuttum" sorusu
böylece anında cevaplanır.

### Bayrak okuma düzeltildi

Önceki sürüm `String(v) === "true"` karşılaştırması yapıyordu ve
şunların hepsi **sessizce** başarısız oluyordu:

| Yazım | Önce | Şimdi |
|---|---|---|
| `VITE_OFFLINE=true` | ✅ | ✅ |
| `VITE_OFFLINE=TRUE` | ❌ | ✅ |
| `VITE_OFFLINE=1` | ❌ | ✅ |
| `VITE_OFFLINE=true ` (sondaki boşluk) | ❌ | ✅ |

Sondaki boşluk en sinsisi — editörde görünmüyor. Değerler artık
kırpılıyor ve `true / 1 / yes / on` kabul ediliyor.

Ayrıca ağ hatası mesajı denenen adresi de gösteriyor
(`http://192.168.1.40:8000 adresine ulaşılamıyor.`).


---

## Bardak görselleri

`hot_cup` ve `ice_cup` eklendi. İçecek kayıtlarında görsel tek tek
yazılmıyor, `temperature` alanından türetiliyor:

```js
temperature: "iced"   →  ice_cup   (kart alt şeridi kırmızı)
temperature: "hot"    →  hot_cup   (kart alt şeridi fıstık yeşili)
```

Yeni içecek eklerken `image` alanı vermeniz gerekmez.

**Optimizasyon:** Yüklediğiniz PNG'ler 704 KB ve 907 KB idi. Görüntüde
kayıp olmadan WebP'ye çevrildi ve 900 px yüksekliğe indirildi:
**1.6 MB → 27 KB.** Alfa kanalı kart zeminiyle birleştirildi, böylece
şeffaflık yerine kağıt tonu kaldı.

**Tema uyumu:** Fotoğrafların arka planı `#E7DFD4`. `theme.js`
içindeki `paper` bu değere tam eşitlendi (önceden `#E7E1D5` idi) —
görseller kartlara çerçevesiz oturuyor. Görselleri değiştirirseniz bu
tonu da eşitleyin, yoksa kartlarda kutu izi belirir.

Orijinal PNG'ler pakete konmadı (1.6 MB, kullanılmıyorlar) — sizde
zaten varlar. Yeniden üretmek isterseniz:

```python
from PIL import Image
PAPER = (231, 223, 212)   # #E7DFD4
im = Image.open("hot_cup.png")
bg = Image.new("RGB", im.size, PAPER)
bg.paste(im, mask=im.split()[-1])
bg = bg.resize((round(bg.width * 900 / bg.height), 900), Image.LANCZOS)
bg.save("src/assets/hot_cup.webp", "WEBP", quality=86, method=6)
```

**`mug3.svg` silindi** (1.2 MB). Kahve içeceklerinin eski görseliydi,
yerini `hot_cup` aldı ve referansı kalmadı. `src/assets/` artık
**2.1 MB → 890 KB**.

### Soğuk içecekler hakkında

Menüde şu an gerçek soğuk içecek yok. Makinedeki buton numaralarını
bilmediğim için uydurmadım — yanlış numara yanlış içeceğin
hazırlanmasına yol açar.

Bunun yerine `Beverages.js` içinde `demoIcedDrinks` var: Iced
Americano, Iced Latte ve Cold Brew. Bunlar **yalnızca çevrimdışı
modda** menüye ekleniyor, üretimde görünmüyorlar. Buton numaraları
900'lü aralıktan, yani makinede karşılığı olmayan yerden seçildi.

Gerçek soğuk içecekleri eklerken: numaraları makinenin
`getBeverageButtonList` çıktısından doğrulayın, kaydı `beverages.drinks`
listesine taşıyın ve `temperature: "iced"` yazın.

---

## Menü: sıcak / soğuk sekmesi

Kahve kategorisine girildiğinde **Sıcak** ve **Soğuk** sekmeleri çıkar.
Liste `temperature` alanına göre süzülür; alanı olmayan eski kayıtlar
`hot` sayılır.

Sekmeler bardak görselini ve ambalaj aksanını taşır — sıcak fıstık
yeşili, soğuk kırmızı. Geri dönüldüğünde sekme `hot`'a sıfırlanır.

Soğuk sekmesi şu an yalnızca çevrimdışı modda dolu (`demoIcedDrinks`).
Gerçek soğuk içecekleri eklerken buton numaralarını makinenin
`getBeverageButtonList` çıktısından doğrulayıp `beverages.drinks`
listesine `temperature: "iced"` ile ekleyin — görsel ve sekme
kendiliğinden çalışır.

---

## Görseller ve logo

| Yer | Görsel |
|---|---|
| Kahve kategorisi kartı | `hot_cup.webp` (eskiden `coffee.webp`) |
| Dondurma kategorisi kartı | `ice_cream.webp` (değişmedi) |
| Sıcak içecekler | `hot_cup.webp` |
| Soğuk içecekler | `ice_cup.webp` |
| Üst çubuk logosu | `logorob_logo.png` (yeni sembol) |

Dondurma için yeni bir görsel gelmediğinden mevcut `ice_cream.webp`
kaldı. Değiştirmek isterseniz aynı isimle üzerine yazmanız yeterli.

**Logo işlendi.** Gönderilen dosya 1064×240 idi ve sembolün çevresi
beyazdı — koyu üst çubukta beyaz kutu oluştururdu. Beyaz şeffafa
çevrildi, sembol kırpıldı ve 120 px yüksekliğe indirildi (12 KB).
Marka turuncusu `#E65315`.

Yeni logo yalnızca semboldan oluştuğu için geniş çubukta tek başına
kayboluyordu. Referans tasarımdaki masthead deseni uygulandı:
sembol + `LOGOROB` kelime markası + küçük slogan satırı.

**Silinen görsel:** `coffee.webp` (32 KB) — kahve kategorisi artık
`hot_cup.webp` kullandığı için referanssız kaldı. `src/assets/`
içindeki 16 görselin tamamı kullanımda.

---

## Düzeltilen şurup hataları

İkisinin de kaynağı aynıydı: `syrups` ve `souces` kayıtlarında
`name_TR` / `name_EN` vardı ama **`name` alanı yoktu**. Arayüz
`option.name` okuduğu için değer hep `undefined` geliyordu.

**1. Tek şurup seçilince hepsi seçili görünüyordu.**

```js
toggle(undefined)                  // selected = [undefined]
selected.includes(undefined)       // HER seçenek için true
```

**2. Sepette seçilen şurup yerine "Renkli Süsler" yazıyordu.**

```js
extras.find(e => e.name === undefined)   // dizinin İLK elemanı
                                          // = souces[0] = Renkli Süsler
```

Aynı hata fiyat hesabını da bozuyordu — hangi ilave seçilirse seçilsin
ilk kaydın fiyatı ekleniyordu.

**Çözüm:** her ilaveye dile bağlı olmayan kalıcı bir `id` eklendi
(`vanilla`, `caramel`, `sprinkles`…). Arayüz artık isim yerine bunu
taşıyor; `findExtra(id)` ve `extraName(id, lang)` yardımcıları
`Beverages.js`'de.

Gerçek DOM'da uçtan uca doğrulandı:

```
şurup seçenek : 4 adet
seçili görünen: 1 adet → Karamel
sepetteki ilaveler: 1 adet → Karamel        ✅
toplam tutar: 0,02   (0,01 içecek + 0,01 şurup)
```


---

## Menü kategorilerini açıp kapatma

```dotenv
VITE_CATEGORY_COFFEE=true
VITE_CATEGORY_ICECREAM=false
```

URL karşılığı: `?categories=coffee` veya `?categories=coffee,ice_cream`

Boş bırakılan kategori **açık** sayılır. Yalnızca tek kategori açıksa
seçim ekranı atlanır, doğrudan o listeye girilir ve geri butonu
gizlenir — kioskta gereksiz bir dokunuş eksilir.

Doğrulandı:

```
varsayılan          → kategori kartları: Kahve, Dondurma
?categories=coffee  → doğrudan liste + Sıcak|Soğuk sekmeleri, geri butonu yok
?categories=ice_cream → doğrudan dondurma listesi, sekme yok
```

---

## Sürelerin nerede ayarlandığı

Kısa cevap: **süreler frontend'de değil, backend'de.**

| Ne | Nerede |
|---|---|
| **Gerçek demleme süresi** | `backend/wmf/core/catalog.py` → `brew_seconds` |
| Backend'e giden sipariş parametreleri | `frontend/src/pages/Home.jsx` → `buildStartMessage()` |
| Çevrimdışı simülasyon süresi | `frontend/src/api/mock.js` → `BREW_SECONDS` |

Akış şöyle işliyor:

1. `Home.jsx` yalnızca **hangi içecek** ve **hangi parametrelerle**
   bilgisini gönderir — süre göndermez:

   ```js
   { function: "startBeverage", a_iBtnNbr: "3", a_iBarista: "1",
     a_iDecaf: "0", a_iSML: "1", a_iMilktype: "-1", ... }
   ```

2. Backend `catalog.brew_seconds(button)` ile süreyi kendi belirler
   (`service/order_service.py`, ADIM 4) ve faz adına gömer: `timer_40s`.

3. `PreparingCoffee.jsx` bu faz adından süreyi **okur** ama ekranda
   göstermez; yalnızca dolumun o süreye yayılması için kullanır.

Yani süre değiştirmek istediğinizde düzenlenecek tek yer
`core/catalog.py`:

```python
{ "button": 3, "recipe": 91, "name_tr": "Latte", ..., "brew_seconds": 40 }
```

⚠️ **Dikkat edilecek çoğaltma:** `mock.js` içindeki `BREW_SECONDS`
tablosu ile `Beverages.js` içindeki `ButtonNumber` / `RecipeNumber`
değerleri `catalog.py`'nin kopyasıdır ve elle senkron tutulmaları
gerekir. Aşama 3'te eklenecek `/catalog` ucu bu çoğaltmayı bitirecek:
arayüz menüyü ve süreleri backend'den alacak.


---

## Şurup görselleri belirginleştirildi

Şişe görselleri **119×500**, yani 1:4,2 oranında. Kartlardaki görsel
alanı 58×50 idi; `objectFit: contain` ile şişe ~12×50 piksele iniyor,
neredeyse görünmez oluyordu.

| | Önce | Sonra |
|---|---|---|
| Görsel alanı yüksekliği | 50 px | **116 px** |
| Kart genişliği | 148 px | 156 px |
| Modal genişliği | 620 px | 720 px |

Ek olarak şişenin arkasına hafif bir daire, altına yumuşak bir gölge
kondu; seçilince hafifçe büyüyor. Sos görselleri (fotoğraf, şeffaf
değil) hafifçe yuvarlatıldı — ham kutu gibi durmuyorlar. Şeffaf
şişelerde bunun görünür etkisi yok.

---

## Dondurma görselleri birleştirildi

Üç dondurma da ana menüdeki `ice_cream.webp` görselini kullanıyor.
Ayrı `vanilla_ice_cream.webp`, `chocolate_ice_cream.webp` ve
`mix_ice_cream.webp` referanssız kaldığı için silindi (112 KB).

Sos fotoğrafları da WebP'ye alındı:

| Dosya | Önce | Sonra |
|---|---|---|
| `findik_kiriklari` | 236 KB JPG | **80 KB** WebP |
| `springles` | 53 KB JPG | 45 KB WebP |

`src/assets/` 928 KB → **652 KB**. 13 görselin tamamı kullanımda.


---

## Düzeltilen hatalar (tüm paket)

| # | Hata | Sonucu |
|---|---|---|
| 1 | `requirements.txt` UTF-16 kodlu | Docker imajı hiç kurulamıyordu |
| 2 | `motor`/`pymongo`/`dnspython` eksik | konteyner ilk import'ta çöküyordu |
| 3 | `MachineMonitor` başlatılmıyordu | ama `order_service` `get_state()` çağırıyordu |
| 4 | Şurup tarifi `ml` yazılıyor, `qty_ml` okunuyordu | tarifli **her** sipariş `KeyError` |
| 5 | `getRecipeComposition`'a ButtonNumber gidiyordu | Espresso hariç stok yanlış düşüyordu |
| 6 | `PreparingCoffee` ve `Alert` yorum satırındaydı | sipariş sonrası geri bildirim yoktu |
| 7 | `ProductDetail` `item.Name` okuyordu | ürün adı/açıklaması boş çıkıyordu |
| 8 | Sepet siparişin başında temizleniyordu | hata alınca müşterinin seçimi siliniyordu |
| 9 | `order_service` → `routers.syrup` importu | servis, rotadan veri okuyordu |
| 10 | `/stock` yenilenince 404 | nginx SPA geri düşüşü yoktu |
| 11 | Backend adresi 3 dosyada sabitti | IP değişince biri hep unutuluyordu |
| 12 | `config.py` iki farklı buton numaralandırması | btn 1 hem Espresso hem "Soğuk süt" |
| 13 | `OverallPill` render sırasında yaratılıyordu | her render'da yeniden takılıyordu |
| 14 | `startSessionTimer` tanımından önce çağrılıyordu | kırılgan, yeri değişse çöker |

---

## Bilinmesi gerekenler

**`StockManagement.jsx` içindeki `ADMIN_PASSWORD` gerçek koruma değil.**
Tarayıcıda çalışan bir sabit, derlenmiş pakette açıkça görünür. Asıl
koruma backend'deki `X-Admin-Token` — Aşama 3'te `/stock/*` yazma
uçlarına takılacak.

**Şurup ayarları bellekte.** Kanal adları ve içecek tarifleri servis
yeniden başlayınca sıfırlanır. MongoDB'ye taşınması Aşama 5'te.

**Fontlar çevrimdışında yüklenmez.** Anton / Inter Tight / JetBrains Mono
Google Fonts'tan geliyor. Kalıcı çözüm: font dosyalarını `public/fonts/`
altına indirip `index.html`'deki `<link>` satırını yerel `@font-face` ile
değiştirin.

**`mug3.svg` 1.2 MB.** Artık `src/assets/`'in yarısından fazlası tek bu
dosya. Görselleri değiştirmemenizi istediğiniz için dokunmadım, ama
sadeleştirilirse paket boyutu yarıya iner.

**`StockManagement.jsx` açık temaya taşınmadı** — personel ekranı, kiosk
değil. Aşama 5'te yönetici paneliyle ele alınacak.

---

## Sırada

| Aşama | İçerik |
|---|---|
| **2** | Faz eşlemesi backend'e, SSE (`/order/stream`), job TTL temizliği |
| **3** | Stok: sunucu tarafı kapı, rezerve/kesinleştir/iade, `/stock/*` token koruması |
| **4** | `startPushDispensing*` ile sabit timer'ların kaldırılması |
| **5** | Yönetici paneli, sipariş iptali, şurup ayarlarının kalıcılığı |
