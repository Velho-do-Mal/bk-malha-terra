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
    n_pontos: int = 50,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Aproximação da distribuição de tensão de toque sobre a área da SE.

    Modelo físico simplificado (comportamento qualitativo, IEEE 80):
    ─────────────────────────────────────────────────────────────────
    • DENTRO da malha:
        O potencial da superfície do solo é sustentado pelos condutores
        enterrados. A tensão de toque é mínima próximo às interseções
        de condutores (≈ 0) e máxima no centro geométrico de cada célula
        da malha (≈ Em). Modelado com perfil senoidal ao quadrado a
        partir do centro da malha até a borda.

    • FORA da malha:
        O potencial de superfície decai rapidamente com a distância.
        A tensão de toque sobe e depois decresce. Modelado com decaimento
        exponencial a partir de Em na borda, comprimento característico
        L ≈ 35 % do raio equivalente da malha.

    Continuidade garantida:
        Em ambos os lados da borda, Etoque → Em (sem degrau visual).

    ⚠️  Aproximação visual — cálculo rigoroso requer FEM (CDEGS, COMSOL).

    Returns
    -------
    (X, Y, Z) grades NumPy com Z = tensão de toque aproximada [V].
    """
    # Grade com margem de 30 % além da malha em cada lado
    margin_x = comprimento * 0.30
    margin_y = largura * 0.30
    x = np.linspace(-margin_x, comprimento + margin_x, n_pontos)
    y = np.linspace(-margin_y, largura + margin_y, n_pontos)
    X, Y = np.meshgrid(x, y)

    cx, cy = comprimento / 2.0, largura / 2.0

    # Máscara dentro / fora da malha
    inside = (X >= 0.0) & (X <= comprimento) & (Y >= 0.0) & (Y <= largura)

    # ── Dentro da malha: senoidal quadrática ──────────────────────
    # Distância ao centro normalizada pela distância centro→canto
    Rmax = np.sqrt(cx**2 + cy**2)
    dist_centro = np.sqrt((X - cx)**2 + (Y - cy)**2)
    d_norm = np.minimum(dist_centro / Rmax, 1.0)
    # Etoque = 0 no centro (sobre o condutor) → Em na borda/cantos
    E_inside = em_v * np.sin(np.pi / 2.0 * d_norm) ** 2

    # ── Fora da malha: decaimento exponencial ─────────────────────
    # Ponto mais próximo sobre a borda da malha
    x_cl = np.clip(X, 0.0, comprimento)
    y_cl = np.clip(Y, 0.0, largura)
    dist_borda = np.sqrt((X - x_cl)**2 + (Y - y_cl)**2)
    # Comprimento característico: ~35 % do raio equivalente da malha
    L_decay = np.sqrt(comprimento * largura) * 0.35
    # Na borda (dist=0) → Em; decresce para 0 ao longe
    E_outside = em_v * np.exp(-dist_borda / L_decay)

    Z = np.where(inside, E_inside, E_outside)
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
    """
    Superfície 3D da tensão de toque com plano horizontal de limite admissível.

    A superfície mostra a variação espacial da tensão de toque calculada pelo
    modelo simplificado. O plano azul indica o valor admissível (IEEE 80).
    Pontos acima do plano azul representam regiões onde o critério de segurança
    seria excedido caso existissem equipamentos aterrados naquele local.
    """
    X, Y, Z = calcula_mapa_tensao(largura, comprimento, rg_ohm, ig_a, em_v)

    gpr_v = rg_ohm * ig_a
    z_max = max(em_v, etoque_adm_v) * 1.15

    # Proporção real da malha para o aspect ratio 3D
    lado_max = max(comprimento, largura)
    ax = comprimento / lado_max
    ay = largura / lado_max

    fig = go.Figure()

    # ── Superfície de tensão de toque ────────────────────────────
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        colorscale=[
            [0.00, "rgb(0, 130, 0)"],    # verde  – zona segura
            [0.45, "rgb(230, 200, 0)"],  # amarelo – atenção
            [1.00, "rgb(180, 0, 0)"],    # vermelho – zona crítica
        ],
        cmin=0.0,
        cmax=z_max,
        colorbar=dict(
            title=dict(text="Etoque [V]", side="right"),
            thickness=14,
            len=0.65,
            y=0.5,
        ),
        opacity=0.90,
        name="Etoque(x,y)",
        hovertemplate=(
            "x = %{x:.1f} m<br>"
            "y = %{y:.1f} m<br>"
            "Etoque ≈ <b>%{z:.0f} V</b><extra></extra>"
        ),
    ))

    # ── Plano horizontal: Etoque admissível ──────────────────────
    Z_lim = np.full_like(Z, etoque_adm_v)
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z_lim,
        colorscale=[[0, "rgba(30,100,220,0.22)"], [1, "rgba(30,100,220,0.22)"]],
        showscale=False,
        opacity=0.38,
        name=f"Eadm = {etoque_adm_v:.0f} V",
        hovertemplate=f"Etoque admissível = {etoque_adm_v:.0f} V<extra></extra>",
    ))

    # ── Contorno da malha no plano Z = 0 ─────────────────────────
    fig.add_trace(go.Scatter3d(
        x=[0, comprimento, comprimento, 0, 0],
        y=[0, 0, largura, largura, 0],
        z=[0, 0, 0, 0, 0],
        mode="lines",
        line=dict(color="black", width=5),
        name="Limite da malha",
        hoverinfo="skip",
    ))

    fig.update_layout(
        title=dict(
            text=(
                f"{titulo}<br>"
                f"<sup>Em = {em_v:.0f} V  |  "
                f"Eadm = {etoque_adm_v:.0f} V  |  "
                f"GPR = {gpr_v:.0f} V  |  "
                f"⚠️ Aproximação visual — cálculo rigoroso requer FEM</sup>"
            ),
            font=dict(size=13),
        ),
        scene=dict(
            xaxis=dict(title="x [m] (comprimento)", gridcolor="lightgray",
                       backgroundcolor="rgb(245,245,245)"),
            yaxis=dict(title="y [m] (largura)", gridcolor="lightgray",
                       backgroundcolor="rgb(245,245,245)"),
            zaxis=dict(
                title="Tensão de toque [V]",
                gridcolor="lightgray",
                backgroundcolor="rgb(245,245,245)",
                range=[0.0, z_max],
            ),
            aspectmode="manual",
            aspectratio=dict(x=ax * 1.6, y=ay * 1.6, z=0.65),
            camera=dict(
                eye=dict(x=-1.6, y=-1.6, z=1.1),
                up=dict(x=0, y=0, z=1),
            ),
        ),
        legend=dict(
            x=0.01, y=0.99,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="lightgray",
            borderwidth=1,
        ),
        height=640,
        margin=dict(l=0, r=0, t=90, b=0),
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
