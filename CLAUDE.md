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

## REGRA ABSOLUTA — USO DE AGENTES

**Você NUNCA age sozinho. Toda e qualquer tarefa, sem exceção, deve ser executada pelos agentes especializados em `.claude/agents/`.**

Isso inclui tarefas pequenas, correções simples, ajustes de texto, mudanças de cor — qualquer coisa. Não existe tarefa pequena demais para usar agente.

Se você se pegar prestes a editar um arquivo sem ter acionado nenhum agente, pare. Acione o agente correto primeiro.

O usuário NÃO vai chamar os agentes — você decide sozinho quais acionar com base no que foi pedido. Essa decisão é sua responsabilidade em cada tarefa.

---

## Os 12 agentes e quando acionar cada um

**`tributario`** — acione quando envolver:
- regime tributário, impostos, alíquotas, obrigações fiscais
- emissão de NFS-e, DAS, DARF, SPED
- tributação de SaaS, assinatura recorrente, afiliação, publicidade
- pagamentos internacionais — Stripe, Railway, APIs externas
- planejamento tributário — pró-labore vs distribuição de lucros
- qualquer decisão de negócio com impacto em imposto
- sempre trabalha junto com `financeiro` e `juridico`

**`financeiro`** — acione quando envolver:
- modelo de negócio, precificação, planos e tiers
- implementação de pagamento, gateway, assinatura recorrente
- onde e como monetizar o portal B2C ou o SaaS B2B
- decisão de onde colocar paywall ou o que é free vs pago
- contratos comerciais, reajuste, multa, política de reembolso
- qualquer decisão técnica com impacto direto em receita
- sempre trabalha junto com `produto`, `juridico` e `security`

**`produto`** — acione SEMPRE que envolver qualquer coisa visual ou de fluxo:
- validação de jornada do usuário, consistência visual, gaps de UX
- OBRIGATÓRIO antes do `uiux` agir e depois que o `uiux` entregar
- fluxo obrigatório: produto (briefing) → uiux (executa) → produto (valida) → qa (testa)

**`uiux`** — acione quando envolver:
- templates HTML, formulários visíveis ao usuário
- fluxo de navegação, mensagens de erro/sucesso
- responsividade, acessibilidade, performance frontend
- cache, Cloudflare e Core Web Vitals no frontend
- SEMPRE após briefing do `produto` e SEMPRE devolvendo para validação do `produto`

**`security`** — acione quando envolver:
- autenticação, login, logout, sessão, token, JWT
- permissões, grupos, controle de acesso e isolamento por tenant
- formulários que recebem dados do usuário
- upload de arquivos, endpoints públicos
- configuração de `settings.py`, dados pessoais, deploy
- webhook de pagamento — validação de assinatura obrigatória

**`arquitetura`** — acione quando envolver:
- criação ou alteração de models Django
- views, queries, migrations, APIs, serializers
- performance ou lentidão reportada
- refatoração de qualquer módulo
- qualquer mudança em `settings.py`

**`qa`** — acione quando:
- qualquer feature nova for implementada
- um bug for corrigido
- um model ou view for alterado
- o agente `produto` aprovar o trabalho do `uiux`
- fluxo de pagamento ou assinatura for alterado

**`validador`** — acione SEMPRE como ÚLTIMO passo quando:
- mais de um agente foi acionado
- uma feature for considerada pronta
- antes de qualquer deploy para o Railway
- sem aprovação do validador, nenhum deploy acontece

**`juridico`** — acione quando envolver:
- termos de uso, política de privacidade, cookies
- coleta de dados de usuários (email, CPF, CNPJ)
- aceite digital de contrato — grava IP, user-agent, timestamp, hash
- contratos com agências (SaaS B2B)
- consentimento, opt-in, unsubscribe
- onboarding de novas agências na plataforma

**`seo`** — acione quando envolver:
- criação ou alteração de templates públicos
- novas páginas do portal ou landing pages do SaaS
- performance de carregamento relatada
- meta tags, sitemap, robots.txt, slugs e URLs públicas
- dados estruturados (JSON-LD, Schema.org)
- configuração de Cloudflare para cache e performance

**`prompts`** — acione quando envolver:
- qualquer integração com IA (Claude, OpenAI, etc)
- geração de texto automático (notícias, roteiros, descrições)
- extração de dados de documentos via IA
- assistente ou chatbot dentro da plataforma
- refinamento de prompt existente que está gerando output ruim

**`editor`** — acione quando envolver:
- reescrita de notícia a partir de link ou texto
- criação de conteúdo editorial para o portal B2C
- geração de prompt de imagem para notícia
- adaptação de conteúdo por canal (email, push, post)

---

## Fluxos obrigatórios por tipo de tarefa

### Qualquer tarefa visual ou de UX
```
produto → uiux → produto → qa → validador
```

### Feature nova completa
```
financeiro (se houver impacto em receita) →
produto → arquitetura + security + uiux (paralelo) →
produto (valida uiux) → qa → validador
```

### Bug visual
```
produto → uiux → produto → qa
```

### Bug de backend
```
arquitetura → qa → validador
```

### Implementação de pagamento
```
tributario + financeiro → arquitetura + security + juridico (paralelo) →
produto → uiux → produto → qa → validador
```

### Conteúdo editorial
```
editor → seo → validador
```

### Página legal (termos, privacidade)
```
juridico → seo + produto → uiux → produto → validador
```

### Deploy para produção
```
todos os 12 agentes → validador
```

---

## Mapeamento automático por pedido

| O usuário pede | Agentes acionados |
|---|---|
| "cria sistema de login" | security + arquitetura + produto → uiux → produto + qa → validador |
| "implementa pagamento recorrente" | tributario + financeiro + arquitetura + security + juridico + produto → uiux → produto + qa → validador |
| "ajusta CSS do header" | produto → uiux → produto → qa |
| "gera notícia a partir de link" | editor + seo |
| "cria landing page do SaaS" | financeiro + produto → uiux → produto + seo + juridico → validador |
| "política de privacidade" | juridico + seo + produto → uiux → produto → validador |
| "a home está lenta" | seo + arquitetura + uiux + qa |
| "onboarding de nova agência" | tributario + financeiro + juridico + security + arquitetura + produto → uiux → produto + qa → validador |
| "prompt gerando lixo" | prompts |
| "como monetizar o portal" | financeiro + tributario |
| "quanto vou pagar de imposto" | tributario |
| "revisa tudo / deixa pronto para prod" | todos os 12 → validador |

---

## Sobre acesso à internet
Os agentes trabalham com o código do projeto. Eles não acessam a internet sozinhos — se precisar de informação externa (lei atualizada, dado de SEO, concorrente), o usuário cola no chat e os agentes usam como contexto.

---

## Variáveis de ambiente esperadas

```
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=
DATABASE_URL=postgresql://...
```

## Comandos do projeto

```bash
python manage.py migrate
python manage.py migrate --check
python manage.py collectstatic --no-input
pytest --cov=. --cov-report=term-missing
python manage.py shell
```