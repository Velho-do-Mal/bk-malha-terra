"""
core/verificacao.py — BK Malha de Terra v2
==========================================

Verificação IEEE 80 §16 com correções P0 do relatório técnico BK:
  - atende_condutor bloqueia aprovação (P0.3)
  - atende_geral = condutor AND (GPR_simples OR toque+passo)  (P0.2)
  - criterio_aprovacao informa se foi simplificado ou detalhado
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.resistencia import (
    GeometriaMalha, ResultadoResistencia, calcula_resistencia_e_tensoes,
)


@dataclass
class Verificacao:
    em_v:             float
    es_v:             float
    etoque_adm_v:     float
    epasso_adm_v:     float
    gpr_v:            float
    atende_toque:     bool
    atende_passo:     bool
    atende_condutor:  bool     # P0: condutor bloqueia aprovação
    atende_gpr_simples: bool
    atende_geral:     bool     # CORRIGIDO: condutor AND (GPR ou toque+passo)
    criterio_aprovacao: str
    margem_toque_pct: float
    margem_passo_pct: float
    observacoes:      list[str]


@dataclass
class IteracaoMalha:
    geometria_final: GeometriaMalha
    resultado:       ResultadoResistencia
    verificacao:     Verificacao
    iteracoes:       int
    historico:       list[dict]


def verifica_malha(
    em_v: float,
    es_v: float,
    gpr_v: float,
    etoque_adm_v: float,
    epasso_adm_v: float,
    bitola_adotada_mm2: float = 0.0,
    bitola_calculada_mm2: float = 0.0,
) -> Verificacao:
    """
    Verifica adequação da malha IEEE 80 §16.

    CORREÇÃO P0: atende_geral exige condutor térmico ok.
        atende_geral = atende_condutor AND (atende_gpr OR (atende_toque AND atende_passo))
    """
    atende_toque    = em_v  <= etoque_adm_v
    atende_passo    = es_v  <= epasso_adm_v
    atende_gpr      = gpr_v <= etoque_adm_v
    atende_condutor = (bitola_adotada_mm2 >= bitola_calculada_mm2) if bitola_calculada_mm2 > 0 else True

    margem_toque = (etoque_adm_v - em_v)  / etoque_adm_v * 100.0
    margem_passo = (epasso_adm_v - es_v)  / epasso_adm_v * 100.0

    atende_tensoes = atende_gpr or (atende_toque and atende_passo)
    atende_geral   = atende_condutor and atende_tensoes

    if not atende_condutor:
        criterio = "reprovado — condutor térmico insuficiente"
    elif not atende_tensoes:
        criterio = "reprovado — tensões acima do admissível"
    elif atende_gpr:
        criterio = "aprovado — critério simplificado (GPR ≤ Etoque)"
    else:
        criterio = "aprovado — critério detalhado (Em/Es ≤ Eadm)"

    obs = []
    if not atende_condutor:
        obs.append(
            f"❌ CONDUTOR REPROVADO: adotado {bitola_adotada_mm2:.0f} mm² "
            f"< mínimo {bitola_calculada_mm2:.0f} mm². "
            "Projeto NÃO PODE SER APROVADO. Aumente a bitola."
        )
    if atende_gpr:
        obs.append(
            f"✅ GPR ({gpr_v:.0f} V) ≤ Etoque ({etoque_adm_v:.0f} V): "
            "critério simplificado IEEE 80 §16 atendido."
        )
    if margem_toque < 10 and atende_toque:
        obs.append(f"⚠️ Margem de toque pequena ({margem_toque:.1f}%). Considere reforço.")
    if margem_passo < 10 and atende_passo:
        obs.append(f"⚠️ Margem de passo pequena ({margem_passo:.1f}%). Verificar periferia.")
    if not atende_toque:
        obs.append(
            f"❌ Tensão de malha: Em={em_v:.0f}V > Eadm={etoque_adm_v:.0f}V "
            f"(excesso {em_v - etoque_adm_v:.0f}V)."
        )
    if not atende_passo:
        obs.append(
            f"❌ Tensão de passo: Es={es_v:.0f}V > Eadm={epasso_adm_v:.0f}V "
            f"(excesso {es_v - epasso_adm_v:.0f}V)."
        )

    return Verificacao(
        em_v=em_v, es_v=es_v,
        etoque_adm_v=etoque_adm_v, epasso_adm_v=epasso_adm_v,
        gpr_v=gpr_v,
        atende_toque=atende_toque, atende_passo=atende_passo,
        atende_condutor=atende_condutor,
        atende_gpr_simples=atende_gpr,
        atende_geral=atende_geral,
        criterio_aprovacao=criterio,
        margem_toque_pct=margem_toque,
        margem_passo_pct=margem_passo,
        observacoes=obs,
    )


def itera_num_hastes(
    geom_inicial: GeometriaMalha,
    rho_eq: float,
    ig_a: float,
    etoque_adm_v: float,
    epasso_adm_v: float,
    bitola_adotada_mm2: float = 0.0,
    bitola_calculada_mm2: float = 0.0,
    n_hastes_min: int = 4,
    n_hastes_max: int = 200,
    incremento: int = 4,
) -> IteracaoMalha:
    """
    Itera o número de hastes até atender (ou atingir limite).
    Agora passa bitola para verifica_malha (correção P0).
    """
    historico = []
    n_hastes_atual = n_hastes_min
    geom = verif = res = None

    while n_hastes_atual <= n_hastes_max:
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
            em_v=res.em_v, es_v=res.es_v, gpr_v=res.gpr_v,
            etoque_adm_v=etoque_adm_v, epasso_adm_v=epasso_adm_v,
            bitola_adotada_mm2=bitola_adotada_mm2,
            bitola_calculada_mm2=bitola_calculada_mm2,
        )
        historico.append({
            "iteracao": len(historico) + 1,
            "n_hastes": n_hastes_atual,
            "rg_ohm": res.rg_adotado_ohm,
            "em_v": res.em_v, "es_v": res.es_v, "gpr_v": res.gpr_v,
            "atende": verif.atende_geral,
        })
        if verif.atende_geral:
            break
        n_hastes_atual += incremento

    return IteracaoMalha(
        geometria_final=geom,
        resultado=res,
        verificacao=verif,
        iteracoes=len(historico),
        historico=historico,
    )
