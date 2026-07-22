#!/usr/bin/env bash
set -euo pipefail

# ==== AYARLAR ====
DOCKER_USER="koraykoksall"
REPO_NAME="logorob_barista_robot_service"
CONTEXT_DIR="./"                      # Dockerfile burada
VERSION_FILE="${CONTEXT_DIR}/__version__.py"

IMAGE="${DOCKER_USER}/${REPO_NAME}"

# VERSION: ENV > __version__.py > git > 0.0.0
if [[ -z "${VERSION:-}" ]]; then
  if [[ -f "${VERSION_FILE}" ]]; then
    # __version__ = "1.0.0" satırından 1.0.0 çek
    VERSION="$(
      sed -nE 's/^[[:space:]]*__version__[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "${VERSION_FILE}" \
      | head -n 1
    )"
  fi

  if [[ -z "${VERSION:-}" ]]; then
    VERSION="$(git describe --tags --always 2>/dev/null || true)"
  fi

  if [[ -z "${VERSION:-}" ]]; then
    VERSION="0.0.0"
  fi
fi

echo "Backend image: ${IMAGE}"
echo "Backend version: ${VERSION}"

# ==== BUILD ====
docker build -t "${IMAGE}:${VERSION}" "${CONTEXT_DIR}"
docker tag "${IMAGE}:${VERSION}" "${IMAGE}:latest"

# ==== PUSH ====
docker push "${IMAGE}:${VERSION}"
docker push "${IMAGE}:latest"

echo "✅ Backend push tamam: ${IMAGE}:${VERSION} ve :latest"


# ==== CLEANUP (LOCAL) ====
echo "🧹 Local image cleanup..."

# Bu scriptin oluşturduğu tag'leri sil
docker rmi "${IMAGE}:${VERSION}" "${IMAGE}:latest" 2>/dev/null || true

# Dangling (etiketsiz) image'ları temizle (build cache'den kalanlar)
docker image prune -f

echo "✅ Cleanup tamam."

