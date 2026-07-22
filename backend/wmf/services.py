"""
services.py

Uygulama genelinde kullanılan singleton servis nesneleri.
Tüm modüller buradan import eder — tekrar instantiation olmaz.
"""

from robot_manager       import RobotManager
from coffee_service      import CoffeeService
from machine_monitor     import MachineMonitor
from machine_info_service import MachineInfoService
from syrup_service       import SyrupService
from config              import (
    ROBOT_IP,
    COFFEE_MACHINE_IP,
    COFFEE_MACHINE_PORT,
    COFFEE_MACHINE_TOKEN,
    SYRUP_HOST,
    SYRUP_PORT,
    SYRUP_TIMEOUT,
)

# ─────────────────────────────────────────────
# ROBOT
# ─────────────────────────────────────────────
robot_mgr = RobotManager(ROBOT_IP)

# ─────────────────────────────────────────────
# KAHVE MAKİNESİ
# ─────────────────────────────────────────────
coffee = CoffeeService()

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
