# BK Malha de Terra

Aplicação Streamlit para elaboração de **memórias de cálculo de malha de aterramento de subestações**, conforme:

- **IEEE Std 80-2013** — *Guide for Safety in AC Substation Grounding*
- **ABNT NBR 15751:2013** — Sistemas de aterramento de subestações
- **ABNT NBR 7117:2020** — Medição da resistividade e estratificação do solo

Desenvolvida pela **Barabach & Knopp Engenharia e Tecnologia (BK Engenharia)**.

---

## Funcionalidades

- Estratificação do solo em 2 camadas (Sunde) a partir de medições de Wenner
- Dimensionamento térmico do condutor (Sverak)
- Cálculo de IG com fator de decremento Df
- Tensões admissíveis Etoque/Epasso (50 ou 70 kg)
- Resistência da malha (Sverak + Schwarz)
- Tensões reais Em e Es (IEEE 80 §16.5)
- Iteração automática de número de hastes
- Posicionamento heurístico (cantos → bordas → interior)
- Visualizações Plotly 2D/3D
- Persistência em PostgreSQL (Neon) com revisões
- **Geração de relatório Word .docx completo**

---

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Streamlit |
| Cálculo | Python (numpy, scipy) |
| Banco | Neon PostgreSQL (SQLAlchemy + psycopg) |
| Gráficos | Plotly (2D/3D) |
| Relatório | python-docx + kaleido |
| Deploy | Railway |
| CI | GitHub Actions |

---

## Estrutura

```
bk-malha-terra/
├── app.py                 # Entry point Streamlit
├── core/                  # Cálculos IEEE 80
│   ├── solo.py            # Wenner + Sunde
│   ├── condutor.py        # Sverak
│   ├── corrente.py        # IG, Df
│   ├── tensoes.py         # Cs, Etoque, Epasso
│   ├── resistencia.py     # Rg (Sverak + Schwarz), Em, Es
│   ├── verificacao.py     # Critério IEEE 80 + iteração
│   └── geometria.py       # Posicionamento de hastes
├── data/                  # Persistência Neon
│   ├── db.py              # Engine + sessions
│   ├── models.py          # ORM
│   └── repository.py      # CRUD
├── ui/
│   └── visualizacoes.py   # Gráficos Plotly
├── relatorio/
│   ├── gerador_word.py    # Geração .docx
│   └── textos.py          # Metodologia/conclusão
├── migrations/
│   └── 001_schema_inicial.sql
├── tests/                 # 60 testes unitários
├── assets/                # Logo BK (colocar bk_logo.png aqui)
├── .github/workflows/     # CI
├── Procfile, railway.json, runtime.txt
└── requirements.txt
```

---

## Setup local

```bash
git clone https://github.com/Velho-do-Mal/bk-malha-terra.git
cd bk-malha-terra

python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate            # Windows

pip install -r requirements.txt

cp .env.example .env
# Editar .env com DATABASE_URL real do Neon

psql "$DATABASE_URL" -f migrations/001_schema_inicial.sql

PYTHONPATH=. pytest tests/ -v       # Roda os 60 testes

streamlit run app.py                # http://localhost:8501
```

---

## Deploy Railway

```bash
railway login
railway init

railway variables set DATABASE_URL="postgresql://..."
railway variables set DB_SCHEMA=bk_malha_terra

railway up

# Migration no Neon Console ou:
psql "$DATABASE_URL" -f migrations/001_schema_inicial.sql
```

Railway lê o `Procfile` e o `railway.json` automaticamente.

---

## Segurança

- Nunca commite `.env` (já no `.gitignore`)
- `DATABASE_URL` lida exclusivamente do ambiente
- Conexão Neon com `sslmode=require`
- Rotação de credenciais: Neon Console → Roles → Reset password

---

## Testes

```bash
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. python tests/smoke_test_caso_real.py
```

Cobertura atual: **60 testes** (incluindo Anexo H.1 da IEEE 80).

---

## Referências

- IEEE Std 80-2013
- ABNT NBR 15751, NBR 7117, NBR 5419, NBR 15749
- MAMEDE FILHO, J. *Manual de Equipamentos Elétricos*
- KINDERMANN, G. *Aterramento Elétrico*
- SVERAK, J. G. (1984), SUNDE, E. D. (1968)

---

Propriedade interna da BK Engenharia.
