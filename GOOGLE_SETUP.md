# Google Cloud + Railway — Setup do Login Google e YouTube Data API

Este documento explica **passo-a-passo** como:

1. Criar um projeto no Google Cloud Console
2. Habilitar a **YouTube Data API v3** (para puxar vídeos)
3. Criar credencial **OAuth 2.0 Client ID** (para login com Gmail)
4. Criar uma **API Key** (para YouTube)
5. Configurar as variáveis no **Railway**

Tempo estimado: ~15 minutos.

---

## 1. Criar projeto no Google Cloud Console

1. Acesse https://console.cloud.google.com
2. Topo da página, clique no seletor de projeto (ao lado do logo "Google Cloud")
3. Clique em **"Novo projeto"**
4. Nome sugerido: `NCfly` — deixe a organização como está
5. Clique em **Criar**
6. Aguarde alguns segundos e **selecione o novo projeto** no seletor

---

## 2. Habilitar a YouTube Data API v3

1. Menu lateral → **APIs e serviços** → **Biblioteca**
2. Na busca digite: `YouTube Data API v3`
3. Clique no card e depois em **Ativar**
4. Aguarde a confirmação (botão vira "Gerenciar")

---

## 3. Criar a API Key do YouTube

Essa é a chave que o backend usa para listar vídeos (não é login, é server-to-server).

1. Menu lateral → **APIs e serviços** → **Credenciais**
2. Topo: **+ Criar credenciais** → **Chave de API**
3. Uma chave será gerada — **copie e guarde** (ex.: `AIzaSy...`)
4. Clique em **Editar chave de API** para restringir:
   - **Restrições de aplicativo**: `Nenhum` (ou por IP do Railway se quiser travar)
   - **Restrições de API**: marcar **Restringir chave** → selecionar apenas `YouTube Data API v3`
5. **Salvar**

> Essa chave vai virar a env var `YOUTUBE_API_KEY` no Railway.

---

## 4. Configurar a tela de consentimento OAuth

Antes de criar o Client ID do login com Gmail, é preciso configurar a tela de consentimento.

1. Menu lateral → **APIs e serviços** → **Tela de permissão OAuth**
2. Tipo de usuário: **Externo** → **Criar**
3. Preencha:
   - **Nome do aplicativo**: `NCfly`
   - **E-mail de suporte**: seu Gmail (`pdrnacari@gmail.com`)
   - **Logo**: opcional
   - **Domínio do aplicativo**:
     - Página inicial: `https://ncfly.com.br`
     - Política de privacidade: `https://ncfly.com.br/privacidade/`
     - Termos de uso: `https://ncfly.com.br/termos/`
   - **Domínios autorizados**: `ncfly.com.br`
   - **E-mail do desenvolvedor**: seu Gmail
4. **Salvar e continuar**
5. **Escopos**: adicione apenas `openid`, `email`, `profile` → **Salvar e continuar**
6. **Usuários de teste**: enquanto o app estiver em modo teste, adicione os Gmails que poderão logar (inclua o seu). Depois você publica o app.
7. **Resumo** → **Voltar para o painel**
8. Se quiser liberar para qualquer Gmail sem modo teste: **Publicar aplicativo** (Google pode pedir verificação, mas para `openid email profile` geralmente libera na hora).

---

## 5. Criar o OAuth 2.0 Client ID (login com Gmail)

1. Menu lateral → **APIs e serviços** → **Credenciais**
2. **+ Criar credenciais** → **ID do cliente OAuth**
3. Tipo de aplicativo: **Aplicativo da Web**
4. Nome: `NCfly Web`
5. **Origens JavaScript autorizadas**:
   ```
   https://ncfly.com.br
   https://www.ncfly.com.br
   ```
6. **URIs de redirecionamento autorizados** — adicione exatamente assim (com `/home/`):
   ```
   https://ncfly.com.br/home/auth/google/callback/
   https://www.ncfly.com.br/home/auth/google/callback/
   ```
   > Apenas o **portal B2C** usa login com Google. O superadmin continua com login por e-mail/senha.
7. **Criar**
8. Um popup mostra o **Client ID** e **Client Secret** — **copie os dois** e guarde.

---

## 6. Configurar variáveis no Railway

No painel do Railway → **Variables** → adicionar:

| Variável | Valor |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | Client ID da seção 5 (termina em `.apps.googleusercontent.com`) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Client Secret da seção 5 |
| `PORTAL_GOOGLE_OAUTH_REDIRECT_URI` | `https://ncfly.com.br/auth/google/callback/` |
| `YOUTUBE_API_KEY` | API Key da seção 3 |

Depois de salvar, o Railway vai **redeploy** automático.

> **Nota**: `PORTAL_GOOGLE_OAUTH_REDIRECT_URI` é opcional — se você não setar, o código usa `request.build_absolute_uri`. Só defina se o domínio variar (ex.: atrás de proxy).

---

## 7. Testar

### Login com Gmail (portal B2C)
1. Entrar em `https://ncfly.com.br/auth/login/` OU clicar em qualquer CTA que exige login (ex.: "Criar alerta")
2. Clicar em **Entrar com Google**
3. Autorizar no popup Google
4. **Após o login, retorna automaticamente para a página de onde veio** (ou pra home se veio direto da tela de login)

### YouTube
1. No superadmin (`/ncadm/`), editar um artigo/notícia
2. Usar a busca de vídeos do YouTube — deve retornar resultados reais (não mock)
3. Se retornar mock ou vazio: conferir log do Railway (`YOUTUBE_API_KEY nao configurada`)

---

## Problemas comuns

**"Erro 400: redirect_uri_mismatch"**
→ A URI de callback não bate com o que está no Google Cloud Console. Conferir se tem barra no final e se é `https://` (não `http://`).

**"Access blocked: This app is in test mode"**
→ O app está em modo teste e o Gmail não está na lista de usuários de teste. Adicionar em **Tela de permissão OAuth → Usuários de teste** OU publicar o app.

**"YOUTUBE_API_KEY nao configurada, retornando mock"**
→ Env var não foi salva no Railway ou o deploy ainda não rodou com a nova config. Conferir aba **Variables** e forçar redeploy.

**"Quota exceeded"** no YouTube
→ Cota diária grátis é de 10.000 unidades/dia. Uma busca `search.list` custa 100. Reduzir nº de buscas ou pedir aumento no Google Cloud Console.

---

## Onde isso está no código

- Login portal B2C: [portal/auth.py:239](portal/auth.py#L239) (`google_oauth_configured`), [portal/views_auth.py:393](portal/views_auth.py#L393) (`portal_google_login`)
- Login superadmin (allauth): [core/settings.py:531](core/settings.py#L531)
- YouTube Data API: [portal/services/youtube_service.py:21](portal/services/youtube_service.py#L21)
