# Dockerfile NCfly
#
# Scrapers de monitoramento usam curl_cffi (sem navegador), entao usamos uma
# imagem Python slim em vez da imagem oficial do Playwright. Isso reduz o
# tamanho da imagem em ~1.5GB e elimina o overhead do Chromium em runtime.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# curl_cffi precisa do libcurl + libnss para impersonar o TLS do Chrome.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcurl4 \
        libnss3 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

# collectstatic precisa de SECRET_KEY mesmo que dummy — envs do Railway so
# existem em runtime, nao em build. A chave real vem do ambiente na execucao.
RUN DJANGO_SECRET_KEY=build-dummy-key-not-used-at-runtime \
    DJANGO_DEBUG=0 \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["sh", "-c", "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 300 --graceful-timeout 30 --log-file -"]
