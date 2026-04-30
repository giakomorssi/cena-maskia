#!/bin/bash
set -e

echo "Starting CENA MASKIA CHAMPIONSHIP API..."

# Parse DB host/port from DATABASE_URL, fallback to "db:5432" (Docker Compose default)
DB_HOST=$(echo "${DATABASE_URL:-}" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_HOST="${DB_HOST:-db}"
DB_PORT=$(echo "${DATABASE_URL:-}" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
WAIT_RETRIES=15
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U postgres 2>/dev/null; do
    WAIT_RETRIES=$((WAIT_RETRIES - 1))
    if [ "$WAIT_RETRIES" -le 0 ]; then
        echo "Database not ready after timeout - continuing anyway"
        break
    fi
    echo "Database is unavailable - sleeping (${WAIT_RETRIES} retries left)"
    sleep 2
done
if [ "$WAIT_RETRIES" -gt 0 ]; then
    echo "Database is ready!"
fi

echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed!"

echo "Setup complete! Starting application..."
exec "$@"
