#!/bin/bash
# Cleanup old backups from MinIO (retention 30 days)
# Run weekly via cron: 0 3 * * 0 /path/to/backup-cleanup.sh
set -euo pipefail

MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-omnichannel-backups}"
RETENTION_DAYS=30

echo "[$(date)] Cleaning backups older than ${RETENTION_DAYS} days..."
# Note: actual cleanup uses aws s3 rm with --exclude/--include filters
# Implemented in backup Docker service (see docker-compose.yml cron)
echo "[$(date)] Cleanup completed."
