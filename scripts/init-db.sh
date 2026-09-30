#!/bin/bash
# ============================================
# Database Initialization Script
# ============================================
# This script initializes all required databases
# for local development environment.
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default values
POSTGRES_HOST=${POSTGRES_HOST:-localhost}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-omnichannel}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}

NEO4J_HOST=${NEO4J_HOST:-localhost}
NEO4J_PORT=${NEO4J_PORT:-7687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}

MINIO_ENDPOINT=${MINIO_ENDPOINT:-localhost:9000}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin}
MINIO_BUCKET=${MINIO_BUCKET:-omnichannel}

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW} Database Initialization${NC}"
echo -e "${YELLOW}========================================${NC}"

# ============================================
# Wait for PostgreSQL
# ============================================
echo -e "${GREEN}[1/4] Waiting for PostgreSQL...${NC}"
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres -c "SELECT 1;" > /dev/null 2>&1; do
    echo "PostgreSQL is not ready yet. Waiting..."
    sleep 2
done
echo -e "${GREEN}PostgreSQL is ready!${NC}"

# ============================================
# Create Database
# ============================================
echo -e "${GREEN}[2/4] Creating database '$POSTGRES_DB'...${NC}"
DB_EXISTS=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'")
if [ "$DB_EXISTS" != "1" ]; then
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d postgres -c "CREATE DATABASE $POSTGRES_DB;"
    echo -e "${GREEN}Database '$POSTGRES_DB' created.${NC}"
else
    echo -e "${GREEN}Database '$POSTGRES_DB' already exists.${NC}"
fi

# ============================================
# Initialize Neo4j
# ============================================
echo -e "${GREEN}[3/4] Initializing Neo4j indexes...${NC}"
until curl -s -u $NEO4J_USER:$NEO4J_PASSWORD http://$NEO4J_HOST:7474/ > /dev/null 2>&1; do
    echo "Neo4j is not ready yet. Waiting..."
    sleep 2
done

# Create constraints for User nodes
curl -s -u $NEO4J_USER:$NEO4J_PASSWORD \
    -H "Content-Type: application/json" \
    -d '{"statements": [{"statement": "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"}]}' \
    http://$NEO4J_HOST:7474/db/neo4j/tx/commit > /dev/null

# Create constraints for Fact nodes
curl -s -u $NEO4J_USER:$NEO4J_PASSWORD \
    -H "Content-Type: application/json" \
    -d '{"statements": [{"statement": "CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE"}]}' \
    http://$NEO4J_HOST:7474/db/neo4j/tx/commit > /dev/null

# Create indexes
curl -s -u $NEO4J_USER:$NEO4J_PASSWORD \
    -H "Content-Type: application/json" \
    -d '{"statements": [{"statement": "CREATE INDEX user_tenant IF NOT EXISTS FOR (u:User) ON (u.tenant_id)"}]}' \
    http://$NEO4J_HOST:7474/db/neo4j/tx/commit > /dev/null

echo -e "${GREEN}Neo4j indexes created.${NC}"

# ============================================
# Initialize MinIO Bucket
# ============================================
echo -e "${GREEN}[4/4] Creating MinIO bucket '$MINIO_BUCKET'...${NC}"
until curl -s http://$MINIO_ENDPOINT/minio/health/live > /dev/null 2>&1; do
    echo "MinIO is not ready yet. Waiting..."
    sleep 2
done

# Check if mc (MinIO Client) is installed
if command -v mc &> /dev/null; then
    mc alias set local http://$MINIO_ENDPOINT $MINIO_ACCESS_KEY $MINIO_SECRET_KEY 2>/dev/null
    mc mb --ignore-existing local/$MINIO_BUCKET 2>/dev/null
    echo -e "${GREEN}MinIO bucket '$MINIO_BUCKET' created.${NC}"
else
    echo -e "${YELLOW}MinIO Client (mc) not installed. Bucket creation skipped.${NC}"
    echo -e "${YELLOW}Please create bucket '$MINIO_BUCKET' manually via MinIO Console.${NC}"
fi

echo -e "${YELLOW}========================================${NC}"
echo -e "${GREEN}All databases initialized successfully!${NC}"
echo -e "${YELLOW}========================================${NC}"
