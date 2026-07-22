"""
routers/

FastAPI APIRouter grupları:
  order   → /order_standart, /order/status, /check_beverage, /connect-test, /send
  machine → /machine/status, /machine/info, /machine/diagnostic, /machine/service,
             /machine/cleaning, /read_do, /set_do
  stock   → /stock/status, /stock/refill, /stock/thresholds,
             /stock/logs/orders, /stock/logs/refills
"""

from routers import order, machine, stock

__all__ = ["order", "machine", "stock"]
