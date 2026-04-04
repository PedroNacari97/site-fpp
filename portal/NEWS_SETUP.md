# Setup do Portal de Noticias

## 1. Criar o arquivo `.env`

Copie o arquivo `.env.example` para `.env` na raiz do projeto.

Exemplo:

```env
DJANGO_DEBUG=True
OPENAI_API_KEY=cole-sua-chave-aqui
OPENAI_NEWS_MODEL=gpt-5.4
OPENAI_NEWS_IMAGE_MODEL=gpt-image-1.5
PORTAL_NEWS_CONFIDENCE_THRESHOLD=0.70
PORTAL_GENERATE_AI_IMAGES=0
PORTAL_FORCE_AI_IMAGES=0
PORTAL_USE_SOURCE_IMAGE_REFERENCE=1
```

## 2. Testar a chave da OpenAI

```powershell
py manage.py test_openai_news
```

## 3. Rodar a sincronizacao das noticias

```powershell
py manage.py sync_home_news --limit 20
```

## 4. Abrir a home publica

```text
http://127.0.0.1:8000/home/
```

## Observacoes

- Se `OPENAI_API_KEY` nao estiver configurada, o sistema cai para o modo fallback.
- Se `PORTAL_GENERATE_AI_IMAGES=1`, o sistema tenta gerar capa editorial nova com IA.
- Se `PORTAL_FORCE_AI_IMAGES=1`, o sistema passa a preferir uma capa propria mesmo quando a materia original tiver imagem.
- Se `PORTAL_USE_SOURCE_IMAGE_REFERENCE=1`, o sistema tenta usar a imagem da materia como referencia real para gerar uma nova variacao mais proxima do original, com alteracoes controladas.
- O prompt de imagem foi ajustado para manter a mesma ideia editorial do artigo e poder usar marcas, produtos e programas reais citados na noticia, mas com variacao visual suficiente para nao copiar a capa da fonte.
- As fontes analisadas ficam na tabela `portal_fonte`.
- O parametro `--limit` controla quantos artigos por fonte entram no processamento daquela execucao. Ele nao afeta a abertura da home; a home so le noticias ja salvas no banco.
- O projeto agora usa `Melhores Cartoes` como fonte principal por padrao. `Passageiro de Primeira` fica salvo no sistema, mas inativo ate voce decidir reativar.
- Se quiser rodar explicitamente so com a fonte principal:

```powershell
py manage.py sync_home_news --source "Melhores Cartoes" --limit 20
```
