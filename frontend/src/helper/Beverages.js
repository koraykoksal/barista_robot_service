import hot_cup            from "../assets/hot_cup.webp";
import ice_cream_cup      from "../assets/ice_cream.webp";
import ice_cup            from "../assets/ice_cup.webp";
import springles          from "../assets/springles.webp";
import badem_kiriklari    from "../assets/badem_kiriklari.webp";
import findik_kiriklari   from "../assets/findik_kiriklari.webp";
import vanilla_syrup      from "../assets/vanilla_syrup.png";
import caramel_syrup      from "../assets/caramel_syrup.png";
import chocolate_syrup    from "../assets/chocolate_syrup.png";
import white_chocolate_syrup from "../assets/white_chocolate_syrup.png";
// Fındık şurubu kaydı aşağıda yorum satırında (kanal 5) — kayıt geri
// açılırsa bu import da açılmalı.
// import hazelnut_syrup from "../assets/hazelnut_syrup.png";
import strawberry_syrup from "../assets/strawberry_syrup.png";



// ─────────────────────────────────────────────
// BARDAK GÖRSELİ
//
// Kahve içeceklerinin görseli tek tek yazılmaz; temperature alanından
// türetilir. Yeni bir içecek eklerken image alanı vermeniz gerekmez —
// temperature: "iced" yazmanız yeterli, soğuk bardak otomatik gelir.
//
// Fotoğrafların arka planı #E7DFD4 ve tema paper rengiyle birebir aynı;
// bu yüzden kartlara çerçevesiz oturuyorlar. Görselleri değiştirirseniz
// theme.js içindeki paper tonunu da eşitleyin, yoksa kartlarda kutu izi
// belirir.
// ─────────────────────────────────────────────
export const cupImage = (temperature) => (temperature === "iced" ? ice_cup : hot_cup);

// ─────────────────────────────────────────────
// Dil seçimine göre isim ve açıklama okumak için yardımcı
// Kullanım: getName(item, language)  → item.Name_TR veya item.Name_EN
// ─────────────────────────────────────────────
export const getName        = (item, lang = "TR") => item[`Name_${lang}`]        ?? item.Name        ?? "";
export const getDescription = (item, lang = "TR") => item[`description_${lang}`] ?? item.description ?? "";

// ─────────────────────────────────────────────
// RETURNVALUE mesajları (checkBeverage API)
// ─────────────────────────────────────────────
const RETURNVALUE_MESSAGES = {
    0:  "Success",
    1:  "Makine çevrimdışı.",
    2:  "Makine hazır değil.",
    3:  "Makine başlatılmamış.",
    4:  "Engelleyici hata var.",
    5:  "Başlatma başarısız.",
    6:  "Başka bir içecek hazırlanıyor.",
    7:  "Parametre hatası.",
    8:  "İçecek çalışmıyor.",
    9:  "Başarısız.",
    10: "Fonksiyon meşgul.",
    11: "Fonksiyon mevcut değil.",
    12: "Token geçersiz.",
    13: "Tarif numarası mevcut değil.",
    14: "Bu işlem için ana ekranın aktif olması gerekiyor.",
};

export const buildCheckBeverageMessage = (result) => {
    const code   = result?.returnvalue;
    const detail = RETURNVALUE_MESSAGES[code] ?? `Bilinmeyen hata kodu: ${code}`;
    return `${detail}\nStatus: ${result?.status} (code=${code})`;
};

// ─────────────────────────────────────────────
// BEVERAGES
// ─────────────────────────────────────────────
export const beverages = {

    categories: [
        { id: 1, name_TR: "Kahve",    name_EN: "Coffee",    type: "coffee"    },
        // { id: 2, name_TR: "Dondurma", name_EN: "Ice Cream", type: "ice_cream" },
    ],

    drinks: [
        {
            ButtonNumber  : 1,
            CupSizes      : [{ CupSize: "Regular", PLU: 1, SKU1: "1", SKU2: "" }],
            Name_TR       : "Espresso",
            Name_EN       : "Espresso",
            description_TR: "İnce öğütülmüş kahveden hazırlanan yoğun ve güçlü saf bir içecek.",
            description_EN: "A rich and intense single shot of finely ground coffee, served pure and strong.",
            RecipeNumber  : 1,
            milk          : false,
            caffeine_TR   : "Yüksek",
            caffeine_EN   : "High",
            temperature   : "hot",
            image         : cupImage("hot"),
            published     : true,
            type          : "coffee",
            price         : "0,00",
        },
        {
            ButtonNumber  : 2,
            CupSizes      : [{ CupSize: "Regular", PLU: 5, SKU1: "5", SKU2: "" }],
            Name_TR       : "Americano",
            Name_EN       : "Americano (Café Crème)",
            description_TR: "Taze espresso üzerine sıcak su eklenerek hazırlanan dengeli bir kahve.",
            description_EN: "A smooth and balanced coffee made by adding hot water to a fresh espresso shot.",
            RecipeNumber  : 5,
            milk          : false,
            caffeine_TR   : "Orta",
            caffeine_EN   : "Medium",
            temperature   : "hot",
            image         : cupImage("hot"),
            published     : true,
            type          : "coffee",
            price         : "0,00",
        },
        {
            ButtonNumber  : 3,
            CupSizes      : [{ CupSize: "Regular", PLU: 12, SKU1: "12", SKU2: "" }],
            Name_TR       : "Latte",
            Name_EN       : "Latte",
            description_TR: "Espresso ve buharda ısıtılmış sütle hazırlanan, üzeri hafif köpüklü kremsi bir kahve.",
            description_EN: "A creamy coffee made with espresso and steamed milk, topped with a light milk foam.",
            RecipeNumber  : 91,
            milk          : true,
            caffeine_TR   : "Orta",
            caffeine_EN   : "Medium",
            temperature   : "hot",
            image         : cupImage("hot"),
            published     : false,
            type          : "coffee",
            price         : "0,00",
        },
        {
            ButtonNumber  : 12,
            CupSizes      : [{ CupSize: "Regular", PLU: 10, SKU1: "10", SKU2: "" }],
            Name_TR       : "Cappuccino",
            Name_EN       : "Cappuccino",
            description_TR: "Espresso, buharda ısıtılmış süt ve kalın köpükten oluşan klasik bir kahve.",
            description_EN: "A classic espresso drink with steamed milk and a thick layer of milk foam for a rich, balanced taste.",
            RecipeNumber  : 88,
            milk          : true,
            caffeine_TR   : "Orta",
            caffeine_EN   : "Medium",
            temperature   : "hot",
            image         : cupImage("hot"),
            published     : false,
            type          : "coffee",
            price         : "0,00",
        },
        {
            ButtonNumber  : 5,
            CupSizes      : [{ CupSize: "Regular", PLU: 3, SKU1: "3", SKU2: "" }],
            Name_TR       : "Ristretto",
            Name_EN       : "Ristretto",
            description_TR: "Yoğun ve konsantre bir espresso çekimi, güçlü ve cesur bir tat sunar.",
            description_EN: "A very short and concentrated espresso shot with an intense and bold flavor.",
            RecipeNumber  : 3,
            milk          : false,
            milkChocolate : false,
            caffeine_TR   : "Yüksek",
            caffeine_EN   : "High",
            temperature   : "hot",
            image         : cupImage("hot"),
            published     : false,
            type          : "coffee",
            price         : "0,00",
        },
        // {
        //     ButtonNumber  : 14,
        //     CupSizes      : [{ CupSize: "Regular", PLU: 24, SKU1: "24", SKU2: "" }],
        //     Name_TR       : "Sütlü Çikolata",
        //     Name_EN       : "Milk Chocolate",
        //     description_TR: "Buharda ısıtılmış süt ve zengin çikolata şurubuyla hazırlanan tatlı ve kremsi bir içecek.",
        //     description_EN: "A sweet and creamy drink made with steamed milk and rich chocolate syrup.",
        //     RecipeNumber  : 95,
        //     milk          : true,
        //     milkChocolate : true,
        //     caffeine_TR   : "Düşük",
        //     caffeine_EN   : "Low",
        //     temperature   : "hot",
        //     image         : cupImage("hot"),
        //     published     : false,
        //     type          : "coffee",
        //     price         : "0,00",
        // },
        {
            ButtonNumber  : 1,
            Name_TR       : "Iced Americano",
            Name_EN       : "Iced Americano",
            description_TR: "Buz üzerine demlenen espresso ve soğuk suyla hazırlanan ferahlatıcı bir kahve.",
            description_EN: "Espresso poured over ice and topped with cold water for a refreshing finish.",
            RecipeNumber  : 1,
            milk          : false,
            caffeine_TR   : "Orta",
            caffeine_EN   : "Medium",
            temperature   : "iced",
            ice_water     : true,     // espresso soğuk suyla tamamlanır
            image         : cupImage("iced"),
            published     : true,
            type          : "coffee",
            price         : "0,00",
        },
        {
            ButtonNumber  : 7,
            Name_TR       : "Iced Latte",
            Name_EN       : "Iced Latte",
            description_TR: "Soğuk süt ve buz üzerine eklenen espresso ile hazırlanan yumuşak içimli kahve.",
            description_EN: "Espresso over cold milk and ice, smooth and lightly sweet.",
            RecipeNumber  : 7,
            milk          : true,
            caffeine_TR   : "Orta",
            caffeine_EN   : "Medium",
            temperature   : "iced",
            ice_water     : false,    // sütle tamamlanır, su alınmaz
            image         : cupImage("iced"),
            published     : true,
            type          : "coffee",
            price         : "0,00",
        },
    ],

    iceCreams: [
        {
            Name_TR       : "Vanilyalı Dondurma",
            Name_EN       : "Vanilla Ice Cream",
            description_TR: "Süt, krema, şeker ve vanilya özüyle yapılan klasik ve kremsi bir dondurma.",
            description_EN: "A classic and creamy vanilla-flavored ice cream made with milk, cream, sugar, and vanilla extract.",
            milk          : true,
            image         : ice_cream_cup,
            published     : true,
            type          : "ice_cream",
            price         : "0,00",
        },
        {
            Name_TR       : "Çikolatalı Dondurma",
            Name_EN       : "Chocolate Ice Cream",
            description_TR: "Süt, krema, şeker ve çikolatayla yapırlanan zengin bir dondurma.",
            description_EN: "A rich and indulgent chocolate-flavored ice cream made with milk, cream, sugar, and chocolate.",
            milk          : true,
            image         : ice_cream_cup,
            published     : true,
            type          : "ice_cream",
            price         : "0,00",
        },
        {
            Name_TR       : "Vanilyalı Çikolatalı Dondurma",
            Name_EN       : "Vanilla Chocolate Ice Cream",
            description_TR: "Farklı tatların tek bir kasede bir araya geldiği lezzetli bir dondurma.",
            description_EN: "A delightful blend of different flavors in a single scoop of ice cream.",
            milk          : true,
            image         : ice_cream_cup,
            published     : true,
            type          : "ice_cream",
            price         : "0,00",
        },
    ],
};

// ─────────────────────────────────────────────
// SOSLAR (Sauces)
// ─────────────────────────────────────────────
export const souces = [
    {
        id           : "sprinkles",
        name_TR      : "Renkli Süsler",
        name_EN      : "Sprinkles",
        description_TR: "Dondurmana eğlenceli ve şenlikli bir dokunuş katan renkli ve tatlı süsler.",
        description_EN: "Colorful and sweet toppings that add a fun and festive touch to your ice cream.",
        image        : springles,
        published    : true,
        price        : "0,00",
    },
    {
        id           : "almonds",
        name_TR      : "Badem Kırıkları",
        name_EN      : "Crushed Almonds",
        description_TR: "Dondurmana hoş bir doku ve lezzet katan çıtır badem parçaları.",
        description_EN: "Crunchy and nutty almond pieces that provide a delightful texture and flavor to your ice cream.",
        image        : badem_kiriklari,
        published    : true,
        price        : "0,00",
    },
    {
        id           : "hazelnuts",
        name_TR      : "Fındık Kırıkları",
        name_EN      : "Crushed Hazelnuts",
        description_TR: "Dondurmana hoş bir doku ve lezzet katan çıtır fındık parçaları.",
        description_EN: "Crunchy and nutty walnut pieces that provide a delightful texture and flavor to your ice cream.",
        image        : findik_kiriklari,
        published    : true,
        price        : "0,00",
    },
];

// ─────────────────────────────────────────────
// ŞURUPLAR (Syrups)
//
// ⚠️  `channel` FİZİKSEL POMPA NUMARASIDIR (LogoSurup kanalı 1–8).
// Müşteri burada şurubu seçer, backend o kanaldan akıtır — yanlış
// numara yanlış şurubun akmasına yol açar. İki kayıt asla aynı
// kanalı paylaşmamalıdır.
//
// Kaç mL akacağı burada YAZILMAZ: her kanalın kendi dose_ml değeri
// vardır ve /stock sayfasından düzenlenir.
//
// Kanal ↔ şurup eşlemesi backend'de de tanımlıdır
// (service/syrup_recipes.py → channel_config). İkisi aynı olmalı.
// ─────────────────────────────────────────────
export const syrups = [
    {
        id           : "vanilla",
        channel      : 4,
        name_TR      : "Vanilya",
        name_EN      : "Vanilla",
        description_TR: "İçeceğine klasik bir lezzet katan tatlı ve kremsi vanilya şurubu.",
        description_EN: "A sweet and creamy vanilla syrup that adds a classic flavor to your drink.",
        image        : vanilla_syrup,
        published    : true,
        price        : "0,00",
    },
    {
        id           : "caramel",
        channel      : 5,
        name_TR      : "Karamel",
        name_EN      : "Caramel",
        description_TR: "İçeceğine zengin bir lezzet katan tatlı ve tereyağlı karamel şurubu.",
        description_EN: "A sweet and buttery caramel syrup that adds a deliciously rich flavor to your drink.",
        image        : caramel_syrup,
        published    : true,
        price        : "0,00",
    },
    {
        id           : "chocolate",
        channel      : 3,
        name_TR      : "Çikolata",
        name_EN      : "Chocolate",
        description_TR: "İçeceğine lüks bir lezzet katan zengin çikolata şurubu.",
        description_EN: "A rich and indulgent chocolate syrup that adds a decadent flavor to your drink.",
        image        : chocolate_syrup,
        published    : true,
        price        : "0,00",
    },
    {
        id           : "white_chocolate",
        channel      : 2,
        name_TR      : "Beyaz Çikolata",
        name_EN      : "White Chocolate",
        description_TR: "İçeceğine zengin bir lezzet katan tatlı ve kremsi beyaz çikolata şurubu.",
        description_EN: "A sweet and creamy white chocolate syrup that adds a rich flavor to your drink.",
        image        : white_chocolate_syrup,
        published    : true,
        price        : "0,00",
    },
    // {
    //     id           : "hazelnut",
    //     channel      : 5,
    //     name_TR      : "Fındık",
    //     name_EN      : "Hazelnut",
    //     description_TR: "İçeceğine zengin bir lezzet katan tatlı ve kremsi fındık şurubu.",
    //     description_EN: "A sweet and creamy hazelnut syrup that adds a rich flavor to your drink.",
    //     image        : hazelnut_syrup,
    //     published    : true,
    //     price        : "0,00",
    // },
    {
        id           : "strawberry",
        channel      : 1,
        name_TR      : "Çilek",
        name_EN      : "Strawberry",
        description_TR: "İçeceğine zengin bir lezzet katan tatlı ve kremsi çilek şurubu.",
        description_EN: "A sweet and creamy strawberry syrup that adds a rich flavor to your drink.",
        image        : strawberry_syrup,
        published    : true,
        price        : "0,00",
    },
];

// ─────────────────────────────────────────────
// İLAVE (şurup / sos) ARAMA
//
// DÜZELTİLEN HATA:
//   Bu kayıtlarda name_TR ve name_EN vardı ama `name` YOKTU.
//   Arayüz option.name okuduğu için değer undefined geliyordu ve
//   iki ayrı hataya yol açıyordu:
//
//     1. selected.includes(undefined) her seçenek için true döndüğü
//        için tek şurup seçilince HEPSİ seçili görünüyordu.
//     2. Sepette extras.find(e => e.name === undefined) dizinin ilk
//        elemanıyla eşleşiyor, yani seçilen şurup yerine hep
//        "Renkli Süsler" yazıyordu.
//
//   Her kayda dile bağlı olmayan kalıcı bir `id` eklendi; arayüz
//   artık isim yerine bunu taşıyor.
// ─────────────────────────────────────────────

/** Tüm ilaveler tek listede — sepet ve detay ekranı buradan arar */
export const allExtras = [...souces, ...syrups];

/** Şurup ilavesinin backend kanal numarası (yoksa null — sos gibi) */
export const extraChannel = (id) => findExtra(id)?.channel ?? null;

/** id → kayıt. Bulunamazsa null. */
export const findExtra = (id) => allExtras.find((e) => e.id === id) ?? null;

/** İlavenin görünen adı */
export const extraName = (id, lang = "TR") => {
    const item = findExtra(id);
    return item ? (item[`name_${lang}`] ?? item.name_TR) : String(id ?? "");
};
