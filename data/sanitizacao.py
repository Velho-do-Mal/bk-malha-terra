"""
data/sanitizacao.py
===================

Conversão de tipos NumPy/dataclasses para tipos Python nativos
serializáveis em JSON e compatíveis com SQLAlchemy.

NumPy retorna tipos como np.float64, np.int64, np.bool_ que não são
serializáveis pelo módulo json padrão e podem causar problemas em
algumas drivers de banco. Esta função normaliza tudo recursivamente.

ATENÇÃO: np.float64 é subclasse de Python float nativo, portanto os
checks de numpy DEVEM vir ANTES do check genérico isinstance(..., float).
"""

from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:  # pragma: no cover
    HAS_NUMPY = False

def to_python(valor: Any) -> Any:
    """
    Converte recursivamente um valor para tipos Python nativos.

    Trata:
    - np.bool_ → bool
    - np.integer → int
    - np.floating → float  (deve vir ANTES do check float nativo!)
    - np.ndarray → list (recursivo)
    - dataclass → dict (recursivo)
    - dict, list, tuple, set → recursivo
    - None, str, int, float, bool → mantém

    Args:
        valor: valor de qualquer tipo

    Returns:
        Valor com tipos Python nativos.
    """
    # NumPy PRIMEIRO — np.float64 é subclasse de float, np.bool_ de bool,
    # np.int_ de int. Se checarmos os nativos antes, os tipos NumPy passam
    # como "nativos" e chegam ao banco ainda como np.float64 etc.
    if HAS_NUMPY:
        if isinstance(valor, np.bool_):
            return bool(valor)
        if isinstance(valor, np.integer):
            return int(valor)
        if isinstance(valor, np.floating):
            return float(valor)
        if isinstance(valor, np.ndarray):
            return [to_python(v) for v in valor.tolist()]

    # Tipos Python nativos básicos (após numpy para evitar falso match)
    if valor is None or isinstance(valor, (str, bool, int, float)):
        return valor

    # Dataclasses
    if is_dataclass(valor) and not isinstance(valor, type):
        return {k: to_python(v) for k, v in asdict(valor).items()}

    # Coleções
    if isinstance(valor, dict):
        return {str(k): to_python(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [to_python(v) for v in valor]

    # Fallback: tenta str
    return str(valor)

def sanitiza_kwargs(**kwargs: Any) -> dict:
    """
    Aplica `to_python` em todos os valores de um dict de kwargs.

    Útil antes de chamar `repository.salva_resultado(**kwargs)` quando
    os valores podem vir de cálculos com NumPy.
    """
    return {k: to_python(v) for k, v in kwargs.items()}
