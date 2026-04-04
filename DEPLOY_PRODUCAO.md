# Deploy em producao

## Recomendacao pratica

### Melhor custo x simplicidade para este projeto
- `Railway` para a aplicacao Django
- `MySQL` no proprio Railway
- `Volume` no Railway para a pasta `media`

Motivo:
- o projeto ja suporta MySQL nativamente
- o deploy pode sair direto da branch `main`
- fica mais simples do que separar app em um lugar e banco em outro

### Opcao para teste barato
- `Render` para a aplicacao
- `Render Postgres` ou outro banco compativel via `DATABASE_URL`

Observacao:
- para teste serve bem
- para producao de verdade, os planos gratuitos costumam ter limites, expiracao de banco ou hibernacao

## Como funciona em producao

O site nao consome dados do Git.

Em producao fica assim:
- `GitHub/main` -> dispara deploy
- `aplicacao Django` -> roda no servidor
- `banco` -> fica em servico separado e persistente
- `media` -> fica em bucket S3/R2/B2 ou volume persistente

## Variaveis principais

Configure no ambiente de producao:

```env
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=sua-chave-forte
DJANGO_ALLOWED_HOSTS=ncfly.com.br,www.ncfly.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://ncfly.com.br,https://www.ncfly.com.br
SITE_BASE_URL=https://ncfly.com.br
SITE_ENVIRONMENT=production
DATABASE_URL=sua-url-do-banco
```

Tambem configure o que voce ja usa no projeto:

```env
GOOGLE_ANALYTICS_MEASUREMENT_ID=
GOOGLE_SEARCH_CONSOLE_VERIFICATION=
PORTAL_CONTACT_EMAIL=contato@ncfly.com.br
PORTAL_DPO_EMAIL=contato@ncfly.com.br
DJANGO_DEFAULT_FROM_EMAIL=contato@ncfly.com.br
TELEGRAM_ALERTS_BOT_TOKEN=
TELEGRAM_ALERTS_WEBHOOK_SECRET=
TELEGRAM_ALERTS_ALLOWED_CHAT_IDS=
OPENAI_API_KEY=
```

## Separacao entre local e producao

Para o painel do superadmin mostrar apenas os acessos e leads do ambiente certo:

- local: `SITE_ENVIRONMENT=local`
- producao: `SITE_ENVIRONMENT=production`

As metricas first-party e os leads passam a ser gravados com ambiente e host. Assim, quando voce abrir o painel em producao, ele considera apenas os dados de producao por padrao.

## Static e media

### Static
- ja esta pronto com `WhiteNoise`
- o build roda `collectstatic`

### Media
O projeto usa uploads e arquivos gerados:
- logos de empresa
- imagens geradas
- outros arquivos em `media/`

Entao em producao voce deve usar uma destas opcoes:
- bucket S3/R2/B2
- volume persistente

Se usar volume no Railway:
- monte um volume
- aponte `DJANGO_MEDIA_ROOT` para o caminho montado

Exemplo:

```env
DJANGO_MEDIA_ROOT=/data/media
DJANGO_MEDIA_URL=/media/
```

## Railway

### App
- conecte o repositorio GitHub
- selecione a branch `main`
- deixe auto deploy ligado
- start command:

```bash
gunicorn core.wsgi:application --log-file -
```

### Banco
- crie um MySQL no Railway
- pegue a `DATABASE_URL`

### Deploy
- configure `build.sh` como build command, se quiser explicito
- build command:

```bash
bash build.sh
```

- rode migracoes como comando pos-deploy:

```bash
python manage.py migrate --noinput
```

## Render

### App
- conecte o repositorio GitHub
- branch `main`
- auto deploy ligado
- build command:

```bash
bash build.sh
```

- start command:

```bash
gunicorn core.wsgi:application --log-file -
```

### Banco
- use um Postgres compativel em `DATABASE_URL`
- este projeto ja aceita `DATABASE_URL`

### Migracoes
Configure como pre-deploy command ou rode manualmente:

```bash
python manage.py migrate --noinput
```

## Dominio

Depois do primeiro deploy:
- adicione o dominio no painel do provedor
- configure DNS
- atualize `DJANGO_ALLOWED_HOSTS`
- atualize `DJANGO_CSRF_TRUSTED_ORIGINS`
- confirme `SITE_BASE_URL`

### Cloudflare
- se o dominio `ncfly.com.br` ja estiver no Cloudflare, use o Cloudflare apenas como DNS/proxy da aplicacao em producao
- nao precisa usar `cloudflared tunnel` para a producao final
- tunnel faz sentido para teste local, webhook temporario e validacao antes do deploy oficial
- para producao estavel, a aplicacao deve ficar hospedada no provedor e o Cloudflare fica na frente do dominio

## Checklist final

- `DEBUG` desligado
- `SECRET_KEY` forte
- banco fora do SQLite
- `main` com auto deploy
- `collectstatic` no build
- migracoes no deploy
- `media` persistente
- HTTPS ativo
- dominio configurado
