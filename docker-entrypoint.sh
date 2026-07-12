#!/bin/sh
set -e

echo "Waiting for database..."
python manage.py wait_for_db --timeout 60

python manage.py migrate --noinput
python manage.py create_dev_token || true

exec "$@"
