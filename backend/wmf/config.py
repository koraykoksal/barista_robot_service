"""
config.py

Tüm yapılandırma sabitleri tek yerden yönetilir.
IP, port, token gibi değerleri değiştirmek için
sadece bu dosyaya bakmak yeterlidir.
"""

# ─────────────────────────────────────────────
# ROBOT
# ─────────────────────────────────────────────
# ROBOT_IP = "192.168.1.201"   # robot2_pitcher — /order_standart akışı
ROBOT_IP = "127.0.0.1"   # simulator için localhost

# ─────────────────────────────────────────────
# İÇECEK TİPİ SINIFLANDIRMASI
# ─────────────────────────────────────────────
# /order_art — iki robot + bölünmüş akış (espresso + süt ayrı)
# Sütlü, çikolatalı, köpüklü içecekler
ORDER_ART_BUTTON_NUMBERS: set = {
    1,   # Soğuk süt
    3,   # Sütlü kahve
    4,   # Süt
    6,   # Süt köpüğü
    7,   # Iced sütlü kahve
    12,  # Cappuccino
    13,  # Latte Macchiato
    14,  # Sütlü Choc
    15,  # Chociatto
    16,  # Iced Cappuccino
    17,  # Iced Latte Macchiato
    18,  # Süt köpüğü soğuk
}

# /order_standart — tek robot akışı
# Sadece espresso/americano/sıcak su gibi
ORDER_STANDART_BUTTON_NUMBERS: set = {
    2,   # Café Crème
    5,   # Ristretto
    11,  # Espresso Macchiato
    56,  # SteamJet
    58,  # Sıcak su
}

# İçecek adları (loglama için)
DRINK_NAMES: dict = {
    1:  "Soğuk süt",
    2:  "Café Crème",
    3:  "Sütlü kahve",
    4:  "Süt",
    5:  "Ristretto",
    6:  "Süt köpüğü",
    7:  "Iced sütlü kahve",
    11: "Espresso Macchiato",
    12: "Cappuccino",
    13: "Latte Macchiato",
    14: "Sütlü Choc",
    15: "Chociatto",
    16: "Iced Cappuccino",
    17: "Iced Latte Macchiato",
    18: "Süt köpüğü soğuk",
    56: "SteamJet",
    58: "Sıcak su",
}

# /order_art — Espresso kısmı için button number
# Sütlü içeceklerde önce espresso, sonra süt recipe'si çekilir
# Aşağıdaki map: orijinal btn → (espresso_btn, sut_btn)
# None ise o adım yok demek (sadece süt veya sadece espresso)
ART_RECIPE_MAP: dict = {
    1:  (None, 4),    # Soğuk süt   → sadece süt (btn 4)
    3:  (5,    4),    # Sütlü kahve → espresso(btn 5) + süt(btn 4)
    4:  (None, 4),    # Süt         → sadece süt (btn 4)
    6:  (None, 6),    # Süt köpüğü  → sadece köpük (btn 6)
    7:  (5,    4),    # Iced sütlü  → espresso(btn 5) + soğuk süt(btn 1)
    12: (5,    12),   # Cappuccino  → espresso(btn 5) + cappuccino süt(btn 12)
    13: (5,    13),   # Latte Macc  → espresso(btn 5) + latte süt(btn 13)
    14: (None, 14),   # Sütlü Choc  → sadece çikolata (btn 14)
    15: (15,   None), # Chociatto   → choc bazlı, tek adım
    16: (5,    16),   # Iced Capp   → espresso(btn 5) + iced capp süt(btn 16)
    17: (5,    17),   # Iced Latte  → espresso(btn 5) + iced latte(btn 17)
    18: (None, 18),   # Süt köpüğü soğuk → soğuk köpük(btn 18)
}

# ─────────────────────────────────────────────
# KAHVE MAKİNESİ
# ─────────────────────────────────────────────
COFFEE_MACHINE_IP    = "192.168.1.111"
COFFEE_MACHINE_PORT  = 25000
COFFEE_MACHINE_TOKEN = "0123456789abcdef0123456789abcdef"

# ─────────────────────────────────────────────
# TIMER — button numarasına göre bekleme süresi (saniye)
# 0 → hemen devam et
# ─────────────────────────────────────────────
BREW_TIMERS: dict = {
    # Espresso tipi (20s)
    1:  23,   # Espresso
    5:  20,   # Ristretto
    # Americano tipi (30s)
    2:  38,   # Americano (Café Crème)
    # Sütlü içecekler (40s)
    3:  40,   # Latte
    12: 28,   # Cappuccino
    14: 41,   # Milk Chocolate
}

# ─────────────────────────────────────────────
# SİPARİŞ AKIŞI
# ─────────────────────────────────────────────
COFFEE_OVERALL_TIMEOUT  = 120.0   # coffee_task toplam max süre (s)
COFFEE_RECV_TIMEOUT     = 20.0    # tek ws.recv() max süre (s)
COFFEE_SILENT_ROUNDS    = 6       # max sessiz tur sayısı
DI_WAIT_TIMEOUT         = 60.0    # DI1/DI3 bekleme timeout (s)

# ─────────────────────────────────────────────
# İÇECEK ADLARI (log için)
# ─────────────────────────────────────────────
BEVERAGE_NAMES: dict = {
    1:  "Espresso",
    2:  "Americano / Café Crème",
    3:  "Latte",
    4:  "Café Americano",
    5:  "Ristretto",
    6:  "2× Espresso",
    7:  "2× Café Crème",
    8:  "2× Café Americano",
    12: "Cappuccino",
    14: "Milk Chocolate",
    47: "Hot Water Large",
    48: "Hot Water",
}

BARISTA_LABELS = {"0": "Hafif (%85)", "1": "Normal (%100)", "2": "Güçlü (%115)"}
SML_LABELS     = {"0": "Small", "1": "Medium", "2": "Large"}
DECAF_LABELS   = {"0": "Normal", "1": "Decaf"}
MILK_LABELS    = {"-1": "Tarife göre (default)", "0": "Normal süt", "1": "Yağsız süt"}
SIRUP_LABELS   = {"-1": "Tarife göre (default)", "0": "Şurrupsuz",
                  "1": "Şurup 1", "2": "Şurup 2", "3": "Şurup 3", "4": "Şurup 4"}

# ─────────────────────────────────────────────
# MAKİNE HATA KODLARI
# ─────────────────────────────────────────────
MACHINE_ERROR_MESSAGES: dict = {
    68:  "Çekirdek kahve bölmesi boş veya kapağı açık",
    69:  "Çekirdek kahve bölmesi boş veya kapağı açık (2. öğütücü)",
    70:  "Çekirdek kahve bölmesi boş veya kapağı açık (3. öğütücü)",
    71:  "Çekirdek kahve bölmesi boş veya kapağı açık (4. öğütücü)",
    74:  "Panel açık",
    75:  "Posa çekmecesi dolu veya yerinde değil",
    76:  "Posa çekmecesi dolu veya yerinde değil",
    80:  "Su deposu boş veya yerinde değil",
    82:  "Süt konteyneri boş veya yerinde değil",
    83:  "Süt konteyneri boş veya yerinde değil (2. konteyner)",
    90:  "Temizlik gerekli",
    92:  "Acil temizlik gerekli",
    136: "Makine ısınıyor",
}


# ─────────────────────────────────────────────
# SYRUP DİSPENSER (LogoSurup)
# ─────────────────────────────────────────────
SYRUP_HOST    = "192.168.1.155"   # LogoSurup cihaz IP
SYRUP_PORT    = 5000              # TCP port (sabit)
SYRUP_TIMEOUT = 15.0              # Toplam işlem timeout (s)
SYRUP_CHANNELS = 8                # Kanal sayısı

# ─────────────────────────────────────────────
# ROBOT MOD YÖNETİMİ
# ─────────────────────────────────────────────
ROBOT_MODE_SWITCH_TIMEOUT = 10.0   # oto moda geçiş için max bekleme (s)
ROBOT_MODE_POLL_INTERVAL  = 0.3    # mod geçiş bekleme polling aralığı (s)
ROBOT_STATUS_POLL_INTERVAL = 2.0   # arka planda robot durum izleme (s)


