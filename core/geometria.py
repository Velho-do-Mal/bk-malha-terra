"""
core/geometria.py
=================

Geração da geometria da malha (cabos e hastes) para visualização e relatório.

Estratégia de posicionamento das hastes (heurística IEEE 80 §16.6):

    1. Cantos da malha — onde os gradientes de tensão de passo são maiores
    2. Pontos médios das bordas — após cantos
    3. Pontos próximos a equipamentos críticos (transformadores, para-raios)
    4. Distribuição uniforme nas bordas (perímetro)
    5. Por último, no interior da malha (efeito menor)

Espaçamento mínimo entre hastes: ≥ comprimento da haste (Lr) para evitar
sobreposição de zonas de influência (NBR 15751 §6.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class PontoHaste:
    """Posição de uma haste no plano da malha (origem no canto inferior esquerdo)."""
    x: float
    y: float
    prioridade: int  # 1=canto, 2=borda, 3=interior, 4=equipamento crítico
    rotulo: str


def gera_cabos_malha(
    largura: float,
    comprimento: float,
    espac_malha: float,
    espac_juncao: float | None = None,
) -> Tuple[List[Tuple[float, float, float, float]], int, int]:
    """
    Gera as coordenadas dos cabos da malha em grade retangular.

    Args:
        largura      : W [m]
        comprimento  : L [m]
        espac_malha  : D principal [m]
        espac_juncao : D nas bordas (opcional, para malha mais densa
                       perimetral conforme prática IEEE 80 §16.6)

    Returns:
        Tupla (segmentos, n_horizontal, n_vertical):
            segmentos: lista de (x1,y1,x2,y2) [m]
            n_horizontal: nº de cabos paralelos a L
            n_vertical:   nº de cabos paralelos a W
    """
    segmentos = []

    # Cabos horizontais (paralelos ao comprimento L, variam em y)
    if espac_juncao and espac_juncao < espac_malha:
        # Bordas mais densas: 2 cabos extras nas bordas inferior e superior
        ys = [0.0, espac_juncao]
        y_atual = espac_juncao + espac_malha
        while y_atual < largura - espac_juncao:
            ys.append(y_atual)
            y_atual += espac_malha
        ys.extend([largura - espac_juncao, largura])
        ys = sorted(set(ys))
    else:
        n_h = int(np.ceil(largura / espac_malha)) + 1
        ys = list(np.linspace(0, largura, n_h))

    for y in ys:
        segmentos.append((0.0, float(y), float(comprimento), float(y)))

    # Cabos verticais (paralelos à largura W, variam em x)
    if espac_juncao and espac_juncao < espac_malha:
        xs = [0.0, espac_juncao]
        x_atual = espac_juncao + espac_malha
        while x_atual < comprimento - espac_juncao:
            xs.append(x_atual)
            x_atual += espac_malha
        xs.extend([comprimento - espac_juncao, comprimento])
        xs = sorted(set(xs))
    else:
        n_v = int(np.ceil(comprimento / espac_malha)) + 1
        xs = list(np.linspace(0, comprimento, n_v))

    for x in xs:
        segmentos.append((float(x), 0.0, float(x), float(largura)))

    return segmentos, len(ys), len(xs)


def posiciona_hastes(
    largura: float,
    comprimento: float,
    n_hastes: int,
    haste_comprimento: float,
) -> List[PontoHaste]:
    """
    Posiciona n hastes priorizando cantos → bordas → interior.

    Args:
        largura          : W [m]
        comprimento      : L [m]
        n_hastes         : nº total de hastes a posicionar
        haste_comprimento: Lr [m] (usado para garantir espaçamento mínimo)

    Returns:
        Lista de PontoHaste posicionadas.
    """
    if n_hastes <= 0:
        return []

    pontos = []
    espac_min = max(haste_comprimento, 2.0)  # mínimo 2m por prática

    # 1. Cantos (até 4)
    cantos = [
        (0.0, 0.0, "Canto SW"),
        (comprimento, 0.0, "Canto SE"),
        (comprimento, largura, "Canto NE"),
        (0.0, largura, "Canto NW"),
    ]
    for i, (x, y, rot) in enumerate(cantos):
        if len(pontos) >= n_hastes:
            return pontos
        pontos.append(PontoHaste(x=x, y=y, prioridade=1, rotulo=rot))

    # 2. Pontos médios das bordas
    meios = [
        (comprimento / 2, 0.0,         "Meio borda S"),
        (comprimento,    largura / 2,  "Meio borda E"),
        (comprimento / 2, largura,     "Meio borda N"),
        (0.0,            largura / 2,  "Meio borda W"),
    ]
    for x, y, rot in meios:
        if len(pontos) >= n_hastes:
            return pontos
        pontos.append(PontoHaste(x=x, y=y, prioridade=2, rotulo=rot))

    # 3. Distribuição uniforme nas bordas (perímetro)
    restantes = n_hastes - len(pontos)
    if restantes > 0:
        # Quantas hastes adicionais por borda
        por_borda = max(1, restantes // 4)
        for borda_idx in range(4):
            for k in range(1, por_borda + 1):
                if len(pontos) >= n_hastes:
                    return pontos
                frac = k / (por_borda + 1)
                if borda_idx == 0:    # sul
                    x, y = comprimento * frac, 0.0
                    rot = f"Borda S #{k}"
                elif borda_idx == 1:  # leste
                    x, y = comprimento, largura * frac
                    rot = f"Borda E #{k}"
                elif borda_idx == 2:  # norte
                    x, y = comprimento * frac, largura
                    rot = f"Borda N #{k}"
                else:                  # oeste
                    x, y = 0.0, largura * frac
                    rot = f"Borda W #{k}"
                # Evita sobreposição
                if not _muito_proximo(x, y, pontos, espac_min):
                    pontos.append(PontoHaste(x=x, y=y, prioridade=2, rotulo=rot))

    # 4. Interior (grid uniforme se sobrar)
    if len(pontos) < n_hastes:
        nx = int(np.sqrt(n_hastes - len(pontos))) + 1
        ny = nx
        for i in range(1, nx):
            for j in range(1, ny):
                if len(pontos) >= n_hastes:
                    return pontos
                x = comprimento * i / nx
                y = largura * j / ny
                if not _muito_proximo(x, y, pontos, espac_min):
                    pontos.append(PontoHaste(
                        x=x, y=y, prioridade=3, rotulo=f"Interior ({i},{j})"
                    ))

    return pontos[:n_hastes]


def _muito_proximo(x: float, y: float,
                   pontos: List[PontoHaste], dist_min: float) -> bool:
    """Retorna True se houver haste a menos de dist_min."""
    for p in pontos:
        if np.hypot(x - p.x, y - p.y) < dist_min:
            return True
    return False
