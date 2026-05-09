"""
data/db.py
==========

Cliente de banco de dados Neon PostgreSQL para o BK Malha de Terra.

IMPORTANTE: A connection string é lida exclusivamente da variável de
ambiente DATABASE_URL. Nunca commitar credenciais.

Uso:
    from data.db import get_engine, get_session

    engine = get_engine()
    with get_session() as session:
        ...
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Carrega .env automaticamente (apenas em desenvolvimento)
load_dotenv()


# ============================================================
# Configuração
# ============================================================

def _get_database_url() -> str:
    """
    Retorna a connection string do Neon a partir do ambiente.

    Raises:
        RuntimeError: se DATABASE_URL não estiver definida.
    """
    url = os.getenv("psql 'postgresql://neondb_owner:npg_wn3oXv5eVFHr@ep-damp-glade-ap4htb9v-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'")
    if not url:
        raise RuntimeError(
            "Variável de ambiente DATABASE_URL não definida. "
            "Crie um arquivo .env baseado em .env.example, ou "
            "configure a variável no Railway."
        )
    return url


def _get_schema() -> str:
    """Retorna o schema do banco (default: bk_malha_terra)."""
    return os.getenv("DB_SCHEMA", "bk_malha_terra")


# ============================================================
# Engine e Session
# ============================================================

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """
    Retorna o engine SQLAlchemy (singleton).

    Configurações:
        - pool_pre_ping: testa conexão antes de usar (Neon hiberna)
        - pool_recycle: recicla conexões a cada 5 min
        - connect_args.options: define search_path automaticamente
    """
    global _engine
    if _engine is None:
        url = _get_database_url()
        schema = _get_schema()
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={
                "options": f"-csearch_path={schema},public"
            }
        )
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
# Healthcheck
# ============================================================

def testa_conexao() -> dict:
    """
    Testa conexão com o banco e retorna info útil.

    Returns:
        Dict com status, versão do PostgreSQL e schema atual.
    """
    try:
        with get_session() as s:
            versao = s.execute(text("SELECT version()")).scalar()
            schema = s.execute(text("SELECT current_schema()")).scalar()
            return {
                "status": "ok",
                "versao_postgres": versao,
                "schema": schema,
            }
    except Exception as e:
        return {
            "status": "erro",
            "erro": str(e),
        }


if __name__ == "__main__":
    # Permite testar conexão direto: python -m data.db
    import json
    print(json.dumps(testa_conexao(), indent=2, default=str))
