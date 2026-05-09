"""
core/tensoes.py
===============

Tensões de toque e passo ADMISSÍVEIS conforme IEEE Std 80-2013, §8.

Critério de Dalziel (corrente suportável pelo corpo humano):

    I_corpo = k / √ts          onde k = 0.116 (50kg) ou 0.157 (70kg)

Resistência do corpo: Rb = 1000 Ω (IEEE 80 §8.3.1)

Fator de redução pela camada superficial (brita) — eq. 27 IEEE 80:

                  0.09 · (1 − ρ/ρs)
    Cs = 1 − ─────────────────────────
                    2·hs + 0.09

Tensões admissíveis (eqs. 32 e 33):

    Toque50: Etoque = (1000 + 1.5·Cs·ρs) · 0.116/√ts
    Toque70: Etoque = (1000 + 1.5·Cs·ρs) · 0.157/√ts
    Passo50: Epasso = (1000 + 6·Cs·ρs) · 0.116/√ts
    Passo70: Epasso = (1000 + 6·Cs·ρs) · 0.157/√ts
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ============================================================
# CONSTANTES
# ============================================================

# Constante de Dalziel
K_50KG = 0.116  # √A·s
K_70KG = 0.157  # √A·s

# Resistência do corpo humano (IEEE 80 §8.3.1)
RB_CORPO = 1000.0  # Ω


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class TensoesAdmissiveis:
    """Tensões de toque e passo admissíveis pelo corpo humano."""
    peso_pessoa_kg: int
    cs_brita: float
    rho_brita: float
    espessura_brita: float
    rho_solo: float
    tempo_choque_s: float
    etoque_v: float
    epasso_v: float
    observacoes: list[str]


# ============================================================
# FUNÇÕES
# ============================================================

def fator_cs(rho_solo: float, rho_brita: float, h_brita: float) -> float:
    """
    Fator de redução Cs da camada superficial (brita).
    IEEE 80-2013 eq. 27.

    Args:
        rho_solo : ρ do solo nativo (camada superior do modelo) [Ω·m]
        rho_brita: ρ da brita superficial [Ω·m]
                   - 3000 Ω·m: brita seca (default IEEE 80 / NBR 15751)
                   - 1200 Ω·m: brita molhada
                   - 5000 Ω·m: brita lavada graúda seca
        h_brita  : espessura da brita [m] (geralmente 0.10 a 0.15)

    Returns:
        Cs adimensional, no intervalo (0, 1].
        Cs = 1 quando não há brita (h_brita = 0).
    """
    if h_brita <= 0:
        return 1.0
    if rho_brita <= 0:
        raise ValueError("ρ da brita deve ser positivo.")
    if rho_solo <= 0:
        raise ValueError("ρ do solo deve ser positivo.")

    cs = 1.0 - (0.09 * (1.0 - rho_solo / rho_brita)) / (2.0 * h_brita + 0.09)
    return float(np.clip(cs, 0.0, 1.0))


def tensao_toque_admissivel(
    cs: float,
    rho_brita: float,
    tempo_s: float,
    peso_kg: int = 50,
) -> float:
    """
    Tensão de toque admissível (IEEE 80 eqs. 32-33).

        Etoque = (Rb + 1.5·Cs·ρs) · k/√ts

    Args:
        cs       : fator de redução da brita
        rho_brita: ρ da brita [Ω·m]
        tempo_s  : tempo de choque (= tempo de eliminação) [s]
        peso_kg  : 50 ou 70

    Returns:
        Etoque admissível [V]
    """
    k = K_50KG if peso_kg == 50 else K_70KG
    return (RB_CORPO + 1.5 * cs * rho_brita) * k / np.sqrt(tempo_s)


def tensao_passo_admissivel(
    cs: float,
    rho_brita: float,
    tempo_s: float,
    peso_kg: int = 50,
) -> float:
    """
    Tensão de passo admissível (IEEE 80 eqs. 30-31).

        Epasso = (Rb + 6·Cs·ρs) · k/√ts

    Args:
        cs       : fator de redução da brita
        rho_brita: ρ da brita [Ω·m]
        tempo_s  : tempo de choque [s]
        peso_kg  : 50 ou 70

    Returns:
        Epasso admissível [V]
    """
    k = K_50KG if peso_kg == 50 else K_70KG
    return (RB_CORPO + 6.0 * cs * rho_brita) * k / np.sqrt(tempo_s)


def calcula_tensoes_admissiveis(
    rho_solo: float,
    rho_brita: float,
    h_brita: float,
    tempo_s: float,
    peso_kg: int = 50,
) -> TensoesAdmissiveis:
    """
    Cálculo completo das tensões admissíveis.

    Args:
        rho_solo : ρ do solo (camada superior) [Ω·m]
        rho_brita: ρ da brita [Ω·m] (default 3000 conforme IEEE 80)
        h_brita  : espessura da brita [m]
        tempo_s  : tempo de eliminação [s]
        peso_kg  : 50 ou 70

    Returns:
        TensoesAdmissiveis com Etoque, Epasso e Cs.
    """
    if peso_kg not in (50, 70):
        raise ValueError("Peso deve ser 50 ou 70 kg.")

    cs = fator_cs(rho_solo, rho_brita, h_brita)
    etoque = tensao_toque_admissivel(cs, rho_brita, tempo_s, peso_kg)
    epasso = tensao_passo_admissivel(cs, rho_brita, tempo_s, peso_kg)

    obs = []
    if h_brita == 0:
        obs.append(
            "Sem brita superficial — Cs = 1.0. "
            "Tensões admissíveis fortemente reduzidas. "
            "Recomendado adicionar brita ≥ 100mm em SE."
        )
    elif h_brita < 0.10:
        obs.append(
            f"Brita com {h_brita*100:.0f}mm. "
            "Recomendado ≥ 100mm para máxima eficácia (IEEE 80 §11.3)."
        )

    if peso_kg == 70:
        obs.append(
            "Cálculo com peso 70kg (menos conservador). "
            "Concessionárias brasileiras geralmente exigem 50kg."
        )

    return TensoesAdmissiveis(
        peso_pessoa_kg=peso_kg,
        cs_brita=cs,
        rho_brita=rho_brita,
        espessura_brita=h_brita,
        rho_solo=rho_solo,
        tempo_choque_s=tempo_s,
        etoque_v=etoque,
        epasso_v=epasso,
        observacoes=obs,
    )
