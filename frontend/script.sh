#!/usr/bin/env bash
set -euo pipefail

# ==== AYARLAR ====
DOCKER_USER="koraykoksall"          # Docker Hub kullanıcı adın
REPO_NAME="logorob_barista_robot_ui"        # Docker Hub repo adı
CONTEXT_DIR="./"           # Docker build context (Dockerfile burada olmalı)

IMAGE="${DOCKER_USER}/${REPO_NAME}"

# VERSION: ENV ile verilebilir. Verilmezse package.json'dan okunur.
if [[ -z "${VERSION:-}" ]]; then
  if command -v node >/dev/null 2>&1; then
    VERSION="$(node -p "require('${CONTEXT_DIR}/package.json').version")"
  else
    echo "ERROR: VERSION verilmedi ve node bulunamadı. Örn: VERSION=1.0.0 ./push_frontend.sh"
    exit 1
  fi
fi

echo "Frontend image: ${IMAGE}"
echo "Frontend version: ${VERSION}"

# ==== BUILD ====
docker build -t "${IMAGE}:${VERSION}" "${CONTEXT_DIR}"
docker tag "${IMAGE}:${VERSION}" "${IMAGE}:latest"

# ==== PUSH ====
docker push "${IMAGE}:${VERSION}"
docker push "${IMAGE}:latest"

echo "✅ Frontend push tamam: ${IMAGE}:${VERSION} ve :latest"


# ==== CLEANUP (LOCAL) ====
echo "🧹 Local image cleanup..."

# Bu scriptin oluşturduğu tag'leri sil
docker rmi "${IMAGE}:${VERSION}" "${IMAGE}:latest" 2>/dev/null || true

# Dangling (etiketsiz) image'ları temizle
docker image prune -f

echo "✅ Cleanup tamam."

