"""
core/corrente.py
================

Cálculo da corrente máxima de malha IG conforme IEEE Std 80-2013, §15.

Corrente de malha (eq. 70 IEEE 80):

    IG = Df · Sf · 3·I0   [A]

onde:
    Df  = fator de decremento (componente DC + AC durante tc)
    Sf  = fator de divisão de corrente (parcela que efetivamente
          escoa pela malha, e não pelos cabos para-raios/neutros)
    3I0 = corrente simétrica RMS de falta fase-terra [A]

Fator de decremento (eq. 79 IEEE 80):

    Df = √( 1 + Ta/tf · (1 − e^(−2·tf/Ta)) )

    Ta = X / (ω·R) = constante de tempo da componente DC [s]
    tf = duração da falta para fins de cálculo térmico/de tensão [s]
    ω  = 2·π·f
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class ResultadoCorrente:
    """Resultado do cálculo da corrente de malha."""
    i_falta_3i0_a: float
    sf_div_corrente: float
    cp_crescimento: float
    xr_ratio: float
    tf_s: float
    df_decremento: float
    ig_a: float
    observacoes: list[str]


# ============================================================
# FUNÇÕES
# ============================================================

def fator_decremento(xr_ratio: float, tf_s: float, freq_hz: float = 60.0) -> float:
    """
    Calcula o fator de decremento Df conforme IEEE 80 eq. 79.

    Args:
        xr_ratio: relação X/R no ponto de falta
        tf_s    : duração da falta [s]
                  Para tensões de toque/passo usar tf = tc (eliminação).
                  Para projeto térmico de condutor pode ser maior.
        freq_hz : frequência do sistema [Hz], default 60 Hz

    Returns:
        Df adimensional (≥ 1.0)

    Notas:
        - Para tf ≥ 1s, Df ≈ 1.0 (componente DC já decaiu)
        - Para X/R baixo (<5), Df ≈ 1.0
        - Para X/R alto (>30) e tf curto (<0.1s), Df pode chegar a 1.7
    """
    if xr_ratio <= 0:
        raise ValueError("X/R deve ser positivo.")
    if tf_s <= 0:
        raise ValueError("tf deve ser positivo.")

    omega = 2.0 * np.pi * freq_hz
    Ta = xr_ratio / omega  # constante de tempo DC [s]

    df = np.sqrt(1.0 + (Ta / tf_s) * (1.0 - np.exp(-2.0 * tf_s / Ta)))
    return float(df)


def corrente_malha_ig(
    i_falta_3i0_a: float,
    sf_div_corrente: float,
    xr_ratio: float,
    tf_s: float,
    cp_crescimento: float = 1.0,
    freq_hz: float = 60.0,
) -> ResultadoCorrente:
    """
    Calcula a corrente máxima de malha IG (eq. 70 IEEE 80).

    IG = Df · Sf · Cp · 3I₀

    Args:
        i_falta_3i0_a  : corrente simétrica RMS de falta 3I₀ [A]
        sf_div_corrente: fator de divisão Sf (Tabela 10 IEEE 80)
        xr_ratio       : X/R no ponto de falta
        tf_s           : duração da falta [s]
        cp_crescimento : fator de crescimento/projeção da corrente futura.
                         IEEE 80 §15 recomenda usar a máxima corrente futura.
                         Cp = 1.00 → sem crescimento previsto.
                         Cp = 1.10 → crescimento moderado (~10%).
                         Cp = 1.20 → crescimento conservador (~20%).
                         Cp = 1.30 → estudo muito conservador.
        freq_hz        : frequência [Hz]

    Returns:
        ResultadoCorrente completo.
    """
    if i_falta_3i0_a <= 0:
        raise ValueError("Corrente de falta deve ser positiva.")
    if not (0.0 < sf_div_corrente <= 1.0):
        raise ValueError("Sf deve estar entre 0 e 1.")
    if cp_crescimento < 1.0:
        raise ValueError("Cp deve ser >= 1.0 (crescimento nunca reduz a corrente de projeto).")

    df = fator_decremento(xr_ratio, tf_s, freq_hz)
    ig = df * sf_div_corrente * cp_crescimento * i_falta_3i0_a

    obs = []
    if df > 1.5:
        obs.append(
            f"Df elevado ({df:.3f}). X/R alto ({xr_ratio}) com tf curto "
            f"({tf_s}s) — verifique se proteção primária é realmente rápida."
        )
    if sf_div_corrente >= 0.95:
        obs.append(
            "Sf próximo de 1.0 — assumindo SE isolada sem cabo guarda. "
            "Confirme com Tabela 10 IEEE 80."
        )
    if tf_s < 0.1:
        obs.append(
            "tf < 100 ms — proteção rápida (relé numérico). "
            "Confirme tempo de eliminação real (proteção + abertura disjuntor)."
        )

    return ResultadoCorrente(
        i_falta_3i0_a=i_falta_3i0_a,
        sf_div_corrente=sf_div_corrente,
        cp_crescimento=cp_crescimento,
        xr_ratio=xr_ratio,
        tf_s=tf_s,
        df_decremento=df,
        ig_a=ig,
        observacoes=obs,
    )
