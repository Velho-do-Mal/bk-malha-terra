"""
core/condutor.py
================

Dimensionamento da seção mínima do condutor da malha de aterramento
conforme IEEE Std 80-2013, §11 (Selection of conductors and connections).

Equação fundamental — Sverak (eq. 37 IEEE 80):

                       √( TCAP·1e-4 / (tc·αr·ρr) ) · √( ln((Tm-Ta)·αr+1)/((Tk0+Ta)·αr) )
    Amm² = I_kA · ────────────────────────────────────────────────────────────────────────
                                                  1

Reorganizando para forma usual:

    A [mm²] = I [A] · √( tc·αr·ρr·1e4 / (TCAP · ln( (K0+Tm)/(K0+Ta) )) )

onde:
    I   = corrente RMS de falta [A]   (assimétrica para período tc)
    tc  = duração da corrente [s]
    αr  = coef. térmico de resistividade a temperatura de referência (Tr)
    ρr  = resistividade do condutor a Tr [μΩ·cm]
    K0  = 1/α0 - Tr [°C]
    Tm  = temperatura máxima admissível [°C]
    Ta  = temperatura ambiente [°C]
    TCAP = capacidade térmica por volume [J/(cm³·°C)]
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


# ============================================================
# Propriedades dos materiais (Tabela 1 IEEE 80-2013)
# ============================================================

class Material(str, Enum):
    """Materiais usuais para condutor de malha."""
    COBRE_NU              = "cobre_nu"           # Soft-drawn 100% IACS
    COBRE_COMERCIAL       = "cobre_comercial"    # Hard-drawn 97% IACS
    COPPERWELD_40         = "copperweld_40"      # 40% IACS
    COPPERWELD_30         = "copperweld_30"      # 30% IACS
    ALUMINIO_5005         = "aluminio_5005"
    ACO_GALVANIZADO       = "aco_galvanizado"


@dataclass(frozen=True)
class PropriedadesMaterial:
    """
    Propriedades térmicas de um material para Sverak.
    Valores da Tabela 1 IEEE 80-2013.

    Atributos:
        nome   : descritivo
        alpha_r: coef. térmico de resistividade a Tr=20°C [1/°C]
        K0     : 1/α0 [°C], onde α0 é coef. a 0°C
        Tm     : temperatura máxima de fusão/conexão [°C]
        rho_r  : resistividade a 20°C [μΩ·cm]
        TCAP   : capacidade térmica [J/(cm³·°C)]
    """
    nome: str
    alpha_r: float
    K0: float
    Tm: float
    rho_r: float
    TCAP: float


# Tabela 1 IEEE 80-2013 (valores exatos da norma)
PROPRIEDADES = {
    Material.COBRE_NU: PropriedadesMaterial(
        nome="Cobre nu (soft-drawn 100% IACS)",
        alpha_r=0.00393, K0=234.0, Tm=1083.0,
        rho_r=1.72, TCAP=3.4,
    ),
    Material.COBRE_COMERCIAL: PropriedadesMaterial(
        nome="Cobre comercial (hard-drawn 97% IACS)",
        alpha_r=0.00381, K0=242.0, Tm=1084.0,
        rho_r=1.78, TCAP=3.4,
    ),
    Material.COPPERWELD_40: PropriedadesMaterial(
        nome="Copperweld 40% IACS",
        alpha_r=0.00378, K0=245.0, Tm=1084.0,
        rho_r=4.40, TCAP=3.85,
    ),
    Material.COPPERWELD_30: PropriedadesMaterial(
        nome="Copperweld 30% IACS",
        alpha_r=0.00378, K0=245.0, Tm=1084.0,
        rho_r=5.86, TCAP=3.85,
    ),
    Material.ALUMINIO_5005: PropriedadesMaterial(
        nome="Alumínio liga 5005",
        alpha_r=0.00353, K0=263.0, Tm=660.0,
        rho_r=3.22, TCAP=2.5,
    ),
    Material.ACO_GALVANIZADO: PropriedadesMaterial(
        nome="Aço galvanizado",
        alpha_r=0.00320, K0=293.0, Tm=419.0,
        rho_r=20.10, TCAP=3.93,
    ),
}


# Bitolas comerciais [mm²] (cobre nu - padrão BR)
BITOLAS_COMERCIAIS = [16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500]


# ============================================================
# DATACLASS DE RESULTADO
# ============================================================

@dataclass
class ResultadoCondutor:
    """Resultado do dimensionamento do condutor."""
    bitola_calculada_mm2: float
    bitola_adotada_mm2: float
    bitola_minima_pratica_mm2: float
    material: str
    temperatura_max_c: float
    temperatura_amb_c: float
    corrente_a: float
    tempo_s: float
    observacoes: list[str]


# ============================================================
# FUNÇÕES PRINCIPAIS
# ============================================================

def secao_minima_sverak(
    corrente_a: float,
    tempo_s: float,
    material: Material = Material.COBRE_NU,
    temperatura_max_c: float | None = None,
    temperatura_amb_c: float = 40.0,
) -> float:
    """
    Calcula a seção mínima do condutor pela equação de Sverak (IEEE 80 eq. 37).

    Args:
        corrente_a       : corrente RMS de falta em A (use IG já calculada)
        tempo_s          : duração da corrente em s (tempo de eliminação)
        material         : material do condutor (enum Material)
        temperatura_max_c: temperatura máxima admissível [°C]. Se None,
                           usa Tm do material (fusão). Recomenda-se valores
                           menores conforme tipo de conexão (ver notas).
        temperatura_amb_c: temperatura ambiente [°C], default 40°C.

    Returns:
        Seção mínima em mm² (não arredondada).

    Notas sobre Tm (Tabela 2 IEEE 80-2013):
        - Conexões soldadas (exotérmica)..............: Tm = 1083°C (cobre)
        - Conexões parafusadas........................: Tm = 250 °C
        - Conexões prensadas (compressão).............: Tm = 450 °C
        Recomendação BK: 250°C para conexões parafusadas (conservador).
    """
    if corrente_a <= 0 or tempo_s <= 0:
        raise ValueError("Corrente e tempo devem ser positivos.")

    prop = PROPRIEDADES[material]

    # Tm padrão = fusão; mas é mais correto usar limite da conexão
    Tm = temperatura_max_c if temperatura_max_c is not None else prop.Tm
    Ta = temperatura_amb_c

    if Tm <= Ta:
        raise ValueError(
            f"Tm ({Tm}°C) deve ser maior que Ta ({Ta}°C)."
        )

    # Equação 37 IEEE 80-2013 reorganizada para A em mm²
    # A [mm²] = I[A] · √( tc·αr·ρr·1e4 / (TCAP · ln( (K0+Tm)/(K0+Ta) )) ) / 1e3 ·... 
    # Forma final consagrada:
    #
    #            I [kA]
    # A [mm²] = ───────── · √(tc) · F_material(Tm, Ta)
    #
    # onde F = √( ρr · 1e4 / (TCAP · αr · ln((K0+Tm)/(K0+Ta))) ) ... 
    #
    # Implementação direta da forma da norma:
    I_kA = corrente_a / 1000.0

    log_term = np.log((prop.K0 + Tm) / (prop.K0 + Ta))
    fator = np.sqrt(
        (prop.TCAP * 1e-4)
        / (tempo_s * prop.alpha_r * prop.rho_r)
        * log_term
    )

    # Eq. 37: A_mm² = I_kA / fator * conversão
    # Com TCAP em J/(cm³·°C), tc em s, ρr em μΩ·cm:
    # A [kcmil] = I_kA · √(...)
    # 1 kcmil = 0.5067 mm²
    # Mas a forma SI direta:
    A_mm2 = I_kA / fator
    # Conversão para mm² (a forma SI direta resulta em mm²)
    return float(A_mm2)


def bitola_comercial(secao_calculada_mm2: float,
                      minimo_pratico_mm2: float = 50.0) -> float:
    """
    Seleciona a bitola comercial imediatamente superior à calculada,
    respeitando um mínimo prático.

    Args:
        secao_calculada_mm2: seção calculada por Sverak
        minimo_pratico_mm2 : mínimo por robustez mecânica (BK = 50 mm²)

    Returns:
        Bitola comercial [mm²]
    """
    minimo = max(secao_calculada_mm2, minimo_pratico_mm2)
    for b in BITOLAS_COMERCIAIS:
        if b >= minimo:
            return float(b)
    return float(BITOLAS_COMERCIAIS[-1])


def dimensiona_condutor(
    corrente_a: float,
    tempo_s: float,
    material: Material = Material.COBRE_NU,
    temperatura_max_c: float = 250.0,  # default conservador (parafusado)
    temperatura_amb_c: float = 40.0,
    minimo_pratico_mm2: float = 50.0,
) -> ResultadoCondutor:
    """
    Dimensionamento completo do condutor com observações.

    Args:
        corrente_a        : corrente RMS [A]
        tempo_s           : duração [s]
        material          : Material enum
        temperatura_max_c : Tm conforme tipo de conexão (default 250°C)
        temperatura_amb_c : Ta [°C]
        minimo_pratico_mm2: mínimo BK por robustez mecânica

    Returns:
        ResultadoCondutor com bitolas calculada, adotada e observações.
    """
    obs = []

    A_calc = secao_minima_sverak(
        corrente_a, tempo_s, material,
        temperatura_max_c, temperatura_amb_c
    )
    A_adotada = bitola_comercial(A_calc, minimo_pratico_mm2)

    if A_calc < minimo_pratico_mm2:
        obs.append(
            f"Seção calculada ({A_calc:.1f} mm²) é inferior ao mínimo "
            f"prático adotado pela BK ({minimo_pratico_mm2} mm²). "
            "Adotado o mínimo por robustez mecânica."
        )

    if temperatura_max_c >= 1000:
        obs.append(
            "Tm próxima da fusão. Recomenda-se usar Tm=250°C "
            "(parafusada) ou 450°C (compressão) para conexões reais."
        )

    obs.append(
        f"Material: {PROPRIEDADES[material].nome}. "
        f"Conexões com Tm={temperatura_max_c}°C, Ta={temperatura_amb_c}°C."
    )

    return ResultadoCondutor(
        bitola_calculada_mm2=A_calc,
        bitola_adotada_mm2=A_adotada,
        bitola_minima_pratica_mm2=minimo_pratico_mm2,
        material=PROPRIEDADES[material].nome,
        temperatura_max_c=temperatura_max_c,
        temperatura_amb_c=temperatura_amb_c,
        corrente_a=corrente_a,
        tempo_s=tempo_s,
        observacoes=obs,
    )
