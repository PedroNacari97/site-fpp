# Telegram / Alertas de Passagens

## Variáveis de ambiente

Adicione no `.env`:

```env
TELEGRAM_ALERTS_BOT_TOKEN=cole-o-token-do-bot
TELEGRAM_ALERTS_WEBHOOK_SECRET=defina-um-segredo-forte
TELEGRAM_ALERTS_ALLOWED_CHAT_IDS=-1001234567890
```

`TELEGRAM_ALERTS_ALLOWED_CHAT_IDS` aceita uma lista separada por vírgula.

## Teste local por polling

Para buscar mensagens diretamente do bot sem publicar webhook:

```powershell
py manage.py remover_telegram_alertas_webhook
py manage.py poll_telegram_alertas --limit 20
```

Se quiser descartar mensagens pendentes ao desligar o webhook:

```powershell
py manage.py remover_telegram_alertas_webhook --drop-pending-updates
```

## Produção com webhook

1. Suba o projeto em URL pública
2. Configure o webhook:

```powershell
py manage.py configurar_telegram_alertas_webhook https://ncfly.com.br
```

O endpoint usado será:

```text
/integracoes/telegram/alertas/webhook/
```

## Regras atuais

- Só processa `message` e `channel_post`
- Ignora chats que não estejam em `TELEGRAM_ALERTS_ALLOWED_CHAT_IDS`
- Não duplica `update_id`
- Também evita cadastrar o mesmo texto bruto repetido no mesmo chat
- Usa o mesmo parser do `Autopreencher` da tela manual
- Aceita `atualizar 10` para rodar o sync em lote de notícias
