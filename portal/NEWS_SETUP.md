# Setup do Portal de Noticias

## 1. Criar o arquivo `.env`

Copie o arquivo `.env.example` para `.env` na raiz do projeto.

Exemplo:

```env
DJANGO_DEBUG=True
OPENAI_API_KEY=cole-sua-chave-aqui
OPENAI_NEWS_MODEL=gpt-4.1-mini
OPENAI_NEWS_IMAGE_MODEL=gpt-image-1
PORTAL_NEWS_CONFIDENCE_THRESHOLD=0.70
PORTAL_GENERATE_AI_IMAGES=0
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
- Se `PORTAL_GENERATE_AI_IMAGES=1`, o sistema tenta gerar capa ilustrativa quando a noticia nao tiver imagem.
- As fontes analisadas ficam na tabela `portal_fonte`.
- O parametro `--limit` controla quantos artigos por fonte entram no processamento daquela execucao. Ele nao afeta a abertura da home; a home so le noticias ja salvas no banco.
- O projeto agora usa `Melhores Cartoes` como fonte principal por padrao. `Passageiro de Primeira` fica salvo no sistema, mas inativo ate voce decidir reativar.
- Se quiser rodar explicitamente so com a fonte principal:

```powershell
py manage.py sync_home_news --source "Melhores Cartoes" --limit 20
```
