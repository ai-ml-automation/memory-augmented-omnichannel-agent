#!/bin/bash
# Backup script for PostgreSQL, Qdrant, Neo4j -> MinIO
# Run daily via cron: 0 2 * * * /path/to/backup.sh

set -euo pipefail

BACKUP_DIR="/tmp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
MINIO_BUCKET="omnichannel-backups"

mkdir -p $BACKUP_DIR
echo "[$(date)] Starting backup..."

echo "[$(date)] Backing up PostgreSQL..."
PGPASSWORD=${POSTGRES_PASSWORD:-changeme} pg_dump -h ${POSTGRES_HOST:-postgres} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-omnichannel} -Fc > $BACKUP_DIR/postgres_$DATE.dump

echo "[$(date)] Creating Qdrant snapshot..."
curl -s -X POST http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}/collections/omnichannel/snapshots > /dev/null
SNAPSHOT=$(curl -s http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}/collections/omnichannel/snapshots | python3 -c "import sys,json; print(json.load(sys.stdin)[chr(114)+chr(101)+chr(115)+chr(117)+chr(108)+chr(116)][0][chr(110)+chr(97)+chr(109)+chr(101)])")
curl -s -o $BACKUP_DIR/qdrant_$DATE.snapshot http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}/collections/omnichannel/snapshots/$SNAPSHOT

# IV.3: Neo4j backup via APOC JSON export
echo "[$(date)] Backing up Neo4j via APOC export..."
NEO4J_HOST=${NEO4J_HOST:-localhost}
NEO4J_PORT=${NEO4J_PORT:-7474}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}

EXPORT_QUERY='{"statements":[{"statement":"CALL apoc.export.json.all(\"/backups/neo4j_'$DATE'.json\", {useTypes:true})"}]}'

curl -s -u "$NEO4J_USER:$NEO4J_PASSWORD" \
     -H "Content-Type: application/json" \
     -X POST "http://$NEO4J_HOST:$NEO4J_PORT/db/neo4j/tx/commit" \
     -d "$EXPORT_QUERY" > /dev/null 2>&1 || \
  echo "[$(date)] WARNING: Neo4j APOC export failed (is APOC plugin installed?)"

# Copy backup from container to host (if running in Docker)
NEO4J_CONTAINER=${NEO4J_CONTAINER:-omnichannel-neo4j}
docker cp "$NEO4J_CONTAINER:/backups/neo4j_$DATE.json" "$BACKUP_DIR/neo4j_$DATE.json" 2>/dev/null || \
  echo "[$(date)] WARNING: Could not copy Neo4j backup (container may not be running)"

echo "[$(date)] Neo4j backup attempted: neo4j_$DATE.json"

echo "[$(date)] Backup completed."
