web: sh -c "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --log-file -"
release: python manage.py migrate --noinput
