"""
tests/test_tensoes.py
=====================

Validação contra exemplo 1 do Anexo H da IEEE 80-2013 (caso clássico).
"""

import pytest

from core.tensoes import (
    calcula_tensoes_admissiveis,
    fator_cs,
    tensao_passo_admissivel,
    tensao_toque_admissivel,
)


class TestFatorCs:
    def test_sem_brita(self):
        assert fator_cs(rho_solo=400, rho_brita=3000, h_brita=0) == 1.0

    def test_brita_padrao_ieee(self):
        """ρ_solo=400, ρ_brita=2500, h=0.102m → Cs ≈ 0.74 (ex. H1 IEEE 80)"""
        cs = fator_cs(rho_solo=400, rho_brita=2500, h_brita=0.102)
        assert 0.70 < cs < 0.80

    def test_brita_grossa_aumenta_cs(self):
        """Brita mais espessa → Cs mais próximo de 1."""
        cs1 = fator_cs(400, 3000, 0.10)
        cs2 = fator_cs(400, 3000, 0.20)
        assert cs2 > cs1

    def test_solo_igual_brita(self):
        """ρ_solo = ρ_brita → Cs = 1 (sem efeito)."""
        cs = fator_cs(rho_solo=3000, rho_brita=3000, h_brita=0.10)
        assert cs == pytest.approx(1.0, rel=1e-6)


class TestTensoesAdmissiveis:
    def test_anexo_h1_ieee80(self):
        """
        Exemplo H.1 IEEE 80-2013 (caso clássico):
            ρ_solo=400, ρ_brita=2500, h_brita=0.102m
            tc=0.5s, peso=70kg
        Resultados esperados (norma):
            Cs ≈ 0.74
            Etoque70 ≈ 838 V
            Epasso70 ≈ 2687 V
        """
        r = calcula_tensoes_admissiveis(
            rho_solo=400,
            rho_brita=2500,
            h_brita=0.102,
            tempo_s=0.5,
            peso_kg=70,
        )
        assert r.cs_brita == pytest.approx(0.74, abs=0.02)
        assert r.etoque_v == pytest.approx(838, rel=0.05)
        assert r.epasso_v == pytest.approx(2687, rel=0.05)

    def test_50kg_mais_conservador(self):
        """Peso 50kg → tensões admissíveis menores que 70kg."""
        r50 = calcula_tensoes_admissiveis(400, 2500, 0.10, 0.5, peso_kg=50)
        r70 = calcula_tensoes_admissiveis(400, 2500, 0.10, 0.5, peso_kg=70)
        assert r50.etoque_v < r70.etoque_v
        assert r50.epasso_v < r70.epasso_v

    def test_peso_invalido(self):
        with pytest.raises(ValueError):
            calcula_tensoes_admissiveis(400, 2500, 0.10, 0.5, peso_kg=60)

    def test_tempo_curto_aumenta_admissivel(self):
        """tc menor → corpo suporta mais corrente → Etoque maior."""
        r1 = calcula_tensoes_admissiveis(400, 2500, 0.10, 0.5, 50)
        r2 = calcula_tensoes_admissiveis(400, 2500, 0.10, 0.1, 50)
        assert r2.etoque_v > r1.etoque_v

    def test_passo_maior_que_toque(self):
        """Sempre Epasso > Etoque (pelos coefs 6 vs 1.5)."""
        r = calcula_tensoes_admissiveis(400, 3000, 0.10, 0.5, 50)
        assert r.epasso_v > r.etoque_v
