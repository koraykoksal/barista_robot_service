"""
service/registry.py   (eski services.py)

Uygulama genelinde paylaşılan singleton servis nesneleri.

NEDEN TEK YERDE:
  Bu nesneler donanım bağlantısı tutar — robot soketi, makine
  WebSocket'i, syrup TCP oturumu. Her modül kendi örneğini yaratsaydı
  aynı cihaza birden fazla bağlantı açılır, robot "zaten bağlı"
  hatası verirdi. Tüm modüller buradan import eder.

  Dosya adı services.py idi; service/ klasörüyle karışıyordu.
  registry.py adı ne yaptığını daha iyi anlatıyor.

İMPORT SIRASI UYARISI:
  Bu modül import edildiği anda nesneler oluşur, ancak HİÇBİRİ
  bağlantı açmaz — bağlantılar app.py lifespan içinde başlatılır.
  Bu ayrım önemli: import zamanında ağ işlemi yapmak, testleri ve
  --reload modunu kırar.
"""

from core.config import (
    COFFEE_MACHINE_IP,
    COFFEE_MACHINE_PORT,
    COFFEE_MACHINE_TOKEN,
    ROBOT_IP,
    SYRUP_HOST,
    SYRUP_PORT,
    SYRUP_TIMEOUT,
)
from service.coffee_service import CoffeeService
from service.machine_info_service import MachineInfoService
from service.machine_monitor import MachineMonitor
from service.robot_manager import RobotManager
from service.syrup_service import SyrupService


# ─────────────────────────────────────────────
# ROBOT
# ─────────────────────────────────────────────
robot_mgr = RobotManager(ROBOT_IP)

# ─────────────────────────────────────────────
# KAHVE MAKİNESİ
# ─────────────────────────────────────────────
# Adres ve token .env'den gelir. Önceden CoffeeService() argümansız
# kuruluyor, sınıf da değerleri kendi içinde sabit tutuyordu — sipariş
# akışı .env'i görmüyordu.
coffee = CoffeeService(
    ip    = COFFEE_MACHINE_IP,
    port  = COFFEE_MACHINE_PORT,
    token = COFFEE_MACHINE_TOKEN,
)

monitor = MachineMonitor(
    ip    = COFFEE_MACHINE_IP,
    port  = COFFEE_MACHINE_PORT,
    token = COFFEE_MACHINE_TOKEN,
)

machine_info = MachineInfoService(
    ws_uri = f"ws://{COFFEE_MACHINE_IP}:{COFFEE_MACHINE_PORT}/",
    token  = COFFEE_MACHINE_TOKEN,
)

# ─────────────────────────────────────────────
# SYRUP DİSPENSER
# ─────────────────────────────────────────────
syrup = SyrupService(
    host    = SYRUP_HOST,
    port    = SYRUP_PORT,
    timeout = SYRUP_TIMEOUT,
)


__all__ = ["robot_mgr", "coffee", "monitor", "machine_info", "syrup"]
