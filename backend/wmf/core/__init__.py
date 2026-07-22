"""
core/ — taban katman

Bu paketteki hiçbir modül service/ veya route/ paketlerine bağımlı
DEĞİLDİR. Bağımlılık yönü tek yönlüdür:

    route  →  service  →  core

Bu kural dairesel importları kökten engeller. Yeni bir modül eklerken
"core içinden bir servisi çağırmam gerekiyor" diye düşünüyorsanız, o
modül aslında core'a ait değildir — service/ altına koyun.

İçerik:
  config.py         → .env'den okunan tüm ayarlar
  catalog.py        → içecek kataloğu (buton/reçete numaraları, malzemeler)
  database.py       → MongoDB bağlantısı ve koleksiyon erişimleri
  security.py       → yönetici token doğrulaması
  version.py        → sürüm numarası
  logging.py        → tutarlı konsol loglama
  machine_errors.py → makine hata kodları ve durum yorumlama
  ws_utils.py       → WebSocket payload ayrıştırıcıları (eski helper.py)
"""
