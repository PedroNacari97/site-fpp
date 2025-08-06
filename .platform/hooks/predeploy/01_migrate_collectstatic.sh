#!/bin/bash
set -e

# Ativa o virtualenv do EB e roda migrações + estáticos
source /var/app/venv/*/bin/activate

python manage.py migrate --noinput
python manage.py collectstatic --noinput
