#!/bin/bash
set -e
source /var/app/venv/*/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput
