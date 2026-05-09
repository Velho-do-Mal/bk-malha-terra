"""
core/resistencia.py
===================

Cálculo da resistência da malha de aterramento (Rg) e tensões reais
de malha (Em) e passo (Es) conforme IEEE Std 80-2013.

Métodos implementados:

1. SVERAK (eq. 52 IEEE 80) - Rg simplificada:

                 ⎡ 1            1                  1            ⎤
   Rg = ρ · ⎢ ─── + ────────── · ⎜1 + ─────────────⎟ ⎥
                 ⎣ Lt          √(20·A)              1+h·√(20/A)   ⎦

   onde:
       ρ  = resistividade do solo [Ω·m]
       Lt = comprimento total enterrado (cabo + hastes) [m]
       A  = área da malha [m²]
       h  = profundidade da malha [m]

2. SCHWARZ (eqs. 53-58) - Rg combinando cabos + hastes:

   R1 = ρ/(π·Lc) · [ln(2·Lc/a') + k1·Lc/√A − k2]   (cabos)
   R2 = ρ/(2π·n·Lr) · [ln(8·Lr/d) − 1 + 2·k1·Lr·(√n − 1)²/√A]  (hastes)
   Rm = ρ/(π·Lc) · [ln(2·Lc/Lr) + k1·Lc/√A − k2 + 1]  (mútua)
   Rg = (R1·R2 − Rm²) / (R1 + R2 − 2·Rm)

3. TENSÃO DE MALHA (eq. 80):

   Em = ρ·Km·Ki·IG / Lm

4. TENSÃO DE PASSO (eq. 92):

   Es = ρ·Ks·Ki·IG / Ls
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class GeometriaMalha:
    """Geometria da malha de aterramento."""
    largura_m: float           # W
    comprimento_m: float       # L
    profundidade_m: float      # h (enterramento da malha)
    espac_malha_m: float       # D (espaçamento entre cabos paralelos)
    bitola_cabo_mm2: float     # seção do cabo
    haste_comprimento_m: float # Lr
    haste_diametro_mm: float   # d
    num_hastes: int            # n

    @property
    def area_m2(self) -> float:
        return self.largura_m * self.comprimento_m

    @property
    def perimetro_m(self) -> float:
        return 2.0 * (self.largura_m + self.comprimento_m)

    @property
    def diametro_cabo_m(self) -> float:
        """Diâmetro equivalente do cabo a partir da seção."""
        return float(np.sqrt(4.0 * self.bitola_cabo_mm2 / np.pi) / 1000.0)

    def comprimento_cabos_m(self) -> float:
        """
        Comprimento total dos cabos formando a malha em grade retangular.
        Aproximação: nx cabos paralelos a L + ny cabos paralelos a W.
        """
        nx = int(np.ceil(self.comprimento_m / self.espac_malha_m)) + 1
        ny = int(np.ceil(self.largura_m / self.espac_malha_m)) + 1
        return nx * self.largura_m + ny * self.comprimento_m

    def comprimento_total_lt(self) -> float:
        """Lt = Lc + Lr·n  (cabo + hastes)"""
        return self.comprimento_cabos_m() + self.haste_comprimento_m * self.num_hastes


@dataclass
class ResultadoResistencia:
    """Resultado completo do cálculo de Rg."""
    rg_sverak_ohm: float
    rg_schwarz_ohm: float
    rg_adotado_ohm: float
    em_v: float
    es_v: float
    gpr_v: float
    Lc_m: float
    Lt_m: float
    Lm_m: float
    Ls_m: float
    Km: float
    Ki: float
    Ks: float
    n_geometrico: float


# ============================================================
# Rg - SVERAK (eq. 52)
# ============================================================

def rg_sverak(rho_eq: float, geom: GeometriaMalha) -> float:
    """
    Resistência da malha por Sverak (IEEE 80 eq. 52).

    Args:
        rho_eq: resistividade equivalente do solo [Ω·m]
        geom  : geometria da malha

    Returns:
        Rg [Ω]
    """
    A = geom.area_m2
    Lt = geom.comprimento_total_lt()
    h = geom.profundidade_m

    if A <= 0 or Lt <= 0:
        raise ValueError("Área e Lt devem ser positivos.")

    termo1 = 1.0 / Lt
    termo2 = (1.0 / np.sqrt(20.0 * A)) * (1.0 + 1.0 / (1.0 + h * np.sqrt(20.0 / A)))
    return float(rho_eq * (termo1 + termo2))


# ============================================================
# Rg - SCHWARZ (eqs. 53-58)
# ============================================================

def _schwarz_k1_k2(geom: GeometriaMalha) -> Tuple[float, float]:
    """
    Coeficientes geométricos de Schwarz (Fig. 25 IEEE 80).
    Aproximação por curve-fit em função de razão lado L/W e profundidade.
    """
    L = max(geom.largura_m, geom.comprimento_m)
    W = min(geom.largura_m, geom.comprimento_m)
    razao = L / W if W > 0 else 1.0
    h = geom.profundidade_m
    A = geom.area_m2
    h_norm = h / np.sqrt(A) if A > 0 else 0.0

    # Aproximações IEEE 80 Fig. 25 (Sverak 1981)
    # k1 ≈ −0.04·razão + 1.41  (para h pequeno)
    # k2 ≈  0.15·razão + 5.50
    # Correção para h:
    k1 = -0.04 * razao + 1.41 - 1.5 * h_norm
    k2 = 0.15 * razao + 5.50 - 4.0 * h_norm
    return float(k1), float(k2)


def rg_schwarz(rho_eq: float, geom: GeometriaMalha) -> float:
    """
    Resistência da malha por Schwarz (IEEE 80 §14.3).

    Combina contribuição dos cabos horizontais (R1), das hastes verticais (R2)
    e a resistência mútua entre eles (Rm).

    Args:
        rho_eq: resistividade equivalente do solo [Ω·m]
        geom  : geometria da malha

    Returns:
        Rg [Ω]
    """
    Lc = geom.comprimento_cabos_m()
    Lr = geom.haste_comprimento_m
    n = max(geom.num_hastes, 1)
    A = geom.area_m2
    h = geom.profundidade_m
    a = geom.diametro_cabo_m / 2.0  # raio do cabo
    a_linha = np.sqrt(a * 2.0 * h)  # raio equivalente para cabo enterrado
    d_haste = geom.haste_diametro_mm / 1000.0  # diâmetro em metros

    k1, k2 = _schwarz_k1_k2(geom)

    # R1 - cabos horizontais (eq. 53)
    R1 = (rho_eq / (np.pi * Lc)) * (
        np.log(2.0 * Lc / a_linha) + k1 * Lc / np.sqrt(A) - k2
    )

    # R2 - hastes verticais (eq. 56)
    R2 = (rho_eq / (2.0 * np.pi * n * Lr)) * (
        np.log(8.0 * Lr / d_haste) - 1.0
        + 2.0 * k1 * Lr * (np.sqrt(n) - 1.0) ** 2 / np.sqrt(A)
    )

    # Rm - resistência mútua (eq. 57)
    Rm = (rho_eq / (np.pi * Lc)) * (
        np.log(2.0 * Lc / Lr) + k1 * Lc / np.sqrt(A) - k2 + 1.0
    )

    # Rg combinada (eq. 58)
    Rg = (R1 * R2 - Rm ** 2) / (R1 + R2 - 2.0 * Rm)
    return float(Rg)


# ============================================================
# TENSÕES Em e Es (IEEE 80 §16.5)
# ============================================================

def _fatores_tensao_malha(geom: GeometriaMalha) -> Tuple[float, float, float, float, float]:
    """
    Calcula os fatores Km, Ki, Ks, Lm, Ls para tensões de malha e passo.

    Returns:
        (Km, Ki, Ks, Lm, Ls)
    """
    L = max(geom.largura_m, geom.comprimento_m)
    W = min(geom.largura_m, geom.comprimento_m)
    A = geom.area_m2
    h = geom.profundidade_m
    D = geom.espac_malha_m
    d = geom.diametro_cabo_m
    Lr = geom.haste_comprimento_m
    n_hastes = geom.num_hastes
    Lc = geom.comprimento_cabos_m()
    Lp = geom.perimetro_m

    # n - fator geométrico (eq. 85)
    na = 2.0 * Lc / Lp
    nb = np.sqrt(Lp / (4.0 * np.sqrt(A)))
    Dm = np.sqrt(L ** 2 + W ** 2)  # maior distância na malha
    nc = (L * W / A) ** (0.7 * A / (L * W))  # = 1 para retangular
    nd = Dm / np.sqrt(L ** 2 + W ** 2)        # = 1 sempre (mantido p/ clareza)
    n = na * nb * nc * nd

    # Fator de irregularidade Ki (eq. 89)
    Ki = 0.644 + 0.148 * n

    # Kii (eq. 83) - para hastes em geometria com hastes nos cantos = 1
    if n_hastes >= 4:
        Kii = 1.0
    else:
        Kii = 1.0 / (2.0 * n) ** (2.0 / n)

    # Kh (eq. 84)
    Kh = np.sqrt(1.0 + h)

    # Km (eq. 81)
    Km = (1.0 / (2.0 * np.pi)) * (
        np.log(
            D ** 2 / (16.0 * h * d)
            + (D + 2.0 * h) ** 2 / (8.0 * D * d)
            - h / (4.0 * d)
        )
        + (Kii / Kh) * np.log(8.0 / (np.pi * (2.0 * n - 1.0)))
    )

    # Ks (eq. 92)
    Ks = (1.0 / np.pi) * (
        1.0 / (2.0 * h)
        + 1.0 / (D + h)
        + (1.0 / D) * (1.0 - 0.5 ** (n - 2.0))
    )

    # Lm e Ls - comprimentos efetivos (eqs. 88, 90)
    if n_hastes > 0:
        # Com hastes (eq. 88)
        Lm = Lc + (1.55 + 1.22 * (Lr / np.sqrt(L ** 2 + W ** 2))) * n_hastes * Lr
    else:
        Lm = Lc

    Ls = 0.75 * Lc + 0.85 * n_hastes * Lr  # eq. 93

    return float(Km), float(Ki), float(Ks), float(Lm), float(Ls)


def tensao_malha_em(rho_eq: float, ig_a: float, geom: GeometriaMalha) -> float:
    """Em = ρ·Km·Ki·IG / Lm   (IEEE 80 eq. 80)"""
    Km, Ki, _, Lm, _ = _fatores_tensao_malha(geom)
    return float(rho_eq * Km * Ki * ig_a / Lm)


def tensao_passo_es(rho_eq: float, ig_a: float, geom: GeometriaMalha) -> float:
    """Es = ρ·Ks·Ki·IG / Ls   (IEEE 80 eq. 92)"""
    _, Ki, Ks, _, Ls = _fatores_tensao_malha(geom)
    return float(rho_eq * Ks * Ki * ig_a / Ls)


# ============================================================
# CÁLCULO INTEGRADO
# ============================================================

def calcula_resistencia_e_tensoes(
    rho_eq: float,
    ig_a: float,
    geom: GeometriaMalha,
) -> ResultadoResistencia:
    """
    Cálculo completo de Rg, GPR, Em e Es.

    Args:
        rho_eq: ρ equivalente do solo [Ω·m]
        ig_a  : corrente de malha IG [A]
        geom  : geometria da malha

    Returns:
        ResultadoResistencia com todos os valores intermediários e finais.
    """
    rg_s = rg_sverak(rho_eq, geom)
    rg_sw = rg_schwarz(rho_eq, geom)
    # Adota Schwarz por ser mais preciso (considera hastes)
    rg = rg_sw

    Km, Ki, Ks, Lm, Ls = _fatores_tensao_malha(geom)
    Lc = geom.comprimento_cabos_m()
    Lt = geom.comprimento_total_lt()

    em = rho_eq * Km * Ki * ig_a / Lm
    es = rho_eq * Ks * Ki * ig_a / Ls
    gpr = rg * ig_a

    # n geométrico para registro
    L = max(geom.largura_m, geom.comprimento_m)
    W = min(geom.largura_m, geom.comprimento_m)
    A = geom.area_m2
    Lp = geom.perimetro_m
    na = 2.0 * Lc / Lp
    nb = np.sqrt(Lp / (4.0 * np.sqrt(A)))
    n = na * nb

    return ResultadoResistencia(
        rg_sverak_ohm=rg_s,
        rg_schwarz_ohm=rg_sw,
        rg_adotado_ohm=rg,
        em_v=em,
        es_v=es,
        gpr_v=gpr,
        Lc_m=Lc,
        Lt_m=Lt,
        Lm_m=Lm,
        Ls_m=Ls,
        Km=Km,
        Ki=Ki,
        Ks=Ks,
        n_geometrico=float(n),
    )
