"""
data/sanitizacao.py
===================

Conversão de tipos NumPy para tipos Python nativos antes de salvar no banco.

CORREÇÃO CRÍTICA:
    np.float64 é subclasse de float em Python, então a verificação
    isinstance(valor, float) retorna True para np.float64 sem converter.
    A checagem de tipos NumPy deve vir ANTES da checagem de float nativo.
"""

from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def to_python(valor: Any) -> Any:
    """
    Converte recursivamente para tipos Python nativos.

    IMPORTANTE: NumPy vem ANTES de float/int/bool
    porque np.float64 é subclasse de float e passaria
    sem conversão se float viesse primeiro.
    """
    if valor is None:
        return None

    # ── NumPy primeiro (antes de float/int/bool nativos) ──────────────────
    if HAS_NUMPY:
        if isinstance(valor, np.bool_):
            return bool(valor)
        if isinstance(valor, np.integer):
            return int(valor)
        if isinstance(valor, np.floating):
            return float(valor)
        if isinstance(valor, np.ndarray):
            return [to_python(v) for v in valor.tolist()]

    # ── Tipos Python nativos (após NumPy) ─────────────────────────────────
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return valor
    if isinstance(valor, str):
        return valor

    # ── Dataclasses ───────────────────────────────────────────────────────
    if is_dataclass(valor) and not isinstance(valor, type):
        return {k: to_python(v) for k, v in asdict(valor).items()}

    # ── Coleções ──────────────────────────────────────────────────────────
    if isinstance(valor, dict):
        return {str(k): to_python(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [to_python(v) for v in valor]

    # ── Fallback ──────────────────────────────────────────────────────────
    return str(valor)


def sanitiza_kwargs(campos: dict | None = None, **kwargs: Any) -> dict:
    """
    Sanitiza todos os valores de um dict para tipos Python nativos.

    Aceita dict direto ou **kwargs:
        sanitiza_kwargs(meu_dict)        → dict direto
        sanitiza_kwargs(**meu_dict)      → desempacotado
        sanitiza_kwargs(a=1, b=np.float64(2.0))
    """
    source = campos if isinstance(campos, dict) else kwargs
    return {k: to_python(v) for k, v in source.items()}
