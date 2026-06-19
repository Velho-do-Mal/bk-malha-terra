"""
data/repository.py ? BK Malha de Terra v2 (Multi-Tenant)
=========================================================
Todas as fun��es recebem tenant_id obrigat�rio.
Garante isolamento: nenhuma query retorna dados de outro tenant.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from data.db import get_session
from data.models import (
    BarraSistema, DadosEntrada, Projeto, RelatorioGerado, Resultado,
    ReleProtecao, SoloWenner, Tenant, TransformadorSE, Usuario,
)
from data.sanitizacao import sanitiza_kwargs, to_python


# ??? PROJETOS ????????????????????????????????????????????????????????????????

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
        # Verifica limite do plano
        tenant = s.query(Tenant).filter_by(id=tenant_id).first()
        if tenant:
            n = s.query(Projeto).filter_by(tenant_id=tenant_id).count()
            if n >= tenant.max_projetos:
                raise RuntimeError(
                    f"Limite de {tenant.max_projetos} projetos do plano "
                    f"{tenant.plano} atingido. Fa�a upgrade para continuar."
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
    """Lista projetos DO TENANT. Nunca retorna projetos de outros tenants."""
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
                selectinload(Projeto.barras),
                selectinload(Projeto.reles),
                selectinload(Projeto.transformadores),
            )
        )
        return s.scalars(stmt).first()


def atualiza_projeto(
    projeto_id: int,
    tenant_id: int,
    **campos,
) -> bool:
    """Atualiza campos do projeto. Retorna True se encontrado."""
    campos = sanitiza_kwargs(campos)
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


# ??? SOLO WENNER ?????????????????????????????????????????????????????????????

def salva_medicoes_wenner(
    projeto_id: int,
    tenant_id: int,
    medicoes: list[dict],
) -> int:
    """Substitui medi��es Wenner do projeto. Retorna quantidade salva."""
    with get_session() as s:
        # Verificar propriedade
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto n�o encontrado ou acesso negado.")

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


# ??? DADOS DE ENTRADA ????????????????????????????????????????????????????????

def salva_dados_entrada(
    projeto_id: int,
    tenant_id: int,
    **campos,
) -> None:
    """Upsert de dados_entrada. Verifica propriedade do tenant."""
    campos = sanitiza_kwargs(campos)
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto n�o encontrado ou acesso negado.")

        de = s.query(DadosEntrada).filter_by(projeto_id=projeto_id).first()
        if de is None:
            de = DadosEntrada(projeto_id=projeto_id)
            s.add(de)

        for k, v in campos.items():
            if hasattr(de, k):
                setattr(de, k, v)


# ??? RESULTADO ???????????????????????????????????????????????????????????????

def salva_resultado(
    projeto_id: int,
    tenant_id: int,
    **campos,
) -> None:
    """Upsert de resultado. Verifica propriedade do tenant."""
    campos = sanitiza_kwargs(campos)
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto n�o encontrado ou acesso negado.")

        res = s.query(Resultado).filter_by(projeto_id=projeto_id).first()
        if res is None:
            res = Resultado(projeto_id=projeto_id)
            s.add(res)

        for k, v in campos.items():
            if hasattr(res, k):
                setattr(res, k, v)


def registra_relatorio(
    projeto_id: int,
    tenant_id: int,
    nome_arquivo: str,
    gerado_por: Optional[str] = None,
) -> None:
    """Registra gera��o de relat�rio Word."""
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto n�o encontrado ou acesso negado.")
        s.add(RelatorioGerado(
            projeto_id=projeto_id,
            nome_arquivo=nome_arquivo,
            gerado_por=gerado_por,
        ))


# ??? TENANT / ADMIN ??????????????????????????????????????????????????????????

def info_tenant(tenant_id: int) -> Optional[dict]:
    """Retorna informa��es do tenant para exibi��o."""
    with get_session() as s:
        t = s.query(Tenant).filter_by(id=tenant_id).first()
        if not t:
            return None
        n_projetos = s.query(Projeto).filter_by(tenant_id=tenant_id).count()
        n_usuarios = s.query(Usuario).filter_by(tenant_id=tenant_id, ativo=True).count()
        return {
            "nome_empresa":  t.nome_empresa,
            "plano":         t.plano,
            "plano_label":   t.plano_label,
            "max_projetos":  t.max_projetos,
            "max_usuarios":  t.max_usuarios,
            "n_projetos":    n_projetos,
            "n_usuarios":    n_usuarios,
            "trial_expira":  t.trial_expira_em,
            "ativo":         t.ativo,
        }


# --- RELATORIOS ---

def lista_relatorios_de(projeto_id: int):
    """Lista relatorios gerados para o projeto, do mais recente ao mais antigo."""
    with get_session() as s:
        rels = (
            s.query(RelatorioGerado)
            .filter_by(projeto_id=projeto_id)
            .order_by(RelatorioGerado.gerado_em.desc())
            .all()
        )
        return [
            dict(
                gerado_em=r.gerado_em,
                nome_arquivo=r.nome_arquivo,
                gerado_por=r.gerado_por,
            )
            for r in rels
        ]


# ═══════════════════════════════════════════════════════════════
# BARRAS DO SISTEMA ELÉTRICO
# ═══════════════════════════════════════════════════════════════

def salva_barras_sistema(
    projeto_id: int,
    tenant_id: int,
    barras: list[dict],
) -> int:
    """Substitui todas as barras do projeto. Retorna quantidade salva."""
    from data.sanitizacao import sanitiza_kwargs
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto não encontrado ou acesso negado.")
        s.query(BarraSistema).filter_by(projeto_id=projeto_id).delete()
        for i, b in enumerate(barras):
            b_clean = sanitiza_kwargs({k: v for k, v in b.items() if k != "projeto_id"})
            s.add(BarraSistema(projeto_id=projeto_id, ordem=i, **b_clean))
        return len(barras)


def lista_barras(projeto_id: int) -> list[BarraSistema]:
    with get_session() as s:
        return (
            s.query(BarraSistema)
            .filter_by(projeto_id=projeto_id)
            .order_by(BarraSistema.ordem)
            .all()
        )


# ═══════════════════════════════════════════════════════════════
# RELÉS DE PROTEÇÃO
# ═══════════════════════════════════════════════════════════════

def salva_reles(
    projeto_id: int,
    tenant_id: int,
    reles: list[dict],
) -> int:
    """Substitui todos os relés. Calcula tc automaticamente."""
    from data.sanitizacao import sanitiza_kwargs
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto não encontrado ou acesso negado.")
        s.query(ReleProtecao).filter_by(projeto_id=projeto_id).delete()
        for r in reles:
            r_clean = sanitiza_kwargs({k: v for k, v in r.items() if k != "projeto_id"})
            if not r_clean.get("tempo_total_tc_s"):
                t_r = float(r_clean.get("tempo_rele_s") or 0)
                t_dj = float(r_clean.get("tempo_abertura_dj_s") or 0.05)
                r_clean["tempo_total_tc_s"] = round(t_r + t_dj, 4)
            s.add(ReleProtecao(projeto_id=projeto_id, **r_clean))
        return len(reles)


def lista_reles(projeto_id: int) -> list[ReleProtecao]:
    with get_session() as s:
        return (
            s.query(ReleProtecao)
            .filter_by(projeto_id=projeto_id)
            .order_by(ReleProtecao.nivel, ReleProtecao.id)
            .all()
        )


def get_tc_adotado(projeto_id: int) -> Optional[float]:
    with get_session() as s:
        r = s.query(ReleProtecao).filter_by(projeto_id=projeto_id, e_tc_adotado=True).first()
        return float(r.tempo_total_tc_s) if r and r.tempo_total_tc_s else None


# ═══════════════════════════════════════════════════════════════
# TRANSFORMADORES
# ═══════════════════════════════════════════════════════════════

def salva_transformadores(
    projeto_id: int,
    tenant_id: int,
    transformadores: list[dict],
) -> int:
    """Substitui todos os transformadores do projeto."""
    from data.sanitizacao import sanitiza_kwargs
    with get_session() as s:
        p = s.query(Projeto).filter_by(id=projeto_id, tenant_id=tenant_id).first()
        if not p:
            raise PermissionError("Projeto não encontrado ou acesso negado.")
        s.query(TransformadorSE).filter_by(projeto_id=projeto_id).delete()
        for t in transformadores:
            t_clean = sanitiza_kwargs({k: v for k, v in t.items() if k != "projeto_id"})
            s.add(TransformadorSE(projeto_id=projeto_id, **t_clean))
        return len(transformadores)


def lista_transformadores(projeto_id: int) -> list[TransformadorSE]:
    with get_session() as s:
        return s.query(TransformadorSE).filter_by(projeto_id=projeto_id).all()
