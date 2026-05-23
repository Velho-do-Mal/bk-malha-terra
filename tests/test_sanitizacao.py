"""
tests/test_sanitizacao.py
=========================

Testa que tipos NumPy são convertidos para tipos Python nativos antes
de salvar no banco. Cobre o bug de "Object of type bool is not JSON
serializable" que aparecia ao salvar np.False_ em campos JSON.
"""

import json
from dataclasses import dataclass

import numpy as np
import pytest

from data.sanitizacao import sanitiza_kwargs, to_python


class TestToPython:
    """Conversão de tipos NumPy individuais para Python nativo."""

    def test_np_bool(self):
        assert to_python(np.True_) is True
        assert to_python(np.False_) is False

    def test_np_int(self):
        valor = to_python(np.int64(42))
        assert valor == 42
        assert isinstance(valor, int)
        assert not isinstance(valor, np.integer)

    def test_np_float(self):
        valor = to_python(np.float64(3.14))
        assert valor == 3.14
        assert isinstance(valor, float)
        # O importante é que seja JSON-serializável
        json.dumps(valor)  # não deve lançar

    def test_np_array(self):
        arr = np.array([1.5, 2.5, 3.5])
        valor = to_python(arr)
        assert valor == [1.5, 2.5, 3.5]
        assert all(isinstance(v, float) for v in valor)

    def test_python_nativo_passa_inalterado(self):
        assert to_python(True) is True
        assert to_python(42) == 42
        assert to_python(3.14) == 3.14
        assert to_python("texto") == "texto"
        assert to_python(None) is None


class TestColecoes:
    """Conversão recursiva de dicts e listas com NumPy."""

    def test_dict_com_np(self):
        d = {
            "atende": np.False_,
            "valor": np.float64(1.5),
            "n": np.int64(10),
        }
        r = to_python(d)
        assert r == {"atende": False, "valor": 1.5, "n": 10}
        assert isinstance(r["atende"], bool)
        assert isinstance(r["valor"], float)
        assert isinstance(r["n"], int)

    def test_dict_aninhado(self):
        d = {
            "outer": {
                "inner": np.float64(2.0),
                "lista": [np.True_, np.False_],
            }
        }
        r = to_python(d)
        assert r == {"outer": {"inner": 2.0, "lista": [True, False]}}

    def test_lista_com_np(self):
        lst = [np.float64(1.0), np.True_, "texto", None]
        r = to_python(lst)
        assert r == [1.0, True, "texto", None]


class TestSerializacaoJSON:
    """Garante que valores sanitizados são JSON-serializáveis."""

    def test_np_quebra_json_padrao(self):
        """Confirma o bug: np.bool_ não é serializável por padrão."""
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.dumps({"valor": np.False_})

    def test_apos_sanitizar_serializa_ok(self):
        """Após to_python, JSON serializa sem erro."""
        d = {
            "atende": np.False_,
            "valor": np.float64(1.5),
            "lista": [np.True_, np.float64(2.0)],
            "nested": {"x": np.int64(5)},
        }
        sanitizado = to_python(d)
        # Não deve lançar exceção
        s = json.dumps(sanitizado)
        # Pode ser desserializado de volta
        d2 = json.loads(s)
        assert d2["atende"] is False
        assert d2["valor"] == 1.5
        assert d2["lista"] == [True, 2.0]
        assert d2["nested"]["x"] == 5


class TestSanitizaKwargs:
    """Helper para sanitizar kwargs antes de chamar repository."""

    def test_kwargs_simples(self):
        r = sanitiza_kwargs(
            atende_toque=np.False_,
            margem_pct=np.float64(-25.5),
            num_hastes=np.int64(40),
        )
        assert r["atende_toque"] is False
        assert r["margem_pct"] == -25.5
        assert r["num_hastes"] == 40
        assert isinstance(r["num_hastes"], int)

    def test_kwargs_com_dict_aninhado(self):
        r = sanitiza_kwargs(
            json_completo={
                "historico": [
                    {"n": np.int64(4), "atende": np.False_},
                    {"n": np.int64(8), "atende": np.True_},
                ],
            },
        )
        # Deve ser serializável após sanitização
        s = json.dumps(r["json_completo"])
        d = json.loads(s)
        assert d["historico"][0]["atende"] is False
        assert d["historico"][1]["atende"] is True


class TestCenarioReal:
    """Cenário que reproduz exatamente o erro do app."""

    def test_caso_app_real(self):
        """
        Reproduz os parâmetros que estavam quebrando o app.py antes
        da correção (do erro reportado pelo Velho).
        """
        campos = {
            "atende_passo": np.False_,
            "atende_toque": np.False_,
            "atende_geral": np.False_,
            "bitola_adotada_mm2": 95.0,
            "h1_m": np.float64(1.295816),
            "margem_toque_pct": np.float64(-489.48),
            "rho1_ohm_m": np.float64(317.289),
            "num_hastes": np.int64(120),
            "bitola_calculada_mm2": np.float64(79.78),
            "json_completo": {
                "historico_iteracao": [
                    {
                        "iteracao": 1,
                        "n_hastes": 4,
                        "rg_ohm": np.float64(3.5),
                        "atende": np.False_,
                    },
                ],
            },
        }
        r = sanitiza_kwargs(**campos)

        # Tudo deve ser JSON-serializável
        json.dumps(r)  # não deve lançar

        # Tipos corretos
        assert isinstance(r["atende_toque"], bool)
        assert isinstance(r["margem_toque_pct"], float)
        assert isinstance(r["num_hastes"], int)
        assert isinstance(r["json_completo"], dict)
        assert isinstance(
            r["json_completo"]["historico_iteracao"][0]["rg_ohm"], float
        )
