"""
core/solo.py
============

Tratamento de medições de resistividade do solo conforme:
- ABNT NBR 7117:2020 - Medição da resistividade e determinação da
  estratificação do solo.
- IEEE Std 80-2013 - §13 Soil characteristics.

Responsabilidades:
1. Calcular ρ aparente a partir das medições de Wenner.
2. Ajustar modelo de solo de 2 camadas (ρ₁, ρ₂, h₁) por otimização.
3. Calcular ρ equivalente para uso em cálculos simplificados (Sverak).

Método de Wenner (NBR 7117 §6.2):
    Quatro eletrodos igualmente espaçados (a) em linha reta.
    Resistividade aparente:

        ρ_a = 2 · π · a · R                 (NBR 7117 eq. 1)

    onde R é a resistência medida no terrômetro.

Estratificação 2 camadas (NBR 7117 §7 e Sunde):
    O solo é modelado como duas camadas:
        - Camada 1: resistividade ρ₁, espessura h₁
        - Camada 2: resistividade ρ₂, profundidade infinita
    Coeficiente de reflexão:
        K = (ρ₂ - ρ₁) / (ρ₂ + ρ₁)
    A resistividade aparente para espaçamento 'a' (Sunde):
        ρ_a(a) = ρ₁ · [1 + 4·Σ_{n=1}^{∞} ( K^n / √(1+(2nh₁/a)²)
                                         - K^n / √(4+(2nh₁/a)²) )]
    Os parâmetros (ρ₁, ρ₂, h₁) são obtidos minimizando o erro
    quadrático em relação às medições de Wenner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from scipy.optimize import minimize

# Número de termos na série de Sunde (truncamento)
_N_TERMOS_SUNDE = 200


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class MedicaoWenner:
    """Uma medição individual de Wenner."""
    espacamento_m: float       # a [m]
    resistencia_ohm: float     # R [Ω]

    @property
    def rho_aparente(self) -> float:
        """ρ_a = 2·π·a·R [Ω·m]   -   NBR 7117 eq. 1"""
        return 2.0 * np.pi * self.espacamento_m * self.resistencia_ohm


@dataclass
class SoloEstratificado:
    """
    Modelo de solo de 2 camadas resultante da estratificação.

    Atributos:
        rho1: resistividade da camada superficial [Ω·m]
        rho2: resistividade da camada profunda    [Ω·m]
        h1  : espessura da camada superficial     [m]
        erro_rms: erro RMS percentual do ajuste   [%]
    """
    rho1: float
    rho2: float
    h1: float
    erro_rms: float = 0.0

    @property
    def coef_reflexao(self) -> float:
        """K = (ρ₂ − ρ₁) / (ρ₂ + ρ₁)"""
        return (self.rho2 - self.rho1) / (self.rho2 + self.rho1)


# ============================================================
# FUNÇÕES PRINCIPAIS
# ============================================================

def calcula_rho_aparente(medicoes: List[MedicaoWenner]) -> List[float]:
    """
    Calcula a resistividade aparente para cada medição.

    Args:
        medicoes: lista de medições de Wenner.

    Returns:
        Lista de ρ_a em Ω·m, na mesma ordem das medições.
    """
    return [m.rho_aparente for m in medicoes]


def rho_aparente_sunde(a: float, rho1: float, rho2: float,
                        h1: float, n_termos: int = _N_TERMOS_SUNDE) -> float:
    """
    Resistividade aparente teórica do modelo de 2 camadas (série de Sunde).

    Args:
        a       : espaçamento Wenner [m]
        rho1    : resistividade camada superior [Ω·m]
        rho2    : resistividade camada inferior [Ω·m]
        h1      : espessura camada superior [m]
        n_termos: número de termos da série truncada

    Returns:
        ρ aparente teórica [Ω·m].

    Referência:
        Sunde, E.D. "Earth Conduction Effects in Transmission Systems",
        Dover, 1968. Equação adotada pela NBR 7117 §7.2.
    """
    if rho1 <= 0 or rho2 <= 0 or h1 <= 0 or a <= 0:
        return float('inf')

    K = (rho2 - rho1) / (rho2 + rho1)
    soma = 0.0
    for n in range(1, n_termos + 1):
        razao = (2 * n * h1) / a
        termo1 = (K ** n) / np.sqrt(1.0 + razao ** 2)
        termo2 = (K ** n) / np.sqrt(4.0 + razao ** 2)
        soma += (termo1 - termo2)

    return rho1 * (1.0 + 4.0 * soma)


def estratifica_2_camadas(medicoes: List[MedicaoWenner]) -> SoloEstratificado:
    """
    Ajusta um modelo de 2 camadas às medições de Wenner.

    A otimização minimiza o erro quadrático relativo entre ρ_a medido
    e ρ_a teórico (Sunde), variando ρ₁, ρ₂ e h₁.

    Args:
        medicoes: pelo menos 4 medições com espaçamentos crescentes.

    Returns:
        SoloEstratificado com parâmetros ajustados e erro RMS.

    Raises:
        ValueError: se houver menos de 3 medições.

    Notas:
        - Chute inicial: ρ₁ ≈ ρ_a do menor espaçamento,
                        ρ₂ ≈ ρ_a do maior espaçamento,
                        h₁ ≈ menor espaçamento.
        - O método usa L-BFGS-B com bounds para evitar valores
          fisicamente impossíveis.
    """
    if len(medicoes) < 3:
        raise ValueError(
            "Estratificação requer pelo menos 3 medições Wenner. "
            "Recomenda-se ≥ 4 com espaçamentos 1, 2, 4, 8, 16 m (NBR 7117)."
        )

    # Ordena por espaçamento
    medicoes = sorted(medicoes, key=lambda m: m.espacamento_m)
    espac = np.array([m.espacamento_m for m in medicoes])
    rho_med = np.array([m.rho_aparente for m in medicoes])

    # Chute inicial
    rho1_0 = float(rho_med[0])
    rho2_0 = float(rho_med[-1])
    h1_0 = float(espac[0])

    def erro(params):
        rho1, rho2, h1 = params
        rho_teo = np.array(
            [rho_aparente_sunde(a, rho1, rho2, h1) for a in espac]
        )
        # Erro quadrático relativo (mais robusto que absoluto)
        return float(np.sum(((rho_teo - rho_med) / rho_med) ** 2))

    # Bounds físicos: ρ ∈ [10, 100000] Ω·m, h ∈ [0.1, 50] m
    bounds = [(10.0, 100000.0), (10.0, 100000.0), (0.1, 50.0)]

    resultado = minimize(
        erro,
        x0=[rho1_0, rho2_0, h1_0],
        method='L-BFGS-B',
        bounds=bounds,
        options={'ftol': 1e-10, 'gtol': 1e-8, 'maxiter': 500}
    )

    rho1_fit, rho2_fit, h1_fit = resultado.x

    # Erro RMS percentual
    rho_teo_final = np.array(
        [rho_aparente_sunde(a, rho1_fit, rho2_fit, h1_fit) for a in espac]
    )
    erro_rel = (rho_teo_final - rho_med) / rho_med
    erro_rms_pct = float(np.sqrt(np.mean(erro_rel ** 2)) * 100.0)

    return SoloEstratificado(
        rho1=float(rho1_fit),
        rho2=float(rho2_fit),
        h1=float(h1_fit),
        erro_rms=erro_rms_pct
    )


def rho_equivalente_simplificado(solo: SoloEstratificado,
                                  comprimento_haste: float) -> float:
    """
    Calcula ρ equivalente para um solo de 2 camadas considerando
    a profundidade de penetração das hastes.

    Aproximação prática (NBR 15751 / Tagg):
        Se a haste fica inteiramente na camada 1 (Lr ≤ h₁): ρ_eq ≈ ρ₁
        Se atravessa a interface, usa-se média ponderada por comprimento:
            ρ_eq = (h₁ · ρ₁ + (Lr − h₁) · ρ₂) / Lr

    Para uso em fórmulas que assumem solo uniforme (Sverak/Schwarz),
    uma boa estimativa é o ρ médio na profundidade da malha + haste.

    Args:
        solo             : solo estratificado já ajustado
        comprimento_haste: comprimento da haste em metros

    Returns:
        ρ equivalente [Ω·m]

    Atenção:
        Para projetos críticos, recomenda-se software dedicado
        (CDEGS, TecAt) que trata solo estratificado rigorosamente.
    """
    Lr = comprimento_haste

    if Lr <= solo.h1:
        return solo.rho1

    return (solo.h1 * solo.rho1 + (Lr - solo.h1) * solo.rho2) / Lr


def rho_aparente_malha(solo: SoloEstratificado,
                        profundidade_malha: float,
                        comprimento_haste: float = 0.0) -> float:
    """
    Calcula ρ aparente para Sverak/Schwarz considerando estratificação 
    do solo (IEEE 80 §13.4.2 + Tagg/Endrenyi).

    Diferente de rho_equivalente_simplificado, esta função considera
    que a malha (na profundidade h) injeta corrente em ambas as camadas.
    Para solos com ρ₂ < ρ₁ (caso comum), o resultado é uma média
    ponderada que reduz Rg adequadamente.

    Fórmula adotada (média geométrica ponderada por profundidade):

        Se Lr > h₁:
            ρ_a = (h₁·ρ₁ + (Lr+h_malha-h₁)·ρ₂) / (Lr+h_malha)
        Senão:
            ρ_a = ρ₁  (haste só vê camada 1)

    Para profundidade total de penetração d_total = h_malha + Lr.

    Args:
        solo              : solo estratificado
        profundidade_malha: h em metros
        comprimento_haste : Lr em metros (0 se sem hastes)

    Returns:
        ρ aparente [Ω·m] - valor para usar em Sverak/Schwarz/Em/Es
    """
    h_malha = profundidade_malha
    Lr = comprimento_haste
    h1 = solo.h1
    
    # Profundidade total que a malha "vê" (cabos + hastes)
    profundidade_total = h_malha + Lr
    
    # Caso 1: tudo na camada 1
    if profundidade_total <= h1:
        return solo.rho1
    
    # Caso 2: atravessa a interface
    parte_camada1 = max(0, h1 - h_malha)  # fração que ainda está em ρ1
    parte_camada2 = profundidade_total - max(h_malha, h1)  # fração em ρ2
    
    if parte_camada1 + parte_camada2 == 0:
        return solo.rho1
    
    rho_a = (parte_camada1 * solo.rho1 + parte_camada2 * solo.rho2) / \
            (parte_camada1 + parte_camada2)
    return float(rho_a)


# ============================================================
# UTILITÁRIOS
# ============================================================

def gera_curva_teorica(solo: SoloEstratificado,
                        a_min: float = 0.5,
                        a_max: float = 32.0,
                        n_pontos: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """
    Gera a curva ρ_a(a) teórica do modelo ajustado.

    Útil para plotar a curva contínua sobre os pontos medidos.

    Args:
        solo    : solo estratificado
        a_min   : espaçamento mínimo [m]
        a_max   : espaçamento máximo [m]
        n_pontos: número de pontos da curva

    Returns:
        Tupla (espaçamentos [m], ρ_a teórico [Ω·m])
    """
    espac = np.logspace(np.log10(a_min), np.log10(a_max), n_pontos)
    rho_teo = np.array([
        rho_aparente_sunde(a, solo.rho1, solo.rho2, solo.h1)
        for a in espac
    ])
    return espac, rho_teo
