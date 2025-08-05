#!/bin/bash
set -e
cd /var/app/current
python manage.py collectstatic --noinput
