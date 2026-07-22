# ══════════════════════════════════════════════════════════════
# WMF Coffee Service — backend imajı
#
# DEĞİŞENLER (v2):
#   • requirements.txt UTF-8 oldu ve motor/pymongo/dnspython eklendi;
#     önceki imaj hiç kurulamıyordu
#   • --no-cache-dir eklendi (imaj boyutu)
#   • root olmayan kullanıcı ile çalışıyor
#   • HEALTHCHECK eklendi
#   • Bağımlılık katmanı koddan ayrıldı — kod değişince pip yeniden
#     çalışmıyor, build hızlanıyor
# ══════════════════════════════════════════════════════════════

FROM python:3.12-slim

# Loglar anında aksın, .pyc üretilmesin
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ── Bağımlılıklar (ayrı katman — önbelleğe alınır) ────────────
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
 && python -m pip install --no-cache-dir -r requirements.txt

# ── Uygulama kodu ────────────────────────────────────────────
COPY . .

# ── Root olmayan kullanıcı ───────────────────────────────────
# Konteyner içinde root çalıştırmak gereksiz bir risk.
RUN useradd --create-home --uid 10001 appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# ── Sağlık kontrolü ──────────────────────────────────────────
# Kök endpoint 200 dönmüyorsa konteyner "unhealthy" işaretlenir.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status==200 else sys.exit(1)"

# host 0.0.0.0 olmalı, yoksa konteyner dışından erişilemez
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
