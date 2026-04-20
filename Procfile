web: sh -c "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 180 --graceful-timeout 30 --log-file -"
release: python manage.py migrate --noinput
