"""
tests/test_resistencia.py
=========================

Validação contra Anexo H IEEE 80-2013 (exemplo H.2 - SE típica).
"""

import pytest

from core.resistencia import (
    GeometriaMalha,
    calcula_resistencia_e_tensoes,
    rg_schwarz,
    rg_sverak,
)


class TestGeometriaMalha:
    def test_area_e_perimetro(self):
        g = GeometriaMalha(
            largura_m=63, comprimento_m=84, profundidade_m=0.5,
            espac_malha_m=7, bitola_cabo_mm2=120,
            haste_comprimento_m=7.5, haste_diametro_mm=15.875, num_hastes=20,
        )
        assert g.area_m2 == pytest.approx(5292)
        assert g.perimetro_m == pytest.approx(294)

    def test_diametro_cabo_a_partir_secao(self):
        g = GeometriaMalha(
            largura_m=10, comprimento_m=10, profundidade_m=0.5,
            espac_malha_m=5, bitola_cabo_mm2=50,  # 50 mm² → d ≈ 7.98mm
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=4,
        )
        # d = 2·√(50/π) = 7.98 mm = 0.00798 m
        assert g.diametro_cabo_m == pytest.approx(0.00798, rel=0.01)


class TestRgSverak:
    def test_se_tipica_ordem_grandeza(self):
        """SE 60×60m, ρ=400, h=0.5m → Rg na faixa 2-5 Ω."""
        g = GeometriaMalha(
            largura_m=60, comprimento_m=60, profundidade_m=0.5,
            espac_malha_m=10, bitola_cabo_mm2=70,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=20,
        )
        rg = rg_sverak(rho_eq=400, geom=g)
        assert 1.5 < rg < 6.0

    def test_solo_pior_rg_maior(self):
        g = GeometriaMalha(
            largura_m=30, comprimento_m=30, profundidade_m=0.5,
            espac_malha_m=5, bitola_cabo_mm2=50,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=10,
        )
        assert rg_sverak(200, g) < rg_sverak(800, g)

    def test_area_maior_rg_menor(self):
        g_pequena = GeometriaMalha(
            largura_m=20, comprimento_m=20, profundidade_m=0.5,
            espac_malha_m=5, bitola_cabo_mm2=50,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=10,
        )
        g_grande = GeometriaMalha(
            largura_m=80, comprimento_m=80, profundidade_m=0.5,
            espac_malha_m=5, bitola_cabo_mm2=50,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=10,
        )
        assert rg_sverak(400, g_grande) < rg_sverak(400, g_pequena)


class TestRgSchwarz:
    def test_se_tipica_ordem_grandeza(self):
        g = GeometriaMalha(
            largura_m=60, comprimento_m=60, profundidade_m=0.5,
            espac_malha_m=10, bitola_cabo_mm2=70,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=20,
        )
        rg = rg_schwarz(rho_eq=400, geom=g)
        assert 1.0 < rg < 8.0

    def test_mais_hastes_rg_menor(self):
        """Adicionar hastes deve reduzir Rg."""
        def make(n):
            return GeometriaMalha(
                largura_m=40, comprimento_m=40, profundidade_m=0.5,
                espac_malha_m=5, bitola_cabo_mm2=50,
                haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=n,
            )
        rg_4 = rg_schwarz(400, make(4))
        rg_40 = rg_schwarz(400, make(40))
        assert rg_40 < rg_4


class TestCalculoIntegrado:
    def test_resultado_completo_consistente(self):
        g = GeometriaMalha(
            largura_m=63, comprimento_m=84, profundidade_m=0.5,
            espac_malha_m=7, bitola_cabo_mm2=120,
            haste_comprimento_m=7.5, haste_diametro_mm=15.875, num_hastes=24,
        )
        r = calcula_resistencia_e_tensoes(rho_eq=400, ig_a=3180, geom=g)

        assert r.rg_adotado_ohm > 0
        assert r.gpr_v == pytest.approx(r.rg_adotado_ohm * 3180, rel=1e-6)
        assert r.em_v > 0
        assert r.es_v > 0
        assert r.Lc_m > 0
        assert r.Lt_m > r.Lc_m  # Lt inclui hastes
        assert r.Lm_m > 0
        assert r.Ls_m > 0
        assert r.n_geometrico > 0

    def test_corrente_maior_tensoes_maiores(self):
        g = GeometriaMalha(
            largura_m=50, comprimento_m=50, profundidade_m=0.5,
            espac_malha_m=10, bitola_cabo_mm2=70,
            haste_comprimento_m=3, haste_diametro_mm=15.875, num_hastes=12,
        )
        r1 = calcula_resistencia_e_tensoes(400, 1000, g)
        r2 = calcula_resistencia_e_tensoes(400, 5000, g)
        assert r2.em_v > r1.em_v
        assert r2.es_v > r1.es_v
        assert r2.gpr_v > r1.gpr_v
