"""
route/ — HTTP katmanı

service/ ve core/ paketlerine bağımlıdır; ters yönde bağımlılık YOKTUR.

    route  →  service  →  core

Bu dosyalarda iş mantığı bulunmaz. Görevleri:
  • isteği doğrulamak (pydantic modelleri)
  • ilgili servisi çağırmak
  • sonucu HTTP yanıtına çevirmek
  • hataları uygun durum koduna eşlemek

Router'lar:
  order.py   → /order_standart, /order/status/{job_id}, /check_beverage
  machine.py → /machine/*, /robot/*
  stock.py   → /stock/*
  syrup.py   → /syrup/*

NOT: Router nesneleri burada TOPLANMAZ; app.py her modülü tek tek
include eder. Böylece bir router'ı geçici olarak devre dışı bırakmak
için tek satır yeterli olur.
"""
