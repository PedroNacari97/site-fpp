# Telegram Noticias

## Variaveis locais

No `.env.local`:

```env
TELEGRAM_NEWS_BOT_TOKEN=cole-o-token-do-bot
TELEGRAM_NEWS_WEBHOOK_SECRET=
TELEGRAM_NEWS_ALLOWED_CHAT_IDS=
```

Se `TELEGRAM_NEWS_ALLOWED_CHAT_IDS` ficar vazio, o bot aceita qualquer chat no ambiente local.

## Teste local com polling

```powershell
py manage.py remover_telegram_noticias_webhook
py manage.py poll_telegram_noticias --limit 20
```

## Produção

Se quiser operar com webhook:

```powershell
py manage.py configurar_telegram_noticias_webhook https://ncfly.com.br
```

Rota pública esperada:

```text
https://ncfly.com.br/integracoes/telegram/noticias/webhook/
```

Se preferir rodar com polling em produção, deixe um worker dedicado:

```powershell
py manage.py remover_telegram_noticias_webhook
py manage.py poll_telegram_noticias --limit 20 --timeout 30
```

## Formatos aceitos

- `atualizar 10`
- link puro
- `noticia https://...`
- texto promocional bruto

## Exemplos

```text
atualizar 8
```

```text
https://www.cartoesdecredito.me/cartoes/btg-tap-black-oferece-ate-2-anos-de-anuidade-gratis/
```

```text
TEM PROMOCODE NOVO NO AR...
```
