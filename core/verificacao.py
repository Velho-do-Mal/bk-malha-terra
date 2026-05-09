"""
core/verificacao.py
===================

Verificação de adequação da malha conforme IEEE Std 80-2013.

Fluxograma de projeto (IEEE 80 §16.4):

    1. Dados elétricos e do solo
    2. Dimensiona condutor
    3. Calcula tensões admissíveis (toque, passo)
    4. Define geometria inicial da malha (D, h, hastes)
    5. Calcula Rg
    6. Calcula GPR = IG·Rg
    7. Se GPR < Etoque admissível → OK, projeto seguro
    8. Senão, calcula Em e Es
    9. Se Em < Etoque admissível E Es < Epasso admissível → OK
    10. Senão, ajusta geometria (mais cabos, mais hastes, brita) e volta ao 5

Este módulo implementa a verificação (passos 7-9) e uma rotina de
iteração automática para ajustar o número de hastes (passo 10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.resistencia import (
    GeometriaMalha,
    ResultadoResistencia,
    calcula_resistencia_e_tensoes,
)


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class Verificacao:
    """Resultado da verificação de uma configuração de malha."""
    em_v: float
    es_v: float
    etoque_adm_v: float
    epasso_adm_v: float
    gpr_v: float
    atende_toque: bool
    atende_passo: bool
    atende_gpr_simples: bool   # GPR < Etoque (caso trivial)
    atende_geral: bool
    margem_toque_pct: float    # (Eadm − Em)/Eadm · 100
    margem_passo_pct: float
    observacoes: list[str]


@dataclass
class IteracaoMalha:
    """Resultado da iteração automática de hastes."""
    geometria_final: GeometriaMalha
    resultado: ResultadoResistencia
    verificacao: Verificacao
    iteracoes: int
    historico: list[dict]


# ============================================================
# VERIFICAÇÃO DE UMA CONFIGURAÇÃO
# ============================================================

def verifica_malha(
    em_v: float,
    es_v: float,
    gpr_v: float,
    etoque_adm_v: float,
    epasso_adm_v: float,
) -> Verificacao:
    """
    Verifica se a malha atende aos critérios de segurança IEEE 80.

    Critério principal:
        Em ≤ Etoque_adm   AND   Es ≤ Epasso_adm

    Critério simplificado (passo 7 do fluxograma):
        Se GPR ≤ Etoque_adm: malha atende sem necessidade de calcular Em/Es
        (porque qualquer ponto da malha terá tensão ≤ GPR)

    Args:
        em_v        : tensão de malha calculada [V]
        es_v        : tensão de passo calculada [V]
        gpr_v       : Ground Potential Rise [V]
        etoque_adm_v: tensão de toque admissível [V]
        epasso_adm_v: tensão de passo admissível [V]

    Returns:
        Verificacao com status e margens.
    """
    atende_toque = em_v <= etoque_adm_v
    atende_passo = es_v <= epasso_adm_v
    atende_gpr   = gpr_v <= etoque_adm_v

    margem_toque = (etoque_adm_v - em_v) / etoque_adm_v * 100.0
    margem_passo = (epasso_adm_v - es_v) / epasso_adm_v * 100.0

    obs = []
    if atende_gpr:
        obs.append(
            f"GPR ({gpr_v:.0f} V) ≤ Etoque admissível "
            f"({etoque_adm_v:.0f} V): malha intrinsecamente segura."
        )
    if margem_toque < 10 and atende_toque:
        obs.append(
            f"Margem de toque pequena ({margem_toque:.1f}%). "
            "Recomenda-se reforço (mais hastes ou cabo)."
        )
    if margem_passo < 10 and atende_passo:
        obs.append(
            f"Margem de passo pequena ({margem_passo:.1f}%). "
            "Verificar pontos críticos (cantos, periferia)."
        )
    if not atende_toque:
        obs.append(
            f"NÃO ATENDE tensão de toque: Em={em_v:.0f}V > Eadm={etoque_adm_v:.0f}V. "
            f"Excesso de {em_v - etoque_adm_v:.0f}V ({-margem_toque:.1f}%)."
        )
    if not atende_passo:
        obs.append(
            f"NÃO ATENDE tensão de passo: Es={es_v:.0f}V > Eadm={epasso_adm_v:.0f}V. "
            f"Excesso de {es_v - epasso_adm_v:.0f}V ({-margem_passo:.1f}%)."
        )

    return Verificacao(
        em_v=em_v,
        es_v=es_v,
        etoque_adm_v=etoque_adm_v,
        epasso_adm_v=epasso_adm_v,
        gpr_v=gpr_v,
        atende_toque=atende_toque,
        atende_passo=atende_passo,
        atende_gpr_simples=atende_gpr,
        atende_geral=atende_toque and atende_passo,
        margem_toque_pct=margem_toque,
        margem_passo_pct=margem_passo,
        observacoes=obs,
    )


# ============================================================
# ITERAÇÃO AUTOMÁTICA DE HASTES
# ============================================================

def itera_num_hastes(
    geom_inicial: GeometriaMalha,
    rho_eq: float,
    ig_a: float,
    etoque_adm_v: float,
    epasso_adm_v: float,
    n_hastes_min: int = 4,
    n_hastes_max: int = 200,
    incremento: int = 4,
) -> IteracaoMalha:
    """
    Itera o número de hastes até atender critérios de segurança ou
    atingir o limite máximo.

    Estratégia:
    1. Começa com n_hastes_min (mínimo: 4 hastes nos cantos)
    2. Calcula Rg, Em, Es, GPR
    3. Verifica
    4. Se atende, retorna
    5. Senão, incrementa hastes e tenta de novo
    6. Se atingir n_hastes_max sem atender, retorna a última config
       (usuário deve revisar geometria, profundidade ou solo)

    Args:
        geom_inicial: geometria inicial (sem hastes ou com poucas)
        rho_eq      : ρ equivalente do solo [Ω·m]
        ig_a        : corrente de malha IG [A]
        etoque_adm_v: tensão de toque admissível [V]
        epasso_adm_v: tensão de passo admissível [V]
        n_hastes_min: número inicial de hastes
        n_hastes_max: limite superior
        incremento  : passo de incremento de hastes

    Returns:
        IteracaoMalha com geometria final, resultado e histórico.
    """
    historico = []
    n_hastes_atual = n_hastes_min
    iteracoes = 0

    while n_hastes_atual <= n_hastes_max:
        iteracoes += 1

        geom = GeometriaMalha(
            largura_m=geom_inicial.largura_m,
            comprimento_m=geom_inicial.comprimento_m,
            profundidade_m=geom_inicial.profundidade_m,
            espac_malha_m=geom_inicial.espac_malha_m,
            bitola_cabo_mm2=geom_inicial.bitola_cabo_mm2,
            haste_comprimento_m=geom_inicial.haste_comprimento_m,
            haste_diametro_mm=geom_inicial.haste_diametro_mm,
            num_hastes=n_hastes_atual,
        )

        res = calcula_resistencia_e_tensoes(rho_eq, ig_a, geom)
        verif = verifica_malha(
            em_v=res.em_v,
            es_v=res.es_v,
            gpr_v=res.gpr_v,
            etoque_adm_v=etoque_adm_v,
            epasso_adm_v=epasso_adm_v,
        )

        historico.append({
            "iteracao": iteracoes,
            "n_hastes": n_hastes_atual,
            "rg_ohm": res.rg_adotado_ohm,
            "em_v": res.em_v,
            "es_v": res.es_v,
            "gpr_v": res.gpr_v,
            "atende": verif.atende_geral,
        })

        if verif.atende_geral:
            return IteracaoMalha(
                geometria_final=geom,
                resultado=res,
                verificacao=verif,
                iteracoes=iteracoes,
                historico=historico,
            )

        n_hastes_atual += incremento

    # Não convergiu — retorna última configuração
    return IteracaoMalha(
        geometria_final=geom,
        resultado=res,
        verificacao=verif,
        iteracoes=iteracoes,
        historico=historico,
    )
