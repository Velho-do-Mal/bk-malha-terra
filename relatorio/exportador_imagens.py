"""
relatorio/exportador_imagens.py
================================

Conversão de figuras Plotly em PNG para inserir no relatório Word.

Estratégia em camadas:
1. Tentar Plotly + kaleido (qualidade alta, idêntico ao app)
2. Se falhar, recriar o gráfico em matplotlib (qualidade um pouco menor,
   mas sem dependência externa)
3. Se também falhar, retornar None e o relatório marca [Figura ausente]

Por que esse fallback existe:
- kaleido novo (>=1.0) precisa Chrome instalado
- Em ambientes Windows com Python 3.13, kaleido 0.2.1 às vezes falha
- matplotlib é robusto e roda em qualquer lugar
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================
# 1. EXPORTAÇÃO VIA PLOTLY + KALEIDO (preferencial)
# ============================================================

def _exporta_plotly(fig, width: int = 900, height: int = 500,
                     scale: int = 2) -> Optional[bytes]:
    """
    Tenta exportar figura Plotly como PNG via kaleido.

    Returns:
        Bytes do PNG ou None se falhar.
    """
    try:
        return fig.to_image(format="png", width=width, height=height, scale=scale)
    except Exception as e:
        logger.warning(f"Falha exportar Plotly via kaleido: {e}")
        return None


# ============================================================
# 2. FALLBACK COM MATPLOTLIB (recriação simplificada)
# ============================================================

def _curva_wenner_mpl(medicoes, solo) -> bytes:
    """Recria curva de Wenner em matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    espac = [m.espacamento_m for m in medicoes]
    rho_med = [m.rho_aparente for m in medicoes]

    # Curva teórica
    from core.solo import gera_curva_teorica
    a_curva, rho_curva = gera_curva_teorica(
        solo, a_min=min(espac) * 0.5, a_max=max(espac) * 2.0, n_pontos=200,
    )

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    ax.semilogx(a_curva, rho_curva, color="#1F4E79", linewidth=2,
                label=f"Modelo 2 camadas (RMS {solo.erro_rms:.2f}%)")
    ax.scatter(espac, rho_med, color="#E67E22", s=80, edgecolor="black",
               zorder=5, label="Medições Wenner")
    ax.axhline(solo.rho1, color="gray", linestyle=":",
               label=f"ρ₁ = {solo.rho1:.0f} Ω·m")
    ax.axhline(solo.rho2, color="gray", linestyle="--",
               label=f"ρ₂ = {solo.rho2:.0f} Ω·m")
    ax.set_xlabel("Espaçamento entre eletrodos a [m]")
    ax.set_ylabel("Resistividade aparente ρ_a [Ω·m]")
    ax.set_title("Estratificação do Solo - Método de Wenner (NBR 7117)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _planta_malha_mpl(largura: float, comprimento: float,
                       cabos: list, hastes: list,
                       titulo: str = "Planta da Malha") -> bytes:
    """Recria planta da malha em matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=(9, 7), dpi=150)

    # Contorno
    rect = Rectangle((0, 0), comprimento, largura, fill=False,
                     edgecolor="black", linewidth=2.5)
    ax.add_patch(rect)

    # Cabos
    for x1, y1, x2, y2 in cabos:
        ax.plot([x1, x2], [y1, y2], color="#1F4E79", linewidth=1.2)

    # Hastes por prioridade
    cores = {1: ("#C0392B", "D"), 2: ("#E67E22", "s"),
             3: ("#3FAE2A", "o"), 4: ("purple", "*")}
    nomes = {1: "Cantos", 2: "Bordas", 3: "Interior", 4: "Crítico"}
    for prio, (cor, marker) in cores.items():
        do_grupo = [h for h in hastes if h.prioridade == prio]
        if do_grupo:
            xs = [h.x for h in do_grupo]
            ys = [h.y for h in do_grupo]
            ax.scatter(xs, ys, c=cor, marker=marker, s=120,
                       edgecolor="black", linewidth=1, zorder=10,
                       label=f"Hastes - {nomes[prio]}")

    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(titulo)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.9)
    margem = max(largura, comprimento) * 0.05
    ax.set_xlim(-margem, comprimento + margem)
    ax.set_ylim(-margem, largura + margem)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _verificacao_mpl(em_v: float, es_v: float,
                      etoque_adm: float, epasso_adm: float) -> bytes:
    """Recria gráfico de verificação em matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    cat = ["Tensão de toque", "Tensão de passo"]
    calc = [em_v, es_v]
    adm = [etoque_adm, epasso_adm]
    cores_calc = [
        "#C0392B" if em_v > etoque_adm else "#3FAE2A",
        "#C0392B" if es_v > epasso_adm else "#3FAE2A",
    ]

    x = np.arange(len(cat))
    largura = 0.35
    bars1 = ax.bar(x - largura/2, adm, largura, label="Admissível",
                   color="lightgray", edgecolor="black")
    bars2 = ax.bar(x + largura/2, calc, largura, label="Calculado",
                   color=cores_calc, edgecolor="black")

    for bar, valor in zip(bars1, adm):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{valor:.0f} V", ha="center", va="bottom", fontsize=10)
    for bar, valor in zip(bars2, calc):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{valor:.0f} V", ha="center", va="bottom", fontsize=10,
                fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cat)
    ax.set_ylabel("Tensão [V]")
    ax.set_title("Verificação - Calculado vs Admissível (IEEE 80)")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _mapa_tensao_mpl(largura: float, comprimento: float,
                      em_v: float, etoque_adm: float) -> bytes:
    """Recria mapa de tensão em matplotlib (2D contour)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = 60
    x = np.linspace(-comprimento * 0.2, comprimento * 1.2, n)
    y = np.linspace(-largura * 0.2, largura * 1.2, n)
    X, Y = np.meshgrid(x, y)
    cx, cy = comprimento / 2, largura / 2
    dist_centro = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    dx = np.maximum(np.maximum(-X, X - comprimento), 0)
    dy = np.maximum(np.maximum(-Y, Y - largura), 0)
    dist_borda = np.sqrt(dx ** 2 + dy ** 2)
    dentro = (X >= 0) & (X <= comprimento) & (Y >= 0) & (Y <= largura)

    Rmax = np.sqrt(cx ** 2 + cy ** 2)
    dentro_t = em_v * (1 - np.cos(np.pi * dist_centro / Rmax) ** 2) * 0.5 + em_v * 0.3
    fora_t = em_v * np.exp(-dist_borda / (max(comprimento, largura) * 0.3))
    Z = np.where(dentro, dentro_t, fora_t)

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    cs = ax.contourf(X, Y, Z, levels=20, cmap="RdYlGn_r")
    ax.contour(X, Y, Z, levels=[etoque_adm], colors="blue",
               linewidths=2, linestyles="--")
    plt.colorbar(cs, ax=ax, label="Tensão de toque [V]")

    # Contorno SE
    ax.plot([0, comprimento, comprimento, 0, 0],
            [0, 0, largura, largura, 0], "k-", linewidth=2)

    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(f"Distribuição da Tensão de Toque (linha azul = "
                  f"Etoque admissível {etoque_adm:.0f} V)")
    ax.set_aspect("equal")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ============================================================
# API PÚBLICA - tenta Plotly, fallback matplotlib
# ============================================================

def exporta_curva_wenner(fig_plotly, medicoes, solo) -> Optional[bytes]:
    """Exporta curva Wenner. Tenta Plotly, fallback matplotlib."""
    img = _exporta_plotly(fig_plotly, 900, 500)
    if img:
        return img
    try:
        return _curva_wenner_mpl(medicoes, solo)
    except Exception as e:
        logger.error(f"Falha matplotlib curva Wenner: {e}")
        return None


def exporta_planta_malha(fig_plotly, largura, comprimento, cabos,
                          hastes, titulo) -> Optional[bytes]:
    """Exporta planta da malha. Tenta Plotly, fallback matplotlib."""
    img = _exporta_plotly(fig_plotly, 900, 700)
    if img:
        return img
    try:
        return _planta_malha_mpl(largura, comprimento, cabos, hastes, titulo)
    except Exception as e:
        logger.error(f"Falha matplotlib planta: {e}")
        return None


def exporta_verificacao(fig_plotly, em_v, es_v,
                         etoque_adm, epasso_adm) -> Optional[bytes]:
    """Exporta gráfico de verificação."""
    img = _exporta_plotly(fig_plotly, 900, 500)
    if img:
        return img
    try:
        return _verificacao_mpl(em_v, es_v, etoque_adm, epasso_adm)
    except Exception as e:
        logger.error(f"Falha matplotlib verificação: {e}")
        return None


def exporta_mapa_tensao(fig_plotly, largura, comprimento,
                         em_v, etoque_adm) -> Optional[bytes]:
    """Exporta mapa 3D de tensão (em 2D no fallback)."""
    img = _exporta_plotly(fig_plotly, 900, 600)
    if img:
        return img
    try:
        return _mapa_tensao_mpl(largura, comprimento, em_v, etoque_adm)
    except Exception as e:
        logger.error(f"Falha matplotlib mapa: {e}")
        return None
