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

RUN python manage.py collectstatic --no-input || true

EXPOSE 8000

CMD gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --log-file -
