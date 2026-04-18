# Source Summary — captured from repo before snipping

## Repo: PedroNacari97/site-fpp @ main (NOT codex — codex branch doesn't exist; using main)

Django monolith. Two surfaces + shared accounts:
- `gestao/` — ADMIN panel (operators/admins manage clients, flights, points programs, issuances, hotels). URL: `/admin_custom/...`
- `painel_cliente/` — CLIENT panel (end clients see their points balance, bookings). URL: `/painel/...`
- `accounts/` — shared login (CPF + password + role dropdown: Cliente / Operador / Administrador / Super Admin)

Brazilian Portuguese. Product is an airline miles / loyalty-points management SaaS for a travel agency called **NCfly** (or FPP — Fidelity Points Program?). Agency books flights using clients' accumulated miles across programs (Smiles, Latam Pass, TudoAzul, etc.).

## Key domain entities (from models/)
- Cliente (client), Empresa (company)
- ProgramaFidelidade (loyalty program, e.g. Smiles)
- ContaFidelidade (loyalty account — client's account in a program)
- ContaAdministrada (managed account — FPP's own pool accounts)
- Movimentacao (point movement: accrual, transfer, debit)
- CotacaoVoo (flight quotation), EmissaoPassagem (ticket issuance), EmissaoHotel (hotel)
- Escala (flight connection), Aeroporto, CompanhiaAerea (airline)
- ValorMilheiro (price per 1000 points — market reference value)
- Passageiro, AuditLog, AcessoClienteLog

## DESIGN TOKENS — from two competing CSS files

### Admin (gestao) — admin-theme.css (newer, "standardized shell")
```
--bg: #f4f6fb
--surface: #ffffff
--border: #e3e8ef
--muted: #5b6473
--heading: #0f172a
--primary: #2563eb  (blue-600)
--primary-strong: #1d4ed8
--accent: #0ea5e9   (sky-500)
--success: #16a34a
--warning: #d97706
--danger: #dc2626
--radius: 16px
--shadow: 0 14px 30px rgba(15, 23, 42, 0.08)

# "Shell" override block adds:
--shell-bg: #f7fafc
--shell-surface: #ffffff
--shell-border: #e2e8f0
--shell-muted: #718096
--shell-text: #1a202c
--shell-primary: #3182ce  (chakra-style blue-500)
--sidebar-width: 256px
```
Font: 'Open Sans' (Google Fonts)
Sidebar: white, 256px, nav-item with right-border accent on active (#3182ce / #ebf4ff bg)
Header: white surface, border-bottom, shadow sm
Buttons: .btn (solid primary #3182ce), .btn--outline, .btn--ghost, .btn--destructive, sizes sm/lg/icon
Cards: 12px radius (from cards.css) / 16px radius (from admin-theme)
Icons: inline SVG, 20x20, stroke currentColor, stroke-width 2, stroke-linecap round, stroke-linejoin round (LUCIDE-STYLE, hand-authored)
Pills: .pill, .pill-success (#ecfdf3/#166534/#bbf7d0 border), .pill-danger, .pill-neutral

### Client panel (painel_cliente) — base/variables.css
```
--color-bg: #f7fafc
--color-text: #1a202c
--color-heading: #1a365d   (deeper navy)
--color-primary: #3182ce
--color-primary-dark: #2c5282
--color-muted: #4a5568
--color-border: #e2e8f0
--color-success: #2f855a
--color-danger: #e53e3e
--color-surface: #ffffff
--color-input-bg: #edf2f7
--color-input-border: #cbd5e0

--shadow-card: 0 10px 10px rgba(0, 0, 0, 0.1)
--shadow-table: 0 10px 8px rgba(0, 0, 0, 0.1)
--shadow-login: 0 2px 32px rgba(0, 0, 0, 0.1)

--radius-lg: 18px; --radius-md: 12px; --radius-sm: 9px; --radius-xs: 8px
--space-xs: 6px; --space-sm: 12px; --space-md: 16px; --space-lg: 20px; --space-xl: 30px
```
Font: 'Open Sans'
Typography: h1 1.5rem/600, h2 1.25rem/600, .section-title 1.25rem/600, .label 0.875rem/#4a5568, .valor 1.4rem/700

### Login (accounts) — login.css (third variant — OLDER, more dramatic)
```
--bg: #f0f4f8    (with gradient to #e8f0f7)
--heading: #2c5aa0  (warmer blue)
--primary: #5a8cc4
--muted: #7a92a8
--border: #d4e4f0
Darker blue: #4a7ab8, #3a6aaa
Error: #c85a5a + #fce8e8 bg
Button: linear-gradient(135deg, #5a8cc4, #4a7ab8), UPPERCASE + letter-spacing
Card: 16px radius, shadow 0 8px 32px rgba(51, 102, 153, 0.08)
Has DARK MODE: bg #1a1a2e, surface #0f3460, etc.
```
Font: 'Segoe UI', Tahoma, Geneva, Verdana (system stack)
Animation: slideIn on login, shake on error

### Older painel.css (gestao sidebar-heavy) — legacy
Sidebar: 210px, linear-gradient(180deg, #2c5aa0 → #1e3f66), white text
has dark mode
Inputs 2px borders, UPPERCASE labels with letter-spacing

## DESIGN UNIFICATION
There are THREE stacked CSS "eras" in this repo:
1. **Legacy** (painel.css, login.css): Navy gradient sidebar (#2c5aa0 → #1e3f66), rounded cards, uppercase labels, dark-mode support, Segoe UI
2. **Admin theme v1** (top of admin-theme.css): #2563eb primary, 16px radius, dramatic shadow
3. **Shell v2** (bottom of admin-theme.css + painel_cliente): #3182ce primary, 12px radius, white sidebar with right-border accent, Chakra-inspired, **Open Sans**

The NEWEST/authoritative direction (shell v2) is what both surfaces converge to:
- Light theme, white surfaces on #f7fafc bg
- Primary #3182ce, primary-dark #2c5282
- White sidebar (256px) with right-border active accent
- Open Sans typography
- Hand-authored lucide-style SVG icons inline

## COPY / TONE
Brazilian Portuguese, formal-but-friendly business SaaS.
- "Bem-vindo, {name}!" (Welcome)
- "Visão consolidada dos clientes, emissões e reservas com hierarquia clara de informações."
- "Filtre para enxergar cartões e relatórios com o contexto correto."
- Button labels: "+ Novo Cliente", "+ Nova Emissão", "Entrar", "Logout", "Buscar", "Limpar"
- Some EMOJI used in stat labels: 👥 Total de Clientes, ✈️ Total de Emissões, 💰 Total Economizado, 👁️ Ver, ✏️ Editar, 🌙/☀️ dark mode toggle
- Labels in UPPERCASE with letter-spacing (.eyebrow class, form labels in legacy)
- "eyebrow" small-caps labels above section titles: "Indicadores" / "Resumo rápido"

## ICONOGRAPHY
- Primary: inline SVG, lucide-style (24x24 viewBox, stroke="currentColor", stroke-width=2, fill=none, round caps/joins)
- NO icon library dependency — hand-authored in templates
- Emoji mixed in as secondary icons (👥✈️💰 in stats, 👁️✏️ in table actions, ⋮ for dropdown, 🌙☀️ for dark mode)
- Logo: `painel_cliente/static/painel_cliente/ncfly_logo.png` — the NCfly logo; need to find the actual file

## KEY SCREENS
- accounts/login.html — centered card, logo, CPF/password/role dropdown, dark-mode toggle top-right
- gestao/dashboard.html — admin dashboard: filter panel → stat grid (clients, emissions, savings) → program stat cards → Emissions/Hotels summary → bar chart
- gestao/clientes.html — filter panel → table with pill status + ⋮ dropdown actions
- painel_cliente/dashboard.html — welcome, Programas de Fidelidade card grid (3 cols), Emissões/Hotéis cards
- painel_cliente/login.html — simpler login inside panel shell

## What's MISSING from repo (need to handle)
- Actual logo PNG file (ncfly_logo.png) — reference exists but binary blob not fetched
- No font files — uses Google Fonts Open Sans (hotlink)
- No raster imagery / marketing assets — B2B internal tool, so this is expected

## Products to build UI kits for
1. **Admin Panel (Gestão)** — operator-facing, dense data management
2. **Client Panel (Painel do Cliente)** — end-client read-only view
Both share login/accounts layer.
