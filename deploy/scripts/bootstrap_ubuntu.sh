#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-literature}"
APP_DIR="${APP_DIR:-/opt/literature-screening-app}"
DATA_DIR="${DATA_DIR:-/opt/literature-screening-data}"
ENV_DIR="${ENV_DIR:-/etc/literature-screening}"
REPO_URL="${REPO_URL:-https://github.com/shisheng329/ai-assisted-review-system.git}"
DOMAIN="${DOMAIN:-_}"
SWAP_SIZE_GB="${SWAP_SIZE_GB:-4}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/scripts/bootstrap_ubuntu.sh"
  exit 1
fi

echo "Installing OS packages..."
apt update
apt install -y git nginx python3 python3-venv python3-pip curl

if ! swapon --show | grep -q "/swapfile"; then
  echo "Creating ${SWAP_SIZE_GB}GB swapfile..."
  fallocate -l "${SWAP_SIZE_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q "^/swapfile " /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi
fi

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${APP_DIR}" "${DATA_DIR}/uploads" "${DATA_DIR}/exports" "${ENV_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" "${DATA_DIR}"

if [[ -d "${APP_DIR}/.git" ]]; then
  echo "Updating existing repository..."
  git -c safe.directory="${APP_DIR}" -C "${APP_DIR}" pull --ff-only
else
  echo "Cloning repository..."
  rm -rf "${APP_DIR:?}/"*
  git clone "${REPO_URL}" "${APP_DIR}"
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "Creating Python virtual environment..."
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${ENV_DIR}/literature-screening.env" ]]; then
  cp "${APP_DIR}/deploy/literature-screening.env.example" "${ENV_DIR}/literature-screening.env"
  chmod 600 "${ENV_DIR}/literature-screening.env"
fi

cp "${APP_DIR}/deploy/systemd/literature-screening.service" /etc/systemd/system/literature-screening.service
systemctl daemon-reload
systemctl enable --now literature-screening

cp "${APP_DIR}/deploy/nginx/literature-screening.conf" /etc/nginx/sites-available/literature-screening.conf
sed -i "s/server_name your-domain.com;/server_name ${DOMAIN};/" /etc/nginx/sites-available/literature-screening.conf
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/literature-screening.conf /etc/nginx/sites-enabled/literature-screening.conf
nginx -t
systemctl reload nginx

echo "Deployment finished."
echo "Local app health: curl http://127.0.0.1:8502"
echo "Public HTTP: http://${DOMAIN}"
