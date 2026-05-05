#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/opt/literature-screening-data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/literature-screening-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="${BACKUP_DIR}/literature-screening-data-${STAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

if [[ ! -d "${DATA_DIR}" ]]; then
  echo "Data directory does not exist: ${DATA_DIR}"
  exit 1
fi

tar -czf "${TARGET}" -C "$(dirname "${DATA_DIR}")" "$(basename "${DATA_DIR}")"
echo "Backup written to ${TARGET}"
