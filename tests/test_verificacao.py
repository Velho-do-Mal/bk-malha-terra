"""
tests/test_verificacao.py
=========================
"""

import pytest

from core.resistencia import GeometriaMalha
from core.verificacao import itera_num_hastes, verifica_malha


class TestVerifica:
    def test_atende_quando_em_e_es_ok(self):
        v = verifica_malha(
            em_v=500, es_v=1500,
            gpr_v=2000,
            etoque_adm_v=800, epasso_adm_v=2500,
        )
        assert v.atende_toque
        assert v.atende_passo
        assert v.atende_geral
        assert v.margem_toque_pct > 0

    def test_nao_atende_toque(self):
        v = verifica_malha(
            em_v=900, es_v=1500,
            gpr_v=3000,
            etoque_adm_v=800, epasso_adm_v=2500,
        )
        assert not v.atende_toque
        assert not v.atende_geral
        assert v.margem_toque_pct < 0
        # v2: mensagem usa emoji ❌ e descreve excesso em Volts
        assert any("❌" in o for o in v.observacoes)

    def test_atende_gpr_simples(self):
        """GPR ≤ Etoque admissível → caso trivial."""
        v = verifica_malha(
            em_v=600, es_v=1000,
            gpr_v=750,  # < 800
            etoque_adm_v=800, epasso_adm_v=2500,
        )
        assert v.atende_gpr_simples
        assert v.atende_geral
        # v2: mensagem cita "simplificado" em vez de "intrinsecamente"
        assert any("simplificado" in o for o in v.observacoes)


class TestIteraHastes:
    def test_itera_ate_atender(self):
        """SE pequena, ρ moderado: deve convergir com poucas hastes."""
        geom = GeometriaMalha(
            largura_m=40, comprimento_m=40, profundidade_m=0.5,
            espac_malha_m=5, bitola_cabo_mm2=70,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=4,
        )
        resultado = itera_num_hastes(
            geom_inicial=geom,
            rho_eq=300,
            ig_a=3000,
            etoque_adm_v=900,
            epasso_adm_v=2800,
            n_hastes_min=4,
            n_hastes_max=80,
            incremento=4,
        )
        assert resultado.iteracoes >= 1
        assert resultado.geometria_final.num_hastes >= 4
        assert len(resultado.historico) == resultado.iteracoes

    def test_caso_dificil_nao_converge(self):
        """ρ muito alto + Eadm pequeno → não converge no limite."""
        geom = GeometriaMalha(
            largura_m=15, comprimento_m=15, profundidade_m=0.5,
            espac_malha_m=3, bitola_cabo_mm2=50,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=4,
        )
        resultado = itera_num_hastes(
            geom_inicial=geom,
            rho_eq=5000,  # solo péssimo
            ig_a=10000,   # IG alto
            etoque_adm_v=300,  # admissível baixíssimo
            epasso_adm_v=900,
            n_hastes_min=4,
            n_hastes_max=20,
            incremento=4,
        )
        # Pode não atender, mas deve retornar histórico
        assert resultado.iteracoes >= 1
        assert len(resultado.historico) >= 1
