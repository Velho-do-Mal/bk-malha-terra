"""
data/repository.py - BK Malha de Terra v2 (Multi-Tenant)
=========================================================
Todas as funcoes recebem tenant_id obrigatorio.
Garante isolamento: nenhuma query retorna dados de outro tenant.

v2.1 - remove imports inexistentes (BarraSistema etc.)
       garante lista_relatorios_de
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from data.db import get_session
from data.models import (
    DadosEntrada, Projeto, RelatorioGerado, Resultado,
    SoloWenner, Tenant, Usuario,
)
from data.sanitizacao import sanitiza_kwargs, to_python


# --- PROJETOS ----------------------------------------------------------------

def cria_projeto(
    tenant_id: int,
    criado_por_id: Optional[int],
    cliente: str,
    nome_projeto: str,
    numero_projeto: str,
    revisao: str = "00",
    responsavel_tecnico: Optional[str] = None,
    crea_responsavel: Optional[str] = None,
    concessionaria: Optional[str] = None,
    data_calculo: Optional[date] = None,
    observacoes: Optional[str] = None,
) -> int:
    """Cria projeto e retorna ID. Isolado por tenant_id."""
    with get_session() as s:
        tenant = s.query(Tenant).filter_by(id=tenant_id).first()
        if tenant:
            n = s.query(Projeto).filter_by(tenant_id=tenant_id).count()
            if n >= tenant.max_projetos:
                raise RuntimeError(
                    f"Limite de {tenant.max_projetos} projetos do plano "
                    f"{tenant.plano} atingido. Faca upgrade para continuar."
                )
        p = Projeto(
            tenant_id=tenant_id,
            criado_por_id=criado_por_id,
            cliente=cliente,
            nome_projeto=nome_projeto,
            numero_projeto=numero_projeto,
            revisao=revisao,
            responsavel_tecnico=responsavel_tecnico,
            crea_responsavel=crea_responsavel,
            concessionaria=concessionaria,
            data_calculo=data_calculo or date.today(),
            observacoes=observacoes,
        )
        s.add(p)
        s.flush()
        return p.id


def lista_projetos(tenant_id: int, limit: int = 100) -> list[Projeto]:
    """Lista projetos DO TENANT."""
    with get_session() as s:
        stmt = (
            select(Projeto)
            .where(Projeto.tenant_id == tenant_id)
            .order_by(Projeto.atualizado_em.desc())
            .limit(limit)
        )
        return list(s.scalars(stmt).all())


def busca_projeto(projeto_id: int, tenant_id: int) -> Optional[Projeto]:
    """Busca projeto por ID, garantindo que pertence ao tenant."""
    with get_session() as s:
        stmt = (
            select(Projeto)
            .where(Projeto.id == projeto_id, Projeto.tenant_id == tenant_id)
            .options(
                selectinload(Projeto.medicoes_wenner),
                selectinload(Projeto.dados_entrada),
                selectinload(Projeto.resultado),
                selectinload(Projeto.relatorios),
            )
        )
        return s.scalars(stmt).first()


def atualiza_projeto(projeto_id: int, tenant_id: int, **campos) -> bool:
    """Atualiza campos do projeto. Retorna True se encontrado."""
    campos = sanitiza_kwargs(**campos)
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            return False
        for k, v in campos.items():
            if hasattr(p, k):
                setattr(p, k, v)
        return True


def deleta_projeto(projeto_id: int, tenant_id: int) -> bool:
    """Deleta projeto (cascade para filhos). Retorna True se deletado."""
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            return False
        s.delete(p)
        return True


# --- SOLO WENNER -------------------------------------------------------------

def salva_medicoes_wenner(
    projeto_id: int,
    tenant_id: int,
    medicoes: list[dict],
) -> int:
    """Substitui medicoes Wenner do projeto. Retorna quantidade salva."""
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto nao encontrado ou acesso negado.")
        s.query(SoloWenner).filter_by(projeto_id=projeto_id).delete()
        for i, m in enumerate(medicoes, start=1):
            s.add(SoloWenner(
                projeto_id=projeto_id,
                ponto=i,
                espacamento_m=float(m["espacamento_m"]),
                resistencia_ohm=float(m["resistencia_ohm"]),
                rho_aparente=float(m.get("rho_aparente", 0)) or None,
            ))
        return len(medicoes)


# --- DADOS DE ENTRADA --------------------------------------------------------

def salva_dados_entrada(projeto_id: int, tenant_id: int, **campos) -> None:
    """Upsert de dados_entrada. Verifica propriedade do tenant."""
    campos = sanitiza_kwargs(**campos)
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto nao encontrado ou acesso negado.")
        de = s.query(DadosEntrada).filter_by(projeto_id=projeto_id).first()
        if de is None:
            de = DadosEntrada(projeto_id=projeto_id)
            s.add(de)
        for k, v in campos.items():
            if hasattr(de, k):
                setattr(de, k, v)


# --- RESULTADO ---------------------------------------------------------------

def salva_resultado(projeto_id: int, tenant_id: int, **campos) -> None:
    """Upsert de resultado. Verifica propriedade do tenant."""
    campos = sanitiza_kwargs(**campos)
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto nao encontrado ou acesso negado.")
        res = s.query(Resultado).filter_by(projeto_id=projeto_id).first()
        if res is None:
            res = Resultado(projeto_id=projeto_id)
            s.add(res)
        for k, v in campos.items():
            if hasattr(res, k):
                setattr(res, k, v)


# --- RELATORIO ---------------------------------------------------------------

def registra_relatorio(
    projeto_id: int,
    tenant_id: int,
    nome_arquivo: str,
    gerado_por: Optional[str] = None,
) -> None:
    """Registra geracao de relatorio Word."""
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto nao encontrado ou acesso negado.")
        s.add(RelatorioGerado(
            projeto_id=projeto_id,
            nome_arquivo=nome_arquivo,
            gerado_por=gerado_por,
        ))


def lista_relatorios_de(projeto_id: int) -> list[dict]:
    """Lista relatorios gerados para o projeto, do mais recente ao mais antigo."""
    with get_session() as s:
        rels = (
            s.query(RelatorioGerado)
            .filter_by(projeto_id=projeto_id)
            .order_by(RelatorioGerado.gerado_em.desc())
            .all()
        )
        return [
            {
                "gerado_em": r.gerado_em,
                "nome_arquivo": r.nome_arquivo,
                "gerado_por": r.gerado_por,
            }
            for r in rels
        ]


# --- TENANT / ADMIN ----------------------------------------------------------

def info_tenant(tenant_id: int) -> Optional[dict]:
    """Retorna informacoes do tenant para exibicao."""
    with get_session() as s:
        t = s.query(Tenant).filter_by(id=tenant_id).first()
        if not t:
            return None
        n_projetos = s.query(Projeto).filter_by(tenant_id=tenant_id).count()
        n_usuarios = s.query(Usuario).filter_by(tenant_id=tenant_id, ativo=True).count()
        return {
            "nome_empresa": t.nome_empresa,
            "plano": t.plano,
            "plano_label": t.plano_label,
            "max_projetos": t.max_projetos,
            "max_usuarios": t.max_usuarios,
            "n_projetos": n_projetos,
            "n_usuarios": n_usuarios,
            "trial_expira": t.trial_expira_em,
            "ativo": t.ativo,
        }
