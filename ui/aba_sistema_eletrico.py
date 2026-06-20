# -*- coding: utf-8 -*-
"""
ui/aba_sistema_eletrico.py
==========================

Aba Streamlit para entrada de:
  - Dados dos transformadores
  - Impedâncias de sequência por barra (Z1, Z2, Z0)
  - Correntes de curto-circuito por barra (Icc3F, Icc2F, Icc1F, Ip)
  - Dados dos relés de proteção e tempo de eliminação (tc)

INTEGRAÇÃO em app.py:
  from ui.aba_sistema_eletrico import aba_sistema_eletrico

  # Na função main(), dentro de st.tabs():
  with abas[N]: aba_sistema_eletrico()
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from auth.auth import tenant_id_atual, is_viewer
from data import repository as repo
# Importar após integrar repository.py:
from data.repository import (
    salva_barras_sistema, lista_barras,
    salva_reles, lista_reles,
    salva_transformadores, lista_transformadores,
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _float(v, default=0.0) -> float:
    try:
        return float(v) if v not in (None, "", "nan") else default
    except (TypeError, ValueError):
        return default


def _icc_3f(tensao_kv: float, z1_r: float, z1_x: float) -> float:
    """Icc trifásico estimado: Icc = V / (√3 × |Z1|)"""
    z1 = np.sqrt(z1_r**2 + z1_x**2)
    if z1 <= 0 or tensao_kv <= 0:
        return 0.0
    return (tensao_kv / np.sqrt(3)) / z1  # kA (se Z em Ω e V em kV)


def _kappa(xr: float) -> float:
    """Fator de pico κ conforme IEC 60909-0:2016 eq. (13)."""
    if xr <= 0:
        return 1.0
    return 1.02 + 0.98 * np.exp(-3.0 / xr)


# ════════════════════════════════════════════════════════════════
# SUBSEÇÃO: TRANSFORMADORES
# ════════════════════════════════════════════════════════════════

def _sub_transformadores(pid: int):
    st.subheader("Transformador(es) da SE")
    st.caption(
        "Informe os dados de placa dos transformadores. "
        "Esses dados aparecem na capa e nos dados do sistema no relatório."
    )

    trafos_existentes = lista_transformadores(pid)
    df_ini = pd.DataFrame([
        {
            "Tag": t.tag or "",
            "Pot. [MVA]": _float(t.potencia_mva),
            "AT [kV]": _float(t.tensao_at_kv),
            "MT [kV]": _float(t.tensao_mt_kv),
            "Grupo": t.grupo_ligacao or "",
            "Zcc [%]": _float(t.zcc_pct),
            "In_AT [A]": _float(t.corrente_nom_at_a),
            "In_MT [A]": _float(t.corrente_nom_mt_a),
            "Fabricante": t.fabricante or "",
        }
        for t in trafos_existentes
    ] or [{
        "Tag": "TR-01", "Pot. [MVA]": 30.0,
        "AT [kV]": 138.0, "MT [kV]": 13.8,
        "Grupo": "YNyn0", "Zcc [%]": 12.5,
        "In_AT [A]": 125.5, "In_MT [A]": 1255.3,
        "Fabricante": "",
    }])

    df_edit = st.data_editor(
        df_ini, num_rows="dynamic", use_container_width=True,
        column_config={
            "Pot. [MVA]": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
            "AT [kV]": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
            "MT [kV]": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
            "Zcc [%]": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
            "In_AT [A]": st.column_config.NumberColumn(format="%.1f", min_value=0.0),
            "In_MT [A]": st.column_config.NumberColumn(format="%.1f", min_value=0.0),
        },
        key="editor_trafos",
    )

    if not is_viewer() and st.button("💾 Salvar transformadores", key="btn_salva_trafos"):
        trafos = [
            {
                "tag": str(r["Tag"]),
                "potencia_mva": _float(r["Pot. [MVA]"]) or None,
                "tensao_at_kv": _float(r["AT [kV]"]) or None,
                "tensao_mt_kv": _float(r["MT [kV]"]) or None,
                "grupo_ligacao": str(r["Grupo"]) or None,
                "zcc_pct": _float(r["Zcc [%]"]) or None,
                "corrente_nom_at_a": _float(r["In_AT [A]"]) or None,
                "corrente_nom_mt_a": _float(r["In_MT [A]"]) or None,
                "fabricante": str(r["Fabricante"]) or None,
            }
            for _, r in df_edit.iterrows()
            if r["Tag"]
        ]
        try:
            salva_transformadores(pid, tenant_id_atual(), trafos)
            st.success(f"{len(trafos)} transformador(es) salvos.")
        except Exception as e:
            st.error(f"Erro: {e}")


# ════════════════════════════════════════════════════════════════
# SUBSEÇÃO: BARRAS E IMPEDÂNCIAS
# ════════════════════════════════════════════════════════════════

def _sub_barras(pid: int):
    st.subheader("Barras e Impedâncias de Sequência")
    st.markdown("""
    Informe as impedâncias de sequência (Z1, Z2, Z0) no ponto de falta de cada barra da SE.
    Os valores são obtidos do **estudo de curto-circuito** (ETAP, DIgSILENT, MATLAB/Simulink, etc.)
    e são usados para documentar a origem da corrente **3I₀** adotada.

    > 💡 **Barra do projeto**: marque ✅ a barra cujo Icc1F é o 3I₀ usado no cálculo da malha.
    """)

    barras_exist = lista_barras(pid)
    df_ini = pd.DataFrame([
        {
            "Barra": b.nome,
            "Tensão [kV]": _float(b.tensao_kv),
            "Tipo": b.tipo or "AT",
            "Z1 R [Ω]": _float(b.z1_r_ohm),
            "Z1 X [Ω]": _float(b.z1_x_ohm),
            "Z0 R [Ω]": _float(b.z0_r_ohm),
            "Z0 X [Ω]": _float(b.z0_x_ohm),
            "Icc3F [kA]": _float(b.icc_3f_ka),
            "Icc1F [kA]": _float(b.icc_1f_ka),
            "Icc2F [kA]": _float(b.icc_2f_ka),
            "Ip [kA]": _float(b.ip_pico_ka),
            "X/R": _float(b.xr_ratio),
            "Barra do projeto ✅": b.e_barra_projeto,
        }
        for b in barras_exist
    ] or [
        {
            "Barra": "Barra AT 138 kV", "Tensão [kV]": 138.0, "Tipo": "AT",
            "Z1 R [Ω]": 2.5, "Z1 X [Ω]": 25.0, "Z0 R [Ω]": 3.8, "Z0 X [Ω]": 10.0,
            "Icc3F [kA]": 0.0, "Icc1F [kA]": 8.0, "Icc2F [kA]": 0.0, "Ip [kA]": 0.0,
            "X/R": 10.0, "Barra do projeto ✅": True,
        },
        {
            "Barra": "Barra MT 13,8 kV", "Tensão [kV]": 13.8, "Tipo": "MT",
            "Z1 R [Ω]": 0.025, "Z1 X [Ω]": 0.25, "Z0 R [Ω]": 0.038, "Z0 X [Ω]": 0.10,
            "Icc3F [kA]": 0.0, "Icc1F [kA]": 0.0, "Icc2F [kA]": 0.0, "Ip [kA]": 0.0,
            "X/R": 10.0, "Barra do projeto ✅": False,
        },
    ])

    df_edit = st.data_editor(
        df_ini, num_rows="dynamic", use_container_width=True,
        column_config={
            "Tensão [kV]": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
            "Tipo": st.column_config.SelectboxColumn(options=["AT", "MT", "BT", "GD", "Outra"]),
            "Z1 R [Ω]": st.column_config.NumberColumn(format="%.6f", min_value=0.0),
            "Z1 X [Ω]": st.column_config.NumberColumn(format="%.6f", min_value=0.0),
            "Z0 R [Ω]": st.column_config.NumberColumn(format="%.6f", min_value=0.0),
            "Z0 X [Ω]": st.column_config.NumberColumn(format="%.6f", min_value=0.0),
            "Icc3F [kA]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "Icc1F [kA]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "Icc2F [kA]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "Ip [kA]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "X/R": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
            "Barra do projeto ✅": st.column_config.CheckboxColumn(),
        },
        key="editor_barras",
    )

    # Auto-calcular Icc3F e Ip quando Z1 fornecido
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚡ Auto-calcular Icc3F e Ip (de Z1 e X/R)", key="btn_calc_icc"):
            st.info(
                "Valores estimativos usando Icc3F = V/(√3·|Z1|). "
                "Para valores definitivos, use o software de estudo elétrico."
            )
            for i, row in df_edit.iterrows():
                v_kv = _float(row["Tensão [kV]"])
                z1r = _float(row["Z1 R [Ω]"])
                z1x = _float(row["Z1 X [Ω]"])
                xr = _float(row["X/R"]) or (z1x / z1r if z1r > 0 else 10.0)
                icc3f = _icc_3f(v_kv, z1r, z1x)
                ip = _kappa(xr) * np.sqrt(2) * icc3f
                st.write(f"**{row['Barra']}**: Icc3F ≈ {icc3f:.4f} kA | Ip ≈ {ip:.4f} kA")

    with col2:
        if not is_viewer() and st.button("💾 Salvar barras", type="primary", key="btn_salva_barras"):
            barras = [
                {
                    "nome": str(r["Barra"]),
                    "tensao_kv": _float(r["Tensão [kV]"]),
                    "tipo": str(r["Tipo"]),
                    "z1_r_ohm": _float(r["Z1 R [Ω]"]) or None,
                    "z1_x_ohm": _float(r["Z1 X [Ω]"]) or None,
                    "z0_r_ohm": _float(r["Z0 R [Ω]"]) or None,
                    "z0_x_ohm": _float(r["Z0 X [Ω]"]) or None,
                    "icc_3f_ka": _float(r["Icc3F [kA]"]) or None,
                    "icc_1f_ka": _float(r["Icc1F [kA]"]) or None,
                    "icc_2f_ka": _float(r["Icc2F [kA]"]) or None,
                    "ip_pico_ka": _float(r["Ip [kA]"]) or None,
                    "xr_ratio": _float(r["X/R"]) or None,
                    "e_barra_projeto": bool(r.get("Barra do projeto ✅", False)),
                }
                for _, r in df_edit.iterrows()
                if r["Barra"]
            ]
            try:
                salva_barras_sistema(pid, tenant_id_atual(), barras)
                st.success(f"{len(barras)} barra(s) salva(s).")
            except Exception as e:
                st.error(f"Erro: {e}")


# ════════════════════════════════════════════════════════════════
# SUBSEÇÃO: RELÉS DE PROTEÇÃO
# ════════════════════════════════════════════════════════════════

def _sub_reles(pid: int):
    st.subheader("Relés de Proteção e Tempo de Eliminação (tc)")
    st.markdown("""
    Cadastre os relés de proteção da SE. O campo **tc total** (t_relé + t_abertura DJ)
    de qualquer relé pode ser marcado como o **tc adotado** no estudo de malha.

    > 🔑 **tc adotado** é o tempo usado nas equações de Dalziel e Sverak.
    """)

    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())
    de = p.dados_entrada if p else None
    tc_atual = float(de.tempo_eliminacao_s) if de else None

    if tc_atual:
        st.info(f"**tc atual no estudo de malha:** {tc_atual:.3f} s  "
                f"— marque o relé correspondente abaixo como ✅ adotado.")

    reles_exist = lista_reles(pid)
    df_ini = pd.DataFrame([
        {
            "Barra": r.barra_nome or "",
            "Relé / Função": r.nome,
            "Fabricante/Modelo": f"{r.fabricante or ''} {r.modelo or ''}".strip(),
            "Funções ANSI": r.funcoes_ansi or "",
            "Tipo": r.tipo_protecao or "Primária",
            "Nível": r.nivel,
            "t_relé [s]": _float(r.tempo_rele_s),
            "t_DJ [s]": _float(r.tempo_abertura_dj_s, 0.05),
            "tc total [s]": _float(r.tempo_total_tc_s),
            "tc adotado ✅": r.e_tc_adotado,
        }
        for r in reles_exist
    ] or [
        {
            "Barra": "Barra AT 138 kV", "Relé / Função": "87T - Dif. Transformador",
            "Fabricante/Modelo": "SEL-487E", "Funções ANSI": "87T",
            "Tipo": "Primária", "Nível": 1,
            "t_relé [s]": 0.020, "t_DJ [s]": 0.050, "tc total [s]": 0.070,
            "tc adotado ✅": True,
        },
        {
            "Barra": "Barra AT 138 kV", "Relé / Função": "50/51 - Sobrecorrente AT",
            "Fabricante/Modelo": "SEL-751", "Funções ANSI": "50/51",
            "Tipo": "1º Backup", "Nível": 2,
            "t_relé [s]": 0.300, "t_DJ [s]": 0.050, "tc total [s]": 0.350,
            "tc adotado ✅": False,
        },
        {
            "Barra": "Barra MT 13,8 kV", "Relé / Função": "51 - Sobrecorrente MT",
            "Fabricante/Modelo": "SEL-751", "Funções ANSI": "51",
            "Tipo": "2º Backup", "Nível": 3,
            "t_relé [s]": 0.600, "t_DJ [s]": 0.060, "tc total [s]": 0.660,
            "tc adotado ✅": False,
        },
    ])

    df_edit = st.data_editor(
        df_ini, num_rows="dynamic", use_container_width=True,
        column_config={
            "Tipo": st.column_config.SelectboxColumn(
                options=["Primária", "1º Backup", "2º Backup", "Emergência"]
            ),
            "Nível": st.column_config.NumberColumn(min_value=1, max_value=4, step=1),
            "t_relé [s]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "t_DJ [s]": st.column_config.NumberColumn(format="%.4f", min_value=0.01, max_value=0.20),
            "tc total [s]": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "tc adotado ✅": st.column_config.CheckboxColumn(
                help="Marque o relé cujo tc é o adotado no estudo de malha"
            ),
        },
        key="editor_reles",
    )

    col1, col2 = st.columns(2)

    # Tabela de coordenação resumida
    with col1:
        st.markdown("**Coordenação — resumo de tempos**")
        df_coord = df_edit[["Tipo", "Nível", "t_relé [s]", "t_DJ [s]", "tc total [s]", "tc adotado ✅"]].copy()
        df_coord = df_coord.sort_values("Nível")
        st.dataframe(df_coord, use_container_width=True, hide_index=True)

    with col2:
        tc_adotado_sel = df_edit[df_edit["tc adotado ✅"] == True]
        if not tc_adotado_sel.empty:
            tc_val = float(tc_adotado_sel.iloc[0]["tc total [s]"])
            st.metric("tc adotado (selecionado)", f"{tc_val:.4f} s")
            if de and abs(tc_val - tc_atual) > 0.001:
                st.warning(
                    f"⚠️ O tc selecionado ({tc_val:.3f} s) difere do tc no estudo "
                    f"de malha ({tc_atual:.3f} s). Salve e atualize a aba 4."
                )

    if not is_viewer() and st.button("💾 Salvar relés", type="primary", key="btn_salva_reles"):
        reles = [
            {
                "barra_nome": str(r["Barra"]) or None,
                "nome": str(r["Relé / Função"]),
                "fabricante": str(r["Fabricante/Modelo"]).split()[0] if r["Fabricante/Modelo"] else None,
                "modelo": " ".join(str(r["Fabricante/Modelo"]).split()[1:]) or None,
                "funcoes_ansi": str(r["Funções ANSI"]) or None,
                "tipo_protecao": str(r["Tipo"]),
                "nivel": int(r["Nível"]),
                "tempo_rele_s": _float(r["t_relé [s]"]) or None,
                "tempo_abertura_dj_s": _float(r["t_DJ [s]"], 0.05),
                "tempo_total_tc_s": _float(r["tc total [s]"]) or None,
                "e_tc_adotado": bool(r.get("tc adotado ✅", False)),
            }
            for _, r in df_edit.iterrows()
            if r["Relé / Função"]
        ]
        try:
            salva_reles(pid, tenant_id_atual(), reles)
            st.success(f"{len(reles)} relé(s) salvo(s).")
        except Exception as e:
            st.error(f"Erro: {e}")


# ════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL DA ABA
# ════════════════════════════════════════════════════════════════

def aba_sistema_eletrico():
    """Aba 'Sistema Elétrico' do app BK Malha de Terra."""
    st.header("5. Sistema Elétrico e Proteção")
    st.caption(
        "Dados para documentar a origem da corrente de falta 3I₀ e do tempo "
        "de eliminação tc utilizados no estudo de malha. Necessários para "
        "aprovação pela concessionária."
    )

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificação do projeto primeiro (aba 1).")
        return

    pid = st.session_state["projeto_id"]

    tab1, tab2, tab3 = st.tabs([
        "🔌 Transformadores",
        "⚡ Barras e Curto-Circuito",
        "🛡️ Relés e Proteção",
    ])

    with tab1:
        _sub_transformadores(pid)

    with tab2:
        _sub_barras(pid)

    with tab3:
        _sub_reles(pid)
