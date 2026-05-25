"""
data/sanitizacao.py
===================

Convers�o de tipos NumPy/dataclasses para tipos Python nativos
serializ�veis em JSON e compat�veis com SQLAlchemy.

NumPy retorna tipos como np.float64, np.int64, np.bool_ que n�o s�o
serializ�veis pelo m�dulo json padr�o e podem causar problemas em
algumas drivers de banco. Esta fun��o normaliza tudo recursivamente.
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
        - np.bool_ ? bool
        - np.integer ? int
        - np.floating ? float
        - np.ndarray ? list (recursivo)
        - dataclass ? dict (recursivo)
        - dict, list, tuple, set ? recursivo
        - None, str, int, float, bool ? mant�m

    Args:
        valor: valor de qualquer tipo

    Returns:
        Valor com tipos Python nativos.
    """
    # Tipos Python nativos b�sicos
    if valor is None or isinstance(valor, (str, bool, int, float)):
        # Cuidado: bool � subclasse de int, ordem importa
        return valor

    # NumPy
    if HAS_NUMPY:
        if isinstance(valor, np.bool_):
            return bool(valor)
        if isinstance(valor, np.integer):
            return int(valor)
        if isinstance(valor, np.floating):
            return float(valor)
        if isinstance(valor, np.ndarray):
            return [to_python(v) for v in valor.tolist()]

    # Dataclasses
    if is_dataclass(valor) and not isinstance(valor, type):
        return {k: to_python(v) for k, v in asdict(valor).items()}

    # Cole��es
    if isinstance(valor, dict):
        return {str(k): to_python(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [to_python(v) for v in valor]

    # Fallback: tenta str
    return str(valor)


def sanitiza_kwargs(kwargs: dict) -> dict:
    """
    Aplica `to_python` em todos os valores de um dict de kwargs.

    �til antes de chamar `repository.salva_resultado(**kwargs)` quando
    os valores podem vir de c�lculos com NumPy.
    """
    return {k: to_python(v) for k, v in kwargs.items()}
