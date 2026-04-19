# NCfly — Claude Code


## COMO SE COMUNICAR

Seja direto como um homem das cavernas. Sem rodeios, sem passar passo a passo do Ã³bvio, sem explicar o que vai fazer antes de fazer.

ERRADO:
"Vou analisar o problema, identificar a causa raiz, e entÃ£o aplicar a correÃ§Ã£o necessÃ¡ria..."

CERTO:
"Corrigido. Card de cotaÃ§Ã£o alinhado com emissÃµes. CÃ¡lculo de chegada estava faltando chamada no template â€” adicionado."

Regras de comunicaÃ§Ã£o:
- Fez â†’ diz o que fez, onde, pronto
- Encontrou problema â†’ descreve o problema e a soluÃ§Ã£o, sem drama
- Precisa de decisÃ£o â†’ pergunta direto, uma linha
- Sem introduÃ§Ãµes, sem conclusÃµes, sem "espero que isso ajude"
- RelatÃ³rio final: lista do que foi feito, lista do que ficou pendente, acabou

## Stack
- **Backend:** Django (Python)
- **Banco:** PostgreSQL (prod via Railway)
- **Deploy:** Railway

## Produtos
- **Portal B2C** â€” notÃ­cias e alertas de passagens aÃ©reas (pÃºblico)
- **SaaS B2B** â€” plataforma de gestÃ£o para agÃªncias de viagens

## Regras universais
- Nunca editar migrations jÃ¡ aplicadas em prod â€” sempre criar novas
- Nunca hardcodar secrets â€” sempre `os.environ` ou `django-environ`
- `DEBUG=False` em produÃ§Ã£o, sempre
- Usar `select_related` / `prefetch_related` para evitar N+1
- Toda view nova precisa de permissÃ£o explÃ­cita
- Todo cÃ³digo novo precisa de teste correspondente

---

## REGRA ABSOLUTA â€” USO DE AGENTES

**VocÃª NUNCA age sozinho. Toda e qualquer tarefa, sem exceÃ§Ã£o, deve ser executada pelos agentes especializados em `.claude/agents/`.**

Isso inclui tarefas pequenas, correÃ§Ãµes simples, ajustes de texto, mudanÃ§as de cor â€” qualquer coisa. NÃ£o existe tarefa pequena demais para usar agente.

Se vocÃª se pegar prestes a editar um arquivo sem ter acionado nenhum agente, pare. Acione o agente correto primeiro.

O usuÃ¡rio NÃƒO vai chamar os agentes â€” vocÃª decide sozinho quais acionar com base no que foi pedido. Essa decisÃ£o Ã© sua responsabilidade em cada tarefa.

---

## Os 12 agentes e quando acionar cada um

**`tributario`** â€” acione quando envolver:
- regime tributÃ¡rio, impostos, alÃ­quotas, obrigaÃ§Ãµes fiscais
- emissÃ£o de NFS-e, DAS, DARF, SPED
- tributaÃ§Ã£o de SaaS, assinatura recorrente, afiliaÃ§Ã£o, publicidade
- pagamentos internacionais â€” Stripe, Railway, APIs externas
- planejamento tributÃ¡rio â€” prÃ³-labore vs distribuiÃ§Ã£o de lucros
- qualquer decisÃ£o de negÃ³cio com impacto em imposto
- sempre trabalha junto com `financeiro` e `juridico`

**`financeiro`** â€” acione quando envolver:
- modelo de negÃ³cio, precificaÃ§Ã£o, planos e tiers
- implementaÃ§Ã£o de pagamento, gateway, assinatura recorrente
- onde e como monetizar o portal B2C ou o SaaS B2B
- decisÃ£o de onde colocar paywall ou o que Ã© free vs pago
- contratos comerciais, reajuste, multa, polÃ­tica de reembolso
- qualquer decisÃ£o tÃ©cnica com impacto direto em receita
- sempre trabalha junto com `produto`, `juridico` e `security`

**`produto`** â€” acione SEMPRE que envolver qualquer coisa visual ou de fluxo:
- validaÃ§Ã£o de jornada do usuÃ¡rio, consistÃªncia visual, gaps de UX
- OBRIGATÃ“RIO antes do `uiux` agir e depois que o `uiux` entregar
- fluxo obrigatÃ³rio: produto (briefing) â†’ uiux (executa) â†’ produto (valida) â†’ qa (testa)

**`uiux`** â€” acione quando envolver:
- templates HTML, formulÃ¡rios visÃ­veis ao usuÃ¡rio
- fluxo de navegaÃ§Ã£o, mensagens de erro/sucesso
- responsividade, acessibilidade, performance frontend
- cache, Cloudflare e Core Web Vitals no frontend
- SEMPRE apÃ³s briefing do `produto` e SEMPRE devolvendo para validaÃ§Ã£o do `produto`

**`security`** â€” acione quando envolver:
- autenticaÃ§Ã£o, login, logout, sessÃ£o, token, JWT
- permissÃµes, grupos, controle de acesso e isolamento por tenant
- formulÃ¡rios que recebem dados do usuÃ¡rio
- upload de arquivos, endpoints pÃºblicos
- configuraÃ§Ã£o de `settings.py`, dados pessoais, deploy
- webhook de pagamento â€” validaÃ§Ã£o de assinatura obrigatÃ³ria

**`arquitetura`** â€” acione quando envolver:
- criaÃ§Ã£o ou alteraÃ§Ã£o de models Django
- views, queries, migrations, APIs, serializers
- performance ou lentidÃ£o reportada
- refatoraÃ§Ã£o de qualquer mÃ³dulo
- qualquer mudanÃ§a em `settings.py`

**`qa`** â€” acione quando:
- qualquer feature nova for implementada
- um bug for corrigido
- um model ou view for alterado
- o agente `produto` aprovar o trabalho do `uiux`
- fluxo de pagamento ou assinatura for alterado

**`validador`** â€” acione SEMPRE como ÃšLTIMO passo quando:
- mais de um agente foi acionado
- uma feature for considerada pronta
- antes de qualquer deploy para o Railway
- sem aprovaÃ§Ã£o do validador, nenhum deploy acontece

**`juridico`** â€” acione quando envolver:
- termos de uso, polÃ­tica de privacidade, cookies
- coleta de dados de usuÃ¡rios (email, CPF, CNPJ)
- aceite digital de contrato â€” grava IP, user-agent, timestamp, hash
- contratos com agÃªncias (SaaS B2B)
- consentimento, opt-in, unsubscribe
- onboarding de novas agÃªncias na plataforma

**`seo`** â€” acione quando envolver:
- criaÃ§Ã£o ou alteraÃ§Ã£o de templates pÃºblicos
- novas pÃ¡ginas do portal ou landing pages do SaaS
- performance de carregamento relatada
- meta tags, sitemap, robots.txt, slugs e URLs pÃºblicas
- dados estruturados (JSON-LD, Schema.org)
- configuraÃ§Ã£o de Cloudflare para cache e performance

**`prompts`** â€” acione quando envolver:
- qualquer integraÃ§Ã£o com IA (Claude, OpenAI, etc)
- geraÃ§Ã£o de texto automÃ¡tico (notÃ­cias, roteiros, descriÃ§Ãµes)
- extraÃ§Ã£o de dados de documentos via IA
- assistente ou chatbot dentro da plataforma
- refinamento de prompt existente que estÃ¡ gerando output ruim

**`editor`** â€” acione quando envolver:
- reescrita de notÃ­cia a partir de link ou texto
- criaÃ§Ã£o de conteÃºdo editorial para o portal B2C
- geraÃ§Ã£o de prompt de imagem para notÃ­cia
- adaptaÃ§Ã£o de conteÃºdo por canal (email, push, post)

---

## Fluxos obrigatÃ³rios por tipo de tarefa

### Qualquer tarefa visual ou de UX
```
produto â†’ uiux â†’ produto â†’ qa â†’ validador
```

### Feature nova completa
```
financeiro (se houver impacto em receita) â†’
produto â†’ arquitetura + security + uiux (paralelo) â†’
produto (valida uiux) â†’ qa â†’ validador
```

### Bug visual
```
produto â†’ uiux â†’ produto â†’ qa
```

### Bug de backend
```
arquitetura â†’ qa â†’ validador
```

### ImplementaÃ§Ã£o de pagamento
```
tributario + financeiro â†’ arquitetura + security + juridico (paralelo) â†’
produto â†’ uiux â†’ produto â†’ qa â†’ validador
```

### ConteÃºdo editorial
```
editor â†’ seo â†’ validador
```

### PÃ¡gina legal (termos, privacidade)
```
juridico â†’ seo + produto â†’ uiux â†’ produto â†’ validador
```

### Deploy para produÃ§Ã£o
```
todos os 12 agentes â†’ validador
```

---

## Mapeamento automÃ¡tico por pedido

| O usuÃ¡rio pede | Agentes acionados |
|---|---|
| "cria sistema de login" | security + arquitetura + produto â†’ uiux â†’ produto + qa â†’ validador |
| "implementa pagamento recorrente" | tributario + financeiro + arquitetura + security + juridico + produto â†’ uiux â†’ produto + qa â†’ validador |
| "ajusta CSS do header" | produto â†’ uiux â†’ produto â†’ qa |
| "gera notÃ­cia a partir de link" | editor + seo |
| "cria landing page do SaaS" | financeiro + produto â†’ uiux â†’ produto + seo + juridico â†’ validador |
| "polÃ­tica de privacidade" | juridico + seo + produto â†’ uiux â†’ produto â†’ validador |
| "a home estÃ¡ lenta" | seo + arquitetura + uiux + qa |
| "onboarding de nova agÃªncia" | tributario + financeiro + juridico + security + arquitetura + produto â†’ uiux â†’ produto + qa â†’ validador |
| "prompt gerando lixo" | prompts |
| "como monetizar o portal" | financeiro + tributario |
| "quanto vou pagar de imposto" | tributario |
| "revisa tudo / deixa pronto para prod" | todos os 12 â†’ validador |

---

## Sobre acesso Ã  internet
Os agentes trabalham com o cÃ³digo do projeto. Eles nÃ£o acessam a internet sozinhos â€” se precisar de informaÃ§Ã£o externa (lei atualizada, dado de SEO, concorrente), o usuÃ¡rio cola no chat e os agentes usam como contexto.

---

## VariÃ¡veis de ambiente esperadas

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
