"""
data/db.py
==========

Cliente de banco de dados para o BK Malha de Terra.

Suporta dois backends, escolhidos automaticamente pela variável
DATABASE_URL:

1. **SQLite local** (desenvolvimento)
   DATABASE_URL=sqlite:///bk_local.db

2. **PostgreSQL** (Neon ou Docker local) (produção/staging)
   DATABASE_URL=postgresql://user:senha@host:porta/db?sslmode=require

A connection string é lida exclusivamente da variável de ambiente
DATABASE_URL. Nunca commitar credenciais.

Uso:
    from data.db import get_engine, get_session, inicializa_banco

    engine = get_engine()
    with get_session() as session:
        ...

Para inicializar tabelas (apenas em dev/SQLite):
    inicializa_banco()
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Carrega .env automaticamente em dev
load_dotenv()


# ============================================================
# Detecção de backend
# ============================================================

def _get_database_url() -> str:
    """
    Retorna a connection string a partir do ambiente.

    Raises:
        RuntimeError: se DATABASE_URL não estiver definida.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Variável de ambiente DATABASE_URL não definida.\n"
            "Para desenvolvimento local com SQLite, use:\n"
            "  DATABASE_URL=sqlite:///bk_local.db\n"
            "Para Neon (produção), use:\n"
            "  DATABASE_URL=postgresql://user:senha@host/db?sslmode=require"
        )
    return url


def _get_schema() -> str:
    """Retorna o schema do banco (default: bk_malha_terra)."""
    return os.getenv("DB_SCHEMA", "bk_malha_terra")


def is_sqlite() -> bool:
    """True se o backend atual é SQLite."""
    return _get_database_url().startswith("sqlite")


def is_postgres() -> bool:
    """True se o backend atual é PostgreSQL."""
    url = _get_database_url()
    return url.startswith("postgres")


# ============================================================
# Migração incremental de startup
# ============================================================

def _migrar_startup(engine: Engine) -> None:
    """
    Adiciona colunas novas em tabelas existentes (ADD COLUMN IF NOT EXISTS)
    e cria tabelas novas que ainda não existam no banco.

    Idempotente — seguro para rodar sempre que o engine é criado.
    Não levanta exceção: erros são silenciados para não bloquear o startup.
    """
    # Cria tabelas que ainda não existem (ex: rele_protecao, transformador_se)
    try:
        from data.models import Base
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        pass

    # Migrações de colunas só fazem sentido em PostgreSQL
    if not is_postgres():
        return

    schema = _get_schema()

    # Colunas adicionadas ao modelo BarraSistema após criação inicial da tabela
    colunas_barra_sistema = [
        ("base_mva",        "NUMERIC(10,3)  DEFAULT 100.0"),
        ("unidade_z",       "VARCHAR(10)    DEFAULT 'Ohm'"),
        ("z1_r_ohm",        "NUMERIC(15,6)"),
        ("z1_x_ohm",        "NUMERIC(15,6)"),
        ("z1_mod_ohm",      "NUMERIC(15,6)"),
        ("z1_ang_grau",     "NUMERIC(8,3)"),
        ("z2_r_ohm",        "NUMERIC(15,6)"),
        ("z2_x_ohm",        "NUMERIC(15,6)"),
        ("z0_r_ohm",        "NUMERIC(15,6)"),
        ("z0_x_ohm",        "NUMERIC(15,6)"),
        ("z0_mod_ohm",      "NUMERIC(15,6)"),
        ("z0_ang_grau",     "NUMERIC(8,3)"),
        ("icc_3f_ka",       "NUMERIC(12,4)"),
        ("icc_2f_ka",       "NUMERIC(12,4)"),
        ("icc_1f_ka",       "NUMERIC(12,4)"),
        ("icc_2f1f_ka",     "NUMERIC(12,4)"),
        ("ip_pico_ka",      "NUMERIC(12,4)"),
        ("xr_ratio",        "NUMERIC(8,3)"),
        ("kappa",           "NUMERIC(6,4)"),
        ("e_barra_projeto", "BOOLEAN DEFAULT FALSE"),
        ("observacoes",     "TEXT"),
        ("criado_em",       "TIMESTAMP DEFAULT NOW()"),
    ]

    # Colunas adicionadas ao modelo ReleProtecao após criação inicial
    colunas_rele_protecao = [
        ("ajuste_pickup_pu", "NUMERIC(10,4)"),
        ("curva",            "VARCHAR(100)"),
        ("observacoes",      "TEXT"),
        ("criado_em",        "TIMESTAMP DEFAULT NOW()"),
    ]

    # Colunas adicionadas ao modelo TransformadorSE após criação inicial
    colunas_transformador_se = [
        ("tag",               "VARCHAR(50)"),
        ("potencia_mva",      "NUMERIC(10,3)"),
        ("tensao_at_kv",      "NUMERIC(10,3)"),
        ("tensao_mt_kv",      "NUMERIC(10,3)"),
        ("tensao_bt_kv",      "NUMERIC(10,3)"),
        ("grupo_ligacao",     "VARCHAR(20)"),
        ("zcc_pct",           "NUMERIC(6,3)"),
        ("corrente_nom_at_a", "NUMERIC(10,2)"),
        ("corrente_nom_mt_a", "NUMERIC(10,2)"),
        ("fabricante",        "VARCHAR(100)"),
        ("numero_serie",      "VARCHAR(100)"),
        ("observacoes",       "TEXT"),
        ("criado_em",         "TIMESTAMP DEFAULT NOW()"),
    ]

    migracoes = [
        ("barra_sistema",    colunas_barra_sistema),
        ("rele_protecao",    colunas_rele_protecao),
        ("transformador_se", colunas_transformador_se),
    ]

    try:
        with engine.begin() as conn:
            for tabela, colunas in migracoes:
                for col, tipo in colunas:
                    conn.execute(text(
                        f'ALTER TABLE "{schema}".{tabela} '
                        f'ADD COLUMN IF NOT EXISTS {col} {tipo}'
                    ))
    except Exception:
        pass  # tabela pode não existir ainda — create_all já a criou acima


# ============================================================
# Engine e Session
# ============================================================

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """
    Retorna o engine SQLAlchemy (singleton).

    Na primeira chamada, além de criar o engine, executa _migrar_startup()
    para garantir que colunas novas existam no banco de produção.

    Configurações por backend:
        SQLite:
            - check_same_thread=False (Streamlit usa múltiplas threads)
            - sem schema (SQLite não tem)
        PostgreSQL:
            - pool_pre_ping (Neon hiberna)
            - pool_recycle 5min
            - search_path no schema definido
    """
    global _engine
    if _engine is None:
        url = _get_database_url()

        if url.startswith("sqlite"):
            _engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            schema = _get_schema()
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={
                    "options": f"-csearch_path={schema},public"
                }
            )

        # Aplica migrações incrementais na primeira inicialização
        _migrar_startup(_engine)

    return _engine


def get_session_factory() -> sessionmaker:
    """Retorna o factory de sessions (singleton)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Session]:
    """
    Context manager de sessão com commit/rollback automáticos.

    Uso:
        with get_session() as session:
            session.execute(...)
            # commit automático na saída sem exceção
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ============================================================
# Inicialização (DEV - SQLite ou Postgres novo)
# ============================================================

def inicializa_banco(forcar: bool = False) -> dict:
    """
    Cria todas as tabelas no banco a partir dos modelos ORM.

    Útil para inicializar o SQLite local ou um Postgres novo sem
    precisar rodar `psql -f migrations/001_schema_inicial.sql`.

    Args:
        forcar: se True, dropa tudo e recria (CUIDADO em prod).

    Returns:
        Dict com info do banco inicializado.

    Raises:
        RuntimeError: se forcar=True em ambiente que parece produção.
    """
    # Importa aqui para evitar import circular
    from data.models import Base

    engine = get_engine()
    schema = _get_schema()

    # Salvaguarda: nunca dropar em produção sem flag explícita extra
    if forcar:
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ("production", "prod"):
            raise RuntimeError(
                "Recusando drop_all em produção. Defina ENVIRONMENT=development "
                "se realmente quiser fazer isso (não recomendado)."
            )

    if is_postgres():
        # Cria schema se não existir
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            conn.execute(text(f'SET search_path TO "{schema}"'))
        # Aplica metadata
        if forcar:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        backend = "postgres"
    else:
        # SQLite: sem schema, tabelas direto
        if forcar:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        backend = "sqlite"

    # Conta tabelas criadas
    with engine.connect() as conn:
        if is_sqlite():
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ))
        else:
            result = conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = :s"
            ), {"s": schema})
        tabelas = [row[0] for row in result]

    return {
        "backend": backend,
        "schema": schema if is_postgres() else "(sqlite não tem schema)",
        "tabelas": tabelas,
        "n_tabelas": len(tabelas),
        "forcado": forcar,
    }


# ============================================================
# Healthcheck
# ============================================================

def testa_conexao() -> dict:
    """
    Testa conexão com o banco e retorna info útil.

    Returns:
        Dict com status, backend, versão e schema atual.
    """
    try:
        with get_session() as s:
            if is_sqlite():
                versao = s.execute(text("SELECT sqlite_version()")).scalar()
                schema_info = "(SQLite - banco em arquivo único)"
                backend = "SQLite"
            else:
                versao = s.execute(text("SELECT version()")).scalar()
                schema_info = s.execute(text("SELECT current_schema()")).scalar()
                backend = "PostgreSQL"

            # Conta tabelas
            if is_sqlite():
                n_tab = s.execute(text(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )).scalar()
            else:
                schema = _get_schema()
                n_tab = s.execute(text(
                    "SELECT COUNT(*) FROM pg_tables WHERE schemaname = :s"
                ), {"s": schema}).scalar()

            return {
                "status": "ok",
                "backend": backend,
                "versao": versao[:80] if versao else "?",
                "schema": schema_info,
                "tabelas_existentes": n_tab,
            }
    except Exception as e:
        return {
            "status": "erro",
            "erro": str(e),
        }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    """
    Uso direto:
        python -m data.db                  # apenas testa conexão
        python -m data.db init             # cria tabelas se não existirem
        python -m data.db reset            # APAGA tudo e recria (cuidado!)
    """
    import sys
    import json

    args = sys.argv[1:]

    if not args:
        print("=" * 60)
        print("Healthcheck do banco")
        print("=" * 60)
        print(json.dumps(testa_conexao(), indent=2, default=str))

    elif args[0] == "init":
        print("Inicializando banco (criando tabelas se não existirem)...")
        try:
            r = inicializa_banco(forcar=False)
            print(json.dumps(r, indent=2, default=str))
            print("\n✓ Banco inicializado com sucesso.")
        except Exception as e:
            print(f"✗ Erro: {e}")
            sys.exit(1)

    elif args[0] == "reset":
        confirmacao = input(
            "\n⚠️  ATENÇÃO: isso vai APAGAR todos os dados do banco.\n"
            "   Digite 'SIM APAGAR' para confirmar: "
        )
        if confirmacao != "SIM APAGAR":
            print("Cancelado.")
            sys.exit(0)
        try:
            r = inicializa_banco(forcar=True)
            print(json.dumps(r, indent=2, default=str))
            print("\n✓ Banco resetado.")
        except Exception as e:
            print(f"✗ Erro: {e}")
            sys.exit(1)

    else:
        print(f"Comando desconhecido: {args[0]}")
        print("Uso: python -m data.db [init|reset]")
        sys.exit(1)
