"""
tests/test_condutor.py
======================

Testes do dimensionamento de condutor (Sverak).
Validação contra ordem de grandeza esperada para casos típicos BR.
"""

import pytest

from core.condutor import (
    Material,
    PROPRIEDADES,
    bitola_comercial,
    dimensiona_condutor,
    secao_minima_sverak,
)


class TestSverak:
    def test_corrente_e_tempo_positivos(self):
        with pytest.raises(ValueError):
            secao_minima_sverak(0, 0.5)
        with pytest.raises(ValueError):
            secao_minima_sverak(10000, 0)

    def test_tm_maior_que_ta(self):
        with pytest.raises(ValueError):
            secao_minima_sverak(10000, 0.5, temperatura_max_c=30, temperatura_amb_c=40)

    def test_ordem_grandeza_se_distribuicao(self):
        """
        SE distribuição típica: I=10kA, tc=0.5s, cobre.
        Esperado: bitola entre 30-70 mm² (Tm=250°C parafusado).
        """
        A = secao_minima_sverak(
            corrente_a=10000,
            tempo_s=0.5,
            material=Material.COBRE_NU,
            temperatura_max_c=250,
            temperatura_amb_c=40,
        )
        assert 30 < A < 80

    def test_corrente_maior_secao_maior(self):
        """Monotonicidade em I."""
        A1 = secao_minima_sverak(5000, 0.5)
        A2 = secao_minima_sverak(15000, 0.5)
        assert A2 > A1

    def test_tempo_maior_secao_maior(self):
        """Monotonicidade em tc."""
        A1 = secao_minima_sverak(10000, 0.2)
        A2 = secao_minima_sverak(10000, 1.0)
        assert A2 > A1


class TestBitolaComercial:
    def test_arredonda_para_cima(self):
        assert bitola_comercial(48.0) == 50.0
        assert bitola_comercial(60.0) == 70.0
        assert bitola_comercial(120.0) == 120.0

    def test_respeita_minimo_pratico(self):
        assert bitola_comercial(20.0, minimo_pratico_mm2=50) == 50.0


class TestDimensionaCondutorIntegrado:
    def test_resultado_completo(self):
        r = dimensiona_condutor(
            corrente_a=12000,
            tempo_s=0.5,
            material=Material.COBRE_NU,
            temperatura_max_c=250,
            minimo_pratico_mm2=50.0,
        )
        assert r.bitola_calculada_mm2 > 0
        assert r.bitola_adotada_mm2 >= r.bitola_minima_pratica_mm2
        assert r.bitola_adotada_mm2 in [50, 70, 95, 120, 150, 185, 240]
        assert "Cobre" in r.material

    def test_avisa_tm_proxima_fusao(self):
        r = dimensiona_condutor(
            corrente_a=10000, tempo_s=0.5,
            material=Material.COBRE_NU,
            temperatura_max_c=1083,
        )
        assert any("fusão" in obs.lower() or "Tm" in obs for obs in r.observacoes)


class TestPropriedadesMateriais:
    def test_todos_materiais_definidos(self):
        for mat in Material:
            assert mat in PROPRIEDADES
            p = PROPRIEDADES[mat]
            assert p.alpha_r > 0
            assert p.K0 > 0
            assert p.Tm > 100
            assert p.rho_r > 0
            assert p.TCAP > 0
