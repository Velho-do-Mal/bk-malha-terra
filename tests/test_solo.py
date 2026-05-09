"""
tests/test_solo.py
==================

Testes unitários do módulo core/solo.py.

Casos de teste baseados em:
- IEEE Std 80-2013, Anexo H (exemplos numéricos)
- NBR 7117:2020 - Anexo D (exemplo de estratificação)
- Mamede Filho - Manual de Equipamentos Elétricos, exemplos do cap. de aterramento

Para rodar:
    pytest tests/test_solo.py -v
"""

import numpy as np
import pytest

from core.solo import (
    MedicaoWenner,
    SoloEstratificado,
    calcula_rho_aparente,
    rho_aparente_sunde,
    estratifica_2_camadas,
    rho_equivalente_simplificado,
    gera_curva_teorica,
)


# ============================================================
# Testes de cálculo de ρ aparente (Wenner)
# ============================================================

class TestRhoAparenteWenner:
    """Verifica ρ_a = 2·π·a·R."""

    def test_rho_aparente_simples(self):
        """a=4m, R=10Ω → ρ_a = 2·π·4·10 ≈ 251,33 Ω·m"""
        m = MedicaoWenner(espacamento_m=4.0, resistencia_ohm=10.0)
        assert m.rho_aparente == pytest.approx(251.327, rel=1e-3)

    def test_rho_aparente_lista(self):
        """Lista de medições retorna lista de ρ_a."""
        medicoes = [
            MedicaoWenner(1.0, 100.0),   # ρ = 628,32
            MedicaoWenner(2.0, 80.0),    # ρ = 1005,3
            MedicaoWenner(4.0, 50.0),    # ρ = 1256,6
        ]
        rhos = calcula_rho_aparente(medicoes)
        assert len(rhos) == 3
        assert rhos[0] == pytest.approx(628.318, rel=1e-3)
        assert rhos[1] == pytest.approx(1005.310, rel=1e-3)
        assert rhos[2] == pytest.approx(1256.637, rel=1e-3)


# ============================================================
# Testes da função de Sunde (modelo direto)
# ============================================================

class TestSunde:
    """Verifica a função rho_aparente_sunde."""

    def test_solo_homogeneo_rho1_igual_rho2(self):
        """
        Quando ρ₁ = ρ₂, o solo é homogêneo: K = 0.
        ρ_a deve ser igual a ρ₁ para qualquer espaçamento.
        """
        rho = 500.0
        for a in [1.0, 2.0, 4.0, 8.0, 16.0]:
            assert rho_aparente_sunde(a, rho, rho, 5.0) == pytest.approx(rho, rel=1e-6)

    def test_a_pequeno_tende_a_rho1(self):
        """
        Para a << h₁: ρ_a → ρ₁ (medindo só a camada superior).
        """
        rho1, rho2, h1 = 100.0, 1000.0, 5.0
        rho_a = rho_aparente_sunde(0.1, rho1, rho2, h1)
        assert rho_a == pytest.approx(rho1, rel=0.05)  # 5% de tolerância

    def test_a_grande_tende_a_rho2(self):
        """
        Para a >> h₁: ρ_a → ρ₂ (medindo predominantemente a camada inferior).
        """
        rho1, rho2, h1 = 100.0, 1000.0, 1.0
        rho_a = rho_aparente_sunde(100.0, rho1, rho2, h1)
        # Tolerância maior porque convergência é assintótica
        assert rho_a == pytest.approx(rho2, rel=0.20)


# ============================================================
# Testes de estratificação (problema inverso)
# ============================================================

class TestEstratificacao:
    """Verifica o ajuste de modelo de 2 camadas."""

    def test_recupera_parametros_de_solo_sintetico(self):
        """
        Gera medições sintéticas com (ρ₁, ρ₂, h₁) conhecidos
        e verifica se o ajuste recupera esses valores.
        """
        rho1_real, rho2_real, h1_real = 300.0, 80.0, 2.5
        espacamentos = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]

        # Gera medições teóricas
        medicoes = []
        for a in espacamentos:
            rho_a = rho_aparente_sunde(a, rho1_real, rho2_real, h1_real)
            R = rho_a / (2.0 * np.pi * a)
            medicoes.append(MedicaoWenner(a, R))

        solo = estratifica_2_camadas(medicoes)

        # Tolerâncias frouxas porque é problema inverso
        assert solo.rho1 == pytest.approx(rho1_real, rel=0.05)
        assert solo.rho2 == pytest.approx(rho2_real, rel=0.10)
        assert solo.h1 == pytest.approx(h1_real, rel=0.15)
        assert solo.erro_rms < 1.0  # < 1%

    def test_erro_para_dados_insuficientes(self):
        """Menos de 3 medições deve levantar ValueError."""
        medicoes = [MedicaoWenner(1.0, 100.0), MedicaoWenner(2.0, 80.0)]
        with pytest.raises(ValueError, match="pelo menos 3 medições"):
            estratifica_2_camadas(medicoes)

    def test_solo_com_camada_superior_de_alta_resistividade(self):
        """
        Caso típico: brita/areia em cima (alta ρ) e argila embaixo (baixa ρ).
        """
        # Sintético: ρ₁=2000 (areia seca), ρ₂=50 (argila), h₁=1m
        rho1_real, rho2_real, h1_real = 2000.0, 50.0, 1.0
        espacamentos = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]

        medicoes = []
        for a in espacamentos:
            rho_a = rho_aparente_sunde(a, rho1_real, rho2_real, h1_real)
            R = rho_a / (2.0 * np.pi * a)
            medicoes.append(MedicaoWenner(a, R))

        solo = estratifica_2_camadas(medicoes)

        # Coeficiente de reflexão deve ser fortemente negativo
        assert solo.coef_reflexao < -0.5
        assert solo.rho1 > solo.rho2


# ============================================================
# Testes de ρ equivalente
# ============================================================

class TestRhoEquivalente:
    """Verifica o cálculo de ρ equivalente para uso simplificado."""

    def test_haste_dentro_camada_1(self):
        """
        Haste de 2m em solo com h₁ = 5m: deve usar ρ₁ inteiro.
        """
        solo = SoloEstratificado(rho1=300, rho2=100, h1=5.0)
        rho_eq = rho_equivalente_simplificado(solo, comprimento_haste=2.0)
        assert rho_eq == pytest.approx(300.0)

    def test_haste_atravessa_camadas(self):
        """
        Haste de 4m, h₁ = 1m: 1m em ρ₁ e 3m em ρ₂.
        ρ_eq = (1·300 + 3·100) / 4 = 150
        """
        solo = SoloEstratificado(rho1=300, rho2=100, h1=1.0)
        rho_eq = rho_equivalente_simplificado(solo, comprimento_haste=4.0)
        assert rho_eq == pytest.approx(150.0)

    def test_haste_exatamente_no_limite(self):
        """Lr = h₁ → ρ_eq = ρ₁."""
        solo = SoloEstratificado(rho1=500, rho2=200, h1=3.0)
        rho_eq = rho_equivalente_simplificado(solo, comprimento_haste=3.0)
        assert rho_eq == pytest.approx(500.0)


# ============================================================
# Testes da curva teórica
# ============================================================

class TestCurvaTeorica:
    """Verifica geração de curva ρ_a(a) para plotagem."""

    def test_dimensao_da_curva(self):
        solo = SoloEstratificado(rho1=200, rho2=80, h1=2.0)
        a, rho = gera_curva_teorica(solo, n_pontos=50)
        assert len(a) == 50
        assert len(rho) == 50
        assert a[0] < a[-1]  # crescente
        assert all(r > 0 for r in rho)  # física

    def test_valores_nos_extremos(self):
        """Curva deve tender a ρ₁ no início e a ρ₂ no fim."""
        solo = SoloEstratificado(rho1=200, rho2=80, h1=1.0)
        a, rho = gera_curva_teorica(solo, a_min=0.1, a_max=200.0, n_pontos=100)
        # Início próximo de ρ₁
        assert rho[0] == pytest.approx(solo.rho1, rel=0.10)
        # Fim caminhando para ρ₂
        assert abs(rho[-1] - solo.rho2) < abs(rho[0] - solo.rho2)


# ============================================================
# Caso prático real - exemplo Mamede simplificado
# ============================================================

class TestCasoMamede:
    """
    Exemplo adaptado de Mamede Filho - capítulo de aterramento.
    SE de distribuição típica.
    """

    def test_se_138kv_solo_tipico(self):
        """
        Medições típicas de campo em SE 138 kV no Sul do Brasil.
        Esperado: ρ₁ entre 100-300, ρ₂ menor (argila úmida abaixo).
        """
        medicoes = [
            MedicaoWenner(1.0, 47.7),    # ρ_a ≈ 300 Ω·m
            MedicaoWenner(2.0, 22.3),    # ρ_a ≈ 280 Ω·m
            MedicaoWenner(4.0, 9.5),     # ρ_a ≈ 239 Ω·m
            MedicaoWenner(8.0, 3.7),     # ρ_a ≈ 186 Ω·m
            MedicaoWenner(16.0, 1.4),    # ρ_a ≈ 141 Ω·m
            MedicaoWenner(32.0, 0.55),   # ρ_a ≈ 110 Ω·m
        ]

        solo = estratifica_2_camadas(medicoes)

        # Coerência física: ρ₁ > ρ₂ (decai com profundidade)
        assert solo.rho1 > solo.rho2
        assert solo.h1 > 0
        assert solo.erro_rms < 10.0  # ajuste razoável (< 10% RMS)
