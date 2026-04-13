#!/usr/bin/env bash
# VNA Backup Script
# Backs up PostgreSQL database and BIDS data directory

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${VNA_BACKUP_DIR:-./backups}/${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

echo "=== VNA Backup ${TIMESTAMP} ==="

# PostgreSQL backup
if command -v docker &>/dev/null && docker compose ps postgres &>/dev/null 2>&1; then
    echo "[1/3] Backing up PostgreSQL..."
    docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-vna}" "${POSTGRES_DB:-vna}" > "${BACKUP_DIR}/database.sql"
    gzip "${BACKUP_DIR}/database.sql"
    echo "  → ${BACKUP_DIR}/database.sql.gz"
else
    echo "[1/3] PostgreSQL not running via Docker, skipping DB backup"
fi

# BIDS data backup
BIDS_DATA="${VNA_BIDS_DATA:-./bids_data}"
if [ -d "${BIDS_DATA}" ] && [ "$(ls -A "${BIDS_DATA}" 2>/dev/null)" ]; then
    echo "[2/3] Backing up BIDS data..."
    tar czf "${BACKUP_DIR}/bids_data.tar.gz" -C "$(dirname "${BIDS_DATA}")" "$(basename "${BIDS_DATA}")"
    echo "  → ${BACKUP_DIR}/bids_data.tar.gz"
else
    echo "[2/3] No BIDS data to backup"
fi

# Configuration backup
echo "[3/3] Backing up configuration..."
cp .env "${BACKUP_DIR}/.env" 2>/dev/null || echo "  → .env not found, skipping"
chmod 600 "${BACKUP_DIR}/.env" 2>/dev/null
cp docker-compose.yml "${BACKUP_DIR}/docker-compose.yml" 2>/dev/null || echo "  → docker-compose.yml not found, skipping"

# Cleanup old backups (keep last 7)
echo ""
echo "Backup complete: ${BACKUP_DIR}"
find ./backups -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
echo "Old backups (>7 days) cleaned up."
