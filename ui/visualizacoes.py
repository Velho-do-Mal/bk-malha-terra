"""
ui/visualizacoes.py
===================

Geração de gráficos Plotly para a UI Streamlit e para o relatório Word.

Gráficos:
1. Curva Wenner: pontos medidos vs modelo Sunde ajustado
2. Planta 2D da malha (cabos + hastes posicionadas)
3. Mapa 3D da tensão de toque ao longo da SE
4. Gráfico de barras: Em vs Etoque, Es vs Epasso
5. Histórico da iteração de hastes
"""

from __future__ import annotations

from typing import List

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.geometria import PontoHaste
from core.solo import MedicaoWenner, SoloEstratificado, gera_curva_teorica


# Cores BK (azul institucional)
COR_BK_AZUL = "#1F4E79"
COR_BK_VERDE = "#3FAE2A"
COR_BK_LARANJA = "#E67E22"
COR_BK_VERMELHO = "#C0392B"


# ============================================================
# 1. CURVA WENNER
# ============================================================

def plot_curva_wenner(
    medicoes: List[MedicaoWenner],
    solo: SoloEstratificado,
) -> go.Figure:
    """
    Plota pontos medidos (Wenner) sobre a curva ajustada do modelo
    de 2 camadas. Eixo x em log para abranger 1m a 32m.
    """
    espac_med = [m.espacamento_m for m in medicoes]
    rho_med = [m.rho_aparente for m in medicoes]

    a_curva, rho_curva = gera_curva_teorica(
        solo,
        a_min=min(espac_med) * 0.5,
        a_max=max(espac_med) * 2.0,
        n_pontos=200,
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=a_curva, y=rho_curva,
        mode="lines",
        name=f"Modelo 2 camadas (erro RMS {solo.erro_rms:.2f}%)",
        line=dict(color=COR_BK_AZUL, width=3),
    ))
    fig.add_trace(go.Scatter(
        x=espac_med, y=rho_med,
        mode="markers",
        name="Medições Wenner",
        marker=dict(size=12, color=COR_BK_LARANJA, symbol="circle",
                    line=dict(color="black", width=1)),
    ))
    fig.add_hline(
        y=solo.rho1, line_dash="dot", line_color="gray",
        annotation_text=f"ρ₁ = {solo.rho1:.0f} Ω·m",
        annotation_position="top right",
    )
    fig.add_hline(
        y=solo.rho2, line_dash="dot", line_color="gray",
        annotation_text=f"ρ₂ = {solo.rho2:.0f} Ω·m",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title="Estratificação do Solo - Método de Wenner (NBR 7117)",
        xaxis=dict(
            title="Espaçamento entre eletrodos a [m]",
            type="log",
            gridcolor="lightgray",
        ),
        yaxis=dict(
            title="Resistividade aparente ρ_a [Ω·m]",
            gridcolor="lightgray",
        ),
        plot_bgcolor="white",
        legend=dict(x=0.02, y=0.02, bgcolor="rgba(255,255,255,0.8)"),
        height=450,
    )
    return fig


# ============================================================
# 2. PLANTA 2D DA MALHA
# ============================================================

def plot_planta_malha(
    largura: float,
    comprimento: float,
    cabos: list[tuple[float, float, float, float]],
    hastes: list[PontoHaste],
    titulo: str = "Planta da Malha de Aterramento",
) -> go.Figure:
    """
    Planta da malha mostrando:
        - Retângulo da SE
        - Cabos da malha (linhas)
        - Hastes (marcadores coloridos por prioridade)
    """
    fig = go.Figure()

    # Contorno da SE
    fig.add_trace(go.Scatter(
        x=[0, comprimento, comprimento, 0, 0],
        y=[0, 0, largura, largura, 0],
        mode="lines",
        name="Limite da SE",
        line=dict(color="black", width=3),
        showlegend=True,
    ))

    # Cabos da malha
    for i, (x1, y1, x2, y2) in enumerate(cabos):
        fig.add_trace(go.Scatter(
            x=[x1, x2], y=[y1, y2],
            mode="lines",
            line=dict(color=COR_BK_AZUL, width=1.5),
            showlegend=(i == 0),
            name="Cabo de cobre",
            hoverinfo="skip",
        ))

    # Hastes por prioridade
    grupos = {1: ("Hastes - cantos", COR_BK_VERMELHO, "diamond"),
              2: ("Hastes - bordas", COR_BK_LARANJA, "square"),
              3: ("Hastes - interior", COR_BK_VERDE, "circle"),
              4: ("Hastes - equip. crítico", "purple", "star")}
    for prio, (nome, cor, simbolo) in grupos.items():
        do_grupo = [h for h in hastes if h.prioridade == prio]
        if not do_grupo:
            continue
        fig.add_trace(go.Scatter(
            x=[h.x for h in do_grupo],
            y=[h.y for h in do_grupo],
            mode="markers",
            name=nome,
            marker=dict(size=14, color=cor, symbol=simbolo,
                        line=dict(color="black", width=1)),
            text=[h.rotulo for h in do_grupo],
            hovertemplate="<b>%{text}</b><br>x=%{x:.1f}m<br>y=%{y:.1f}m<extra></extra>",
        ))

    fig.update_layout(
        title=titulo,
        xaxis=dict(title="x [m] (comprimento)", scaleanchor="y", scaleratio=1,
                   gridcolor="lightgray"),
        yaxis=dict(title="y [m] (largura)", gridcolor="lightgray"),
        plot_bgcolor="white",
        height=600,
        showlegend=True,
        legend=dict(x=1.02, y=1.0),
    )
    return fig


# ============================================================
# 3. MAPA 3D DE TENSÃO DE TOQUE
# ============================================================

def calcula_mapa_tensao(
    largura: float,
    comprimento: float,
    rg_ohm: float,
    ig_a: float,
    em_v: float,
    n_pontos: int = 40,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Aproximação simplificada da distribuição de tensão de toque sobre a SE.

    Modelo: superposição de função de decaimento radial a partir das bordas.
    No centro da malha: tensão ≈ 0 (referência).
    Nas bordas: tensão máxima ≈ Em.
    Fora: decai com 1/r.

    Esta é uma aproximação visual - cálculo rigoroso requer FEM.

    Returns:
        (X, Y, Z) com Z = tensão de toque [V] em cada ponto.
    """
    x = np.linspace(-comprimento * 0.2, comprimento * 1.2, n_pontos)
    y = np.linspace(-largura * 0.2, largura * 1.2, n_pontos)
    X, Y = np.meshgrid(x, y)

    # Distância ao centro da malha
    cx, cy = comprimento / 2, largura / 2
    dist_centro = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)

    # Distância à borda mais próxima (negativo dentro)
    dx = np.maximum(np.maximum(-X, X - comprimento), 0)
    dy = np.maximum(np.maximum(-Y, Y - largura), 0)
    dist_borda = np.sqrt(dx ** 2 + dy ** 2)

    # Dentro da malha
    dentro = (X >= 0) & (X <= comprimento) & (Y >= 0) & (Y <= largura)

    # Modelo simplificado:
    # - Dentro: tensão = Em·sen(π·r/Rmax) (máxima nos cantos, mínima no centro)
    # - Fora: tensão = Em·exp(-d/L) (decai exponencialmente)
    Rmax = np.sqrt(cx ** 2 + cy ** 2)
    dentro_tensao = em_v * (1.0 - np.cos(np.pi * dist_centro / Rmax) ** 2) * 0.5 + em_v * 0.3
    fora_tensao = em_v * np.exp(-dist_borda / (max(comprimento, largura) * 0.3))

    Z = np.where(dentro, dentro_tensao, fora_tensao)
    return X, Y, Z


def plot_mapa_tensao_3d(
    largura: float,
    comprimento: float,
    rg_ohm: float,
    ig_a: float,
    em_v: float,
    etoque_adm_v: float,
    titulo: str = "Distribuição da Tensão de Toque",
) -> go.Figure:
    """Superfície 3D da tensão de toque com plano horizontal de admissível."""
    X, Y, Z = calcula_mapa_tensao(largura, comprimento, rg_ohm, ig_a, em_v)

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        colorscale=[[0, "green"], [0.5, "yellow"], [1.0, "red"]],
        cmin=0, cmax=max(em_v, etoque_adm_v) * 1.2,
        colorbar=dict(title="V"),
        name="Tensão",
    ))
    # Plano de Etoque admissível
    Z_lim = np.full_like(Z, etoque_adm_v)
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z_lim,
        colorscale=[[0, "rgba(0,150,255,0.3)"], [1, "rgba(0,150,255,0.3)"]],
        showscale=False,
        opacity=0.4,
        name=f"Etoque adm = {etoque_adm_v:.0f} V",
    ))

    fig.update_layout(
        title=titulo,
        scene=dict(
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="Tensão [V]",
            aspectmode="manual",
            aspectratio=dict(x=2, y=2, z=1),
        ),
        height=600,
    )
    return fig


# ============================================================
# 4. GRÁFICO DE VERIFICAÇÃO (BARRAS)
# ============================================================

def plot_verificacao(
    em_v: float,
    es_v: float,
    etoque_adm: float,
    epasso_adm: float,
) -> go.Figure:
    """Comparação visual: calculado vs admissível."""
    cat = ["Tensão de toque", "Tensão de passo"]
    calc = [em_v, es_v]
    adm = [etoque_adm, epasso_adm]

    cores_calc = [
        COR_BK_VERMELHO if em_v > etoque_adm else COR_BK_VERDE,
        COR_BK_VERMELHO if es_v > epasso_adm else COR_BK_VERDE,
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Admissível", x=cat, y=adm,
        marker_color="lightgray",
        text=[f"{v:.0f} V" for v in adm], textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Calculado", x=cat, y=calc,
        marker_color=cores_calc,
        text=[f"{v:.0f} V" for v in calc], textposition="outside",
    ))
    fig.update_layout(
        title="Verificação - Calculado vs Admissível (IEEE 80)",
        yaxis=dict(title="Tensão [V]", gridcolor="lightgray"),
        plot_bgcolor="white",
        barmode="group",
        height=400,
    )
    return fig


# ============================================================
# 5. HISTÓRICO DE ITERAÇÃO
# ============================================================

def plot_iteracao_hastes(historico: list[dict],
                          etoque_adm: float,
                          epasso_adm: float) -> go.Figure:
    """Mostra Em e Es em função do nº de hastes (iteração)."""
    n = [h["n_hastes"] for h in historico]
    em = [h["em_v"] for h in historico]
    es = [h["es_v"] for h in historico]

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Tensão de toque", "Tensão de passo"))

    # Toque
    fig.add_trace(go.Scatter(x=n, y=em, mode="lines+markers",
                              name="Em", line=dict(color=COR_BK_AZUL)),
                   row=1, col=1)
    fig.add_hline(y=etoque_adm, line_dash="dash", line_color="red",
                   annotation_text=f"Adm = {etoque_adm:.0f}V", row=1, col=1)

    # Passo
    fig.add_trace(go.Scatter(x=n, y=es, mode="lines+markers",
                              name="Es", line=dict(color=COR_BK_VERDE)),
                   row=1, col=2)
    fig.add_hline(y=epasso_adm, line_dash="dash", line_color="red",
                   annotation_text=f"Adm = {epasso_adm:.0f}V", row=1, col=2)

    fig.update_xaxes(title_text="Número de hastes", row=1, col=1)
    fig.update_xaxes(title_text="Número de hastes", row=1, col=2)
    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="V", row=1, col=2)
    fig.update_layout(
        title="Convergência da Iteração - Tensões vs nº de Hastes",
        height=400,
        plot_bgcolor="white",
    )
    return fig
