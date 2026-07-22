FROM python:3.12-slim

WORKDIR /app

# (opsiyonel ama iyi) loglar anında gelsin
ENV PYTHONUNBUFFERED=1

# COPY requirements.txt .
# COPY . .
# RUN python -m pip install --no-cache-dir fastapi "uvicorn[standard]"

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY . .

EXPOSE 8000

# ÖNEMLİ: host 0.0.0.0 olmalı yoksa dışarıdan erişemezsin
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
