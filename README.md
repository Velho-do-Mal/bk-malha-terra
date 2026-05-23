# BK Malha de Terra v2 — SaaS Multi-Tenant

> IEEE 80-2013 · NBR 15751 · NBR 7117 · Multi-tenant · Correções P0

## O que mudou na v2

### Multi-Tenancy
- Tenant = empresa cliente; cada empresa vê apenas seus próprios projetos
- Roles: `admin` (gerencia usuários) | `engenheiro` (edita) | `viewer` (leitura)
- Isolamento duplo: FK `tenant_id` no banco + filtro obrigatório em todas as queries

### Correções P0 (relatório técnico BK 22/05/2026)
| Correção | Arquivo | Impacto |
|---|---|---|
| Fator Cp — crescimento da corrente | `core/corrente.py` | IG = Df·Sf·**Cp**·3I₀ |
| Condutor bloqueia aprovação | `core/verificacao.py` | atende_geral = condutor AND tensões |
| Critério GPR rastreável | `core/verificacao.py` | informa simplificado vs detalhado |

### Novas telas
- Tela de login/cadastro (trial 14 dias gratuito)
- Painel admin: gerenciar usuários, ver limites do plano, alterar senha

## Estrutura
```
bk-malha-terra-v2/
├── app.py                  ← auth gate no main()
├── auth/
│   ├── auth.py             ← bcrypt, sessão, CRUD usuários
│   ├── pagina_login.py     ← login + cadastro
│   └── pagina_admin.py     ← painel admin
├── core/
│   ├── corrente.py         ← + Cp (P0)
│   └── verificacao.py      ← atende_condutor + criterio (P0)
├── data/
│   ├── models.py           ← Tenant + Usuario + tenant_id
│   └── repository.py       ← todas queries com tenant_id
├── migrations/
│   ├── 001_schema_inicial.sql
│   └── 002_multitenancy.sql  ← NOVO
├── scripts/
│   └── setup_inicial.py    ← cria primeiro admin
└── requirements.txt        ← + bcrypt>=4.1.0
```

## Deploy Railway (primeiro deploy)
```bash
# 1. Push
git push origin main

# 2. Variáveis de ambiente Railway:
#    DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require
#    DB_SCHEMA=bk_malha_terra
#    ENVIRONMENT=production

# 3. Aplicar migration (terminal Railway ou psql):
psql "$DATABASE_URL" -f migrations/002_multitenancy.sql

# 4. Criar primeiro admin:
python scripts/setup_inicial.py
```

## Upgrade v1 → v2 (banco existente)
```bash
psql "$DATABASE_URL" -f migrations/002_multitenancy.sql
# A migration cria tenant padrão e migra projetos existentes automaticamente.
```

## Planos
| Plano | Projetos | Usuários |
|---|---|---|
| trial | 3 | 2 |
| pro | 50 | 5 |
| enterprise | ∞ | ∞ |
