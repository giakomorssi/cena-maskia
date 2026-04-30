#!/bin/bash
set -e

echo "Starting CENA MASKIA CHAMPIONSHIP API..."

# Parse DB host/port from DATABASE_URL, fallback to "db:5432" (Docker Compose default)
DB_HOST=$(echo "${DATABASE_URL:-}" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_HOST="${DB_HOST:-db}"
DB_PORT=$(echo "${DATABASE_URL:-}" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U postgres 2>/dev/null; do
    echo "Database is unavailable - sleeping"
    sleep 2
done
echo "Database is ready!"

echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed!"

echo "Setup complete! Starting application..."
exec "$@"
