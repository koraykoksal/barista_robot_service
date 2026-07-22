"""
service/ — iş mantığı ve cihaz istemcileri

core/ paketine bağımlıdır, route/ paketine bağımlı DEĞİLDİR.

    route  →  service  →  core

İçerik:
  registry.py             → singleton servis nesneleri (eski services.py)
  robot_manager.py        → Fairino robot bağlantısı, DO/DI, mod yönetimi
  connect_robot.py        → robot bağlantı kurucu
  coffee_service.py       → WMF kahve makinesi WebSocket istemcisi
  machine_monitor.py      → makine hata/temizlik durumu izleyici (push abonelikleri)
  machine_info_service.py → makine bilgi/diagnostik sorguları
  syrup_service.py        → LogoSurup TCP istemcisi
  syrup_recipes.py        → şurup kanal yapılandırması ve içecek tarifleri
  stock_service.py        → stok okuma/düşme/yenileme
  order_service.py        → sipariş akışının tamamı

NOT — registry.py neden ayrı:
  Servis nesneleri modül seviyesinde bir kez oluşturulur. Her modül
  kendi örneğini yaratsaydı robot birden fazla kez bağlanmaya çalışırdı.
  Tüm modüller registry'den import eder.
"""
