@'
# NCfly — Claude Code

## Stack
- **Backend:** Django (Python)
- **Banco:** PostgreSQL (prod via Railway)
- **Deploy:** Railway

## Produtos
- **Portal B2C** — notícias e alertas de passagens aéreas (público)
- **SaaS B2B** — plataforma de gestão para agências de viagens

## Regras universais
- Nunca editar migrations já aplicadas em prod — sempre criar novas
- Nunca hardcodar secrets — sempre `os.environ` ou `django-environ`
- `DEBUG=False` em produção, sempre
- Usar `select_related` / `prefetch_related` para evitar N+1
- Toda view nova precisa de permissão explícita
- Todo código novo precisa de teste correspondente

---

## Agentes e quando acionar cada um

Você tem 8 subagentes em `.claude/agents/`. Acione automaticamente — o usuário NÃO chama agente por agente, você decide sozinho com base no que foi pedido.

### Regras de acionamento automático

**`security`** — acione quando envolver:
- autenticação, login, logout, sessão, token, JWT
- permissões, grupos, controle de acesso
- formulários que recebem dados do usuário
- upload de arquivos, endpoints públicos
- configuração de `settings.py`, dados pessoais, deploy

**`arquitetura`** — acione quando envolver:
- criação ou alteração de models Django
- views, queries, migrations, APIs, serializers
- performance ou lentidão reportada
- qualquer mudança em `settings.py`

**`uiux`** — acione quando envolver:
- templates HTML, formulários visíveis ao usuário
- fluxo de navegação, mensagens de erro/sucesso
- responsividade, acessibilidade
- qualquer coisa que o usuário final vê
- melhora da jornada do usuario
- ideias de melhorias sem perder identidade visual
- testar fluxos e ver se estão todos certo

**`qa`** — acione quando:
- qualquer feature nova for implementada
- um bug for corrigido
- um model ou view for alterado

**`validador`** — acione SEMPRE como ÚLTIMO passo quando:
- mais de um agente foi acionado
- uma feature for considerada pronta
- antes de qualquer deploy para o Railway

**`juridico`** — acione quando envolver:
- termos de uso, política de privacidade, cookies
- coleta de dados de usuários (email, CPF, CNPJ)
- contratos com agências (SaaS B2B)
- consentimento, opt-in, unsubscribe
- onboarding de novas agências na plataforma

**`seo`** — acione quando envolver:
- criação ou alteração de templates públicos
- novas páginas do portal de notícias ou landing pages do SaaS
- performance de carregamento relatada
- meta tags, sitemap, robots.txt, slugs e URLs públicas

**`prompts`** — acione quando envolver:
- qualquer integração com IA (Claude, OpenAI, etc)
- geração de texto automático (notícias, roteiros, descrições)
- extração de dados de documentos via IA
- assistente ou chatbot dentro da plataforma
- refinamento de prompt existente que está gerando output ruim

### Mapeamento automático por pedido

| O usuário pede | Agentes acionados |
|---|---|
| "cria sistema de login" | security + arquitetura + uiux + qa → validador |
| "gera notícia automática a partir do alerta" | prompts + arquitetura + qa |
| "cria roteiro de viagem com IA para a agência" | prompts + arquitetura + security + qa → validador |
| "cria landing page do SaaS" | seo + uiux + juridico |
| "política de privacidade do portal" | juridico + seo + uiux |
| "a home está carregando lenta" | seo + arquitetura |
| "onboarding de nova agência" | juridico + security + arquitetura + qa → validador |
| "o prompt de roteiro está gerando lixo" | prompts |
| "adiciona formulário de opt-in de alertas" | juridico + security + uiux + qa → validador |
| "deixa pronto para produção" | todos os 8 |

### Quando acionar todos os 8
- "revisa tudo", "faz o deploy", "deixa pronto para produção"
- Lançamento de nova seção do portal ou do SaaS
- Feature nova completa e crítica do zero

---

## Sobre acesso à internet pelos agentes
Os agentes trabalham com o código do projeto — eles podem acessar a internet sozinhos. Se precisar de informação externa (legislação atualizada, dados de concorrente, métricas de SEO), o usuário cola no chat e os agentes usam como contexto.

---

## Variáveis de ambiente esperadas