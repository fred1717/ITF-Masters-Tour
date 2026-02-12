#!/usr/bin/env bash
# run_local.sh — Launch Flask locally against Docker PostgreSQL
# Run from project root: ./run_local.sh

set -e

# Load .env if present (optional, defaults are in db_connection.py)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "Loaded .env"
fi

# Ensure Flask finds templates and static files from project root
export FLASK_APP=app.py
export FLASK_ENV=development

echo "Starting Flask on http://127.0.0.1:5000"
python3 app.py
