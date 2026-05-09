"""
data/repository.py
==================

Camada de repositório (CRUD) para projetos de malha de terra.
Centraliza o acesso ao banco para que a UI Streamlit fique limpa.

Padrão: cada função abre/fecha sua própria sessão via get_session().
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from data.db import get_session
from data.models import (
    DadosEntrada, Projeto, RelatorioGerado, Resultado, SoloWenner
)


# ============================================================
# PROJETOS - CRUD
# ============================================================

def cria_projeto(
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
    """
    Cria um novo projeto e retorna o ID.

    Raises:
        IntegrityError: se (numero_projeto, revisao) já existir.
    """
    with get_session() as s:
        p = Projeto(
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
        s.flush()  # gera o id
        return p.id


def busca_projeto(projeto_id: int) -> Optional[Projeto]:
    """
    Retorna o projeto com filhos eager-loaded (medições, dados, resultado).
    """
    with get_session() as s:
        stmt = (
            select(Projeto)
            .where(Projeto.id == projeto_id)
            .options(
                selectinload(Projeto.medicoes_wenner),
                selectinload(Projeto.dados_entrada),
                selectinload(Projeto.resultado),
            )
        )
        return s.execute(stmt).scalar_one_or_none()


def lista_projetos(limit: int = 100) -> list[Projeto]:
    """Lista projetos ordenados por data de cálculo (mais recentes primeiro)."""
    with get_session() as s:
        stmt = (
            select(Projeto)
            .order_by(Projeto.atualizado_em.desc())
            .limit(limit)
        )
        return list(s.execute(stmt).scalars().all())


def lista_revisoes_de(numero_projeto: str) -> list[Projeto]:
    """Retorna todas as revisões de um número de projeto, ordenadas."""
    with get_session() as s:
        stmt = (
            select(Projeto)
            .where(Projeto.numero_projeto == numero_projeto)
            .order_by(Projeto.revisao)
        )
        return list(s.execute(stmt).scalars().all())


def deleta_projeto(projeto_id: int) -> None:
    """Remove projeto e todos os filhos via CASCADE."""
    with get_session() as s:
        p = s.get(Projeto, projeto_id)
        if p:
            s.delete(p)


# ============================================================
# WENNER
# ============================================================

def salva_medicoes_wenner(
    projeto_id: int,
    medicoes: list[tuple[float, float]],
) -> None:
    """
    Substitui todas as medições Wenner do projeto.

    Args:
        projeto_id: id do projeto
        medicoes  : lista de (espacamento_m, resistencia_ohm)
    """
    import numpy as np
    with get_session() as s:
        # Apaga existentes
        s.query(SoloWenner).filter(SoloWenner.projeto_id == projeto_id).delete()
        # Insere novas
        for i, (esp, R) in enumerate(medicoes, start=1):
            rho = float(2.0 * np.pi * esp * R)
            s.add(SoloWenner(
                projeto_id=projeto_id,
                ponto=i,
                espacamento_m=esp,
                resistencia_ohm=R,
                rho_aparente=rho,
            ))


# ============================================================
# DADOS DE ENTRADA
# ============================================================

def salva_dados_entrada(projeto_id: int, **campos) -> None:
    """
    Cria ou atualiza os dados de entrada do projeto.
    Campos aceitos: largura_m, comprimento_m, profundidade_malha_m,
    espac_malha_principal_m, espac_malha_juncao_m, brita_*, haste_*,
    condutor_*, i_falta_3i0_ka, tempo_eliminacao_s, sf_div_corrente,
    xr_ratio, df_decremento, peso_pessoa_kg.
    """
    with get_session() as s:
        existente = s.query(DadosEntrada).filter_by(projeto_id=projeto_id).first()
        if existente:
            for k, v in campos.items():
                if hasattr(existente, k):
                    setattr(existente, k, v)
        else:
            s.add(DadosEntrada(projeto_id=projeto_id, **campos))


# ============================================================
# RESULTADOS
# ============================================================

def salva_resultado(projeto_id: int, **campos) -> None:
    """Cria ou atualiza o resultado do projeto."""
    with get_session() as s:
        existente = s.query(Resultado).filter_by(projeto_id=projeto_id).first()
        if existente:
            for k, v in campos.items():
                if hasattr(existente, k):
                    setattr(existente, k, v)
        else:
            s.add(Resultado(projeto_id=projeto_id, **campos))


# ============================================================
# RELATÓRIOS
# ============================================================

def registra_relatorio(
    projeto_id: int, nome_arquivo: str, gerado_por: Optional[str] = None
) -> int:
    """Registra que um relatório .docx foi gerado."""
    with get_session() as s:
        r = RelatorioGerado(
            projeto_id=projeto_id,
            nome_arquivo=nome_arquivo,
            gerado_por=gerado_por,
        )
        s.add(r)
        s.flush()
        return r.id


# ============================================================
# UTILITÁRIOS
# ============================================================

def proximo_numero_revisao(numero_projeto: str) -> str:
    """
    Sugere a próxima revisão para um número de projeto.
    Ex: se existem R00, R01, retorna 'R02'.
    """
    revs = lista_revisoes_de(numero_projeto)
    if not revs:
        return "00"
    nums = []
    for p in revs:
        try:
            nums.append(int(p.revisao))
        except ValueError:
            continue
    return f"{max(nums) + 1:02d}" if nums else "00"
