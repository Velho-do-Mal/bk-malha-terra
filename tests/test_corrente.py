"""
tests/test_corrente.py
======================
"""

import pytest

from core.corrente import corrente_malha_ig, fator_decremento


class TestFatorDecremento:
    def test_xr_baixo_df_proximo_um(self):
        """X/R baixo → componente DC pequena → Df ≈ 1."""
        df = fator_decremento(xr_ratio=2, tf_s=0.5)
        assert df < 1.05

    def test_tf_longo_df_proximo_um(self):
        """tf longo → DC já decaiu → Df ≈ 1."""
        df = fator_decremento(xr_ratio=20, tf_s=2.0)
        assert df < 1.05

    def test_xr_alto_tf_curto_df_elevado(self):
        """X/R alto + tf curto → Df > 1.2."""
        df = fator_decremento(xr_ratio=30, tf_s=0.05)
        assert df > 1.20

    def test_valores_negativos(self):
        with pytest.raises(ValueError):
            fator_decremento(-1, 0.5)
        with pytest.raises(ValueError):
            fator_decremento(10, -0.1)


class TestIG:
    def test_ig_calculo_basico(self):
        r = corrente_malha_ig(
            i_falta_3i0_a=10000,
            sf_div_corrente=0.6,
            xr_ratio=10,
            tf_s=0.5,
        )
        # IG = Df · 0.6 · 10000 ≈ 6000-6500 A
        assert 5800 < r.ig_a < 7000
        assert r.df_decremento >= 1.0

    def test_sf_invalido(self):
        with pytest.raises(ValueError):
            corrente_malha_ig(10000, sf_div_corrente=1.5,
                               xr_ratio=10, tf_s=0.5)
        with pytest.raises(ValueError):
            corrente_malha_ig(10000, sf_div_corrente=0,
                               xr_ratio=10, tf_s=0.5)

    def test_corrente_invalida(self):
        with pytest.raises(ValueError):
            corrente_malha_ig(0, 0.6, 10, 0.5)
