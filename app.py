"""
app.py
======

BK Malha de Terra v2 Ã¢ÂÂ SaaS Multi-Tenant
Dimensionamento de malhas de aterramento IEEE 80 / NBR 15751

Novidades v2:
    - AutenticaÃÂ§ÃÂ£o (login/cadastro por empresa)
    - Multi-tenancy: cada empresa vÃÂª apenas seus projetos
    - Fator Cp de crescimento da corrente (P0 do relatÃÂ³rio tÃÂ©cnico)
    - atende_condutor bloqueia aprovaÃÂ§ÃÂ£o (P0 do relatÃÂ³rio tÃÂ©cnico)
    - CritÃÂ©rio GPR correto na verificaÃÂ§ÃÂ£o final (P0)
    - PÃÂ¡gina de administraÃÂ§ÃÂ£o de usuÃÂ¡rios

Rodar:
    streamlit run app.py
"""

from __future__ import annotations

import io
import json
import os
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

# ---- Auth (v2) ----
from auth.auth import verificar_sessao, tenant_id_atual, usuario_id_atual, is_viewer
from auth.pagina_login import render_login, render_sidebar_usuario
from auth.pagina_admin import render_admin

# ---- Core ----
from core.condutor import Material, dimensiona_condutor
from core.corrente import corrente_malha_ig
from core.geometria import gera_cabos_malha, posiciona_hastes
from core.resistencia import GeometriaMalha, calcula_resistencia_e_tensoes
from core.solo import (
    MedicaoWenner, estratifica_2_camadas, rho_aparente_malha,
    rho_equivalente_simplificado,
)
from core.tensoes import calcula_tensoes_admissiveis
from core.verificacao import itera_num_hastes

# ---- Data ----
from data import repository as repo
from data.db import testa_conexao

# ---- UI ----
from ui.visualizacoes import (
    plot_curva_wenner, plot_iteracao_hastes, plot_mapa_tensao_3d,
    plot_planta_malha, plot_verificacao,
)



# ============================================================
# CONFIGURAÃÂÃÂO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="BK Malha de Terra",
    page_icon="Ã¢ÂÂ¡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SIDEBAR - SELEÃÂÃÂO/CRIAÃÂÃÂO DE PROJETO
# ============================================================

def sidebar_projetos():
    st.sidebar.title("Ã¢ÂÂ¡ BK Malha de Terra")
    st.sidebar.caption("IEEE 80-2013 ÃÂ· NBR 15751 ÃÂ· NBR 7117")

    # Healthcheck do banco
    with st.sidebar.expander("Ã°ÂÂÂ Banco de dados", expanded=False):
        if st.button("Testar conexÃÂ£o"):
            r = testa_conexao()
            if r["status"] == "ok":
                emoji = "Ã°ÂÂÂÃ¯Â¸Â" if r["backend"] == "SQLite" else "Ã°ÂÂÂ"
                st.success(f"{emoji} {r['backend']} ÃÂ· {r['tabelas_existentes']} tabelas")
                st.caption(r["versao"][:80])
            else:
                st.error(f"Erro: {r.get('erro', '?')}")

    st.sidebar.divider()

    # Ã¢ÂÂÃ¢ÂÂ Info do usuÃÂ¡rio e empresa Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    render_sidebar_usuario()

    st.sidebar.divider()
    st.sidebar.subheader("Projeto atual")

    # Lista apenas projetos do tenant logado
    tid = tenant_id_atual()
    try:
        projetos = repo.lista_projetos(tenant_id=tid, limit=50) if tid else []
    except Exception as e:
        st.sidebar.error(f"Banco indisponÃÂ­vel: {e}")
        projetos = []

    opcoes = ["Ã¢ÂÂ Novo projeto..."] + [
        f"#{p.id} ÃÂ· {p.numero_projeto} R{p.revisao} ÃÂ· {p.cliente[:30]}"
        for p in projetos
    ]
    escolha = st.sidebar.selectbox("Selecionar", opcoes, key="select_projeto")

    if escolha == "Ã¢ÂÂ Novo projeto...":
        st.session_state["projeto_id"] = None
    else:
        idx = opcoes.index(escolha) - 1
        st.session_state["projeto_id"] = projetos[idx].id

    if st.session_state.get("projeto_id"):
        if st.sidebar.button("Ã°ÂÂÂÃ¯Â¸Â Excluir projeto", type="secondary"):
            repo.deleta_projeto(st.session_state["projeto_id"], tenant_id=tenant_id_atual())
            st.session_state["projeto_id"] = None
            st.rerun()


# ============================================================
# ABA 1 - PROJETO
# ============================================================

def aba_projeto():
    st.header("1. IdentificaÃÂ§ÃÂ£o do Projeto")

    pid = st.session_state.get("projeto_id")
    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual()) if pid else None

    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input(
            "Cliente *", value=(p.cliente if p else ""), max_chars=200
        )
        nome = st.text_input(
            "Nome do projeto *", value=(p.nome_projeto if p else ""), max_chars=300
        )
        numero = st.text_input(
            "NÃÂºmero do projeto *", value=(p.numero_projeto if p else ""), max_chars=50
        )
        revisao = st.text_input(
            "RevisÃÂ£o", value=(p.revisao if p else "00"), max_chars=10
        )
    with col2:
        responsavel = st.text_input(
            "ResponsÃÂ¡vel tÃÂ©cnico", value=(p.responsavel_tecnico or "" if p else ""),
        )
        crea = st.text_input(
            "CREA do responsÃÂ¡vel", value=(p.crea_responsavel or "" if p else ""),
        )
        concessionaria = st.selectbox(
            "ConcessionÃÂ¡ria",
            options=["", "Celesc", "Energisa", "Copel", "CPFL", "Enel",
                     "Neoenergia", "Equatorial", "Outra"],
            index=0,
        )
        data_calc = st.date_input(
            "Data do cÃÂ¡lculo", value=(p.data_calculo if p else date.today())
        )

    obs = st.text_area("ObservaÃÂ§ÃÂµes", value=(p.observacoes or "" if p else ""))

    if st.button("Ã°ÂÂÂ¾ Salvar identificaÃÂ§ÃÂ£o", type="primary"):
        if not (cliente and nome and numero):
            st.error("Cliente, nome e nÃÂºmero sÃÂ£o obrigatÃÂ³rios.")
            return
        try:
            if pid:
                # Atualiza (criamos via cria_projeto pq nÃÂ£o temos update direto)
                # Para v1 - simplificaÃÂ§ÃÂ£o: deletar e recriar mantendo id ÃÂ© complicado.
                # Vamos atualizar via SQL direto:
                from data.db import get_session
                from data.models import Projeto
                with get_session() as s:
                    pp = s.get(Projeto, pid)
                    pp.cliente = cliente
                    pp.nome_projeto = nome
                    pp.numero_projeto = numero
                    pp.revisao = revisao
                    pp.responsavel_tecnico = responsavel
                    pp.crea_responsavel = crea
                    pp.concessionaria = concessionaria
                    pp.data_calculo = data_calc
                    pp.observacoes = obs
                st.success(f"Projeto #{pid} atualizado.")
            else:
                new_id = repo.cria_projeto(
                    tenant_id=tenant_id_atual(),
                    criado_por_id=usuario_id_atual(),
                    cliente=cliente, nome_projeto=nome, numero_projeto=numero,
                    revisao=revisao, responsavel_tecnico=responsavel,
                    crea_responsavel=crea, concessionaria=concessionaria,
                    data_calculo=data_calc, observacoes=obs,
                )
                st.session_state["projeto_id"] = new_id
                st.success(f"Projeto criado com ID #{new_id}.")
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")


# ============================================================
# ABA 2 - SOLO
# ============================================================

def aba_solo():
    st.header("2. Solo - MÃÂ©todo de Wenner (NBR 7117)")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificaÃÂ§ÃÂ£o do projeto primeiro (aba 1).")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())

    st.markdown("""
    Insira pelo menos **4 mediÃÂ§ÃÂµes** com espaÃÂ§amentos crescentes (recomendado:
    1, 2, 4, 8, 16, 32 m). O app calcula ÃÂ aparente e ajusta um modelo de
    **2 camadas** por otimizaÃÂ§ÃÂ£o (Sunde).
    """)

    # Carrega mediÃÂ§ÃÂµes existentes ou template
    if p and p.medicoes_wenner:
        df_inicial = pd.DataFrame([
            {"EspaÃÂ§amento a [m]": float(m.espacamento_m),
             "ResistÃÂªncia R [ÃÂ©]": float(m.resistencia_ohm)}
            for m in p.medicoes_wenner
        ])
    else:
        df_inicial = pd.DataFrame({
            "EspaÃÂ§amento a [m]":  [1.0, 2.0, 4.0, 8.0, 16.0, 32.0],
            "ResistÃÂªncia R [ÃÂ©]":  [50.0, 25.0, 12.0, 6.0, 3.0, 1.5],
        })

    df_edit = st.data_editor(
        df_inicial,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "EspaÃÂ§amento a [m]": st.column_config.NumberColumn(
                format="%.2f", min_value=0.1, max_value=200.0
            ),
            "ResistÃÂªncia R [ÃÂ©]": st.column_config.NumberColumn(
                format="%.4f", min_value=0.001
            ),
        },
        key="editor_wenner",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ã°ÂÂ§Â® Calcular estratificaÃÂ§ÃÂ£o", type="primary"):
            try:
                medicoes = [
                    MedicaoWenner(
                        espacamento_m=float(row["EspaÃÂ§amento a [m]"]),
                        resistencia_ohm=float(row["ResistÃÂªncia R [ÃÂ©]"]),
                    )
                    for _, row in df_edit.iterrows()
                    if row["EspaÃÂ§amento a [m]"] > 0 and row["ResistÃÂªncia R [ÃÂ©]"] > 0
                ]
                if len(medicoes) < 3:
                    st.error("Insira pelo menos 3 mediÃÂ§ÃÂµes vÃÂ¡lidas.")
                    return

                solo = estratifica_2_camadas(medicoes)
                st.session_state["solo"] = solo
                st.session_state["medicoes"] = medicoes

                # Persiste no banco
                repo.salva_medicoes_wenner(
                    pid,
                    tenant_id=tenant_id_atual(),
                    medicoes=[{"espacamento_m": m.espacamento_m, "resistencia_ohm": m.resistencia_ohm}
                               for m in medicoes],
                )

                st.success("EstratificaÃÂ§ÃÂ£o calculada e salva.")
            except Exception as e:
                st.error(f"Erro: {e}")

    # Mostra resultados
    solo = st.session_state.get("solo")
    medicoes = st.session_state.get("medicoes")
    if solo and medicoes:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ÃÂÃ¢ÂÂ", f"{solo.rho1:.0f} ÃÂ©ÃÂ·m")
        c2.metric("ÃÂÃ¢ÂÂ", f"{solo.rho2:.0f} ÃÂ©ÃÂ·m")
        c3.metric("hÃ¢ÂÂ", f"{solo.h1:.2f} m")
        c4.metric("Erro RMS", f"{solo.erro_rms:.2f}%")

        st.plotly_chart(plot_curva_wenner(medicoes, solo), use_container_width=True)

        if solo.erro_rms > 15:
            st.warning(
                f"Erro RMS de {solo.erro_rms:.1f}% ÃÂ© alto. Considere refazer "
                "as mediÃÂ§ÃÂµes (vÃÂ¡rias direÃÂ§ÃÂµes, mesmo nÃÂ­vel d'ÃÂ¡gua) ou usar "
                "modelo de 3+ camadas em software dedicado."
            )


# ============================================================
# ABA 3 - GEOMETRIA
# ============================================================

def aba_geometria():
    st.header("3. Geometria, Brita e Hastes")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificaÃÂ§ÃÂ£o primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())
    de = p.dados_entrada if p else None

    st.subheader("DimensÃÂµes da SE")
    col1, col2, col3 = st.columns(3)
    largura = col1.number_input(
        "Largura W [m]",
        min_value=5.0, max_value=500.0,
        value=float(de.largura_m) if de else 40.0, step=1.0,
    )
    comprimento = col2.number_input(
        "Comprimento L [m]",
        min_value=5.0, max_value=500.0,
        value=float(de.comprimento_m) if de else 50.0, step=1.0,
    )
    profundidade = col3.number_input(
        "Profundidade da malha h [m]",
        min_value=0.3, max_value=2.0,
        value=float(de.profundidade_malha_m) if de else 0.5, step=0.05,
    )

    col1, col2 = st.columns(2)
    espac_principal = col1.number_input(
        "EspaÃÂ§amento da malha principal D [m]",
        min_value=1.0, max_value=20.0,
        value=float(de.espac_malha_principal_m) if de else 5.0, step=0.5,
    )
    espac_juncao = col2.number_input(
        "EspaÃÂ§amento da malha de junÃÂ§ÃÂ£o (bordas) [m]",
        min_value=0.5, max_value=20.0,
        value=float(de.espac_malha_juncao_m or 2.5) if de else 2.5, step=0.5,
        help="Malha mais densa nas bordas reduz Em nos cantos. Recomendado D/2.",
    )

    st.subheader("Brita superficial")
    col1, col2 = st.columns(2)
    brita_h = col1.number_input(
        "Espessura da brita [m]",
        min_value=0.0, max_value=0.30,
        value=float(de.brita_espessura_m) if de else 0.10, step=0.01,
        help="0.10m ÃÂ© o mÃÂ­nimo recomendado pela IEEE 80 ÃÂ§11.3",
    )
    brita_rho = col2.selectbox(
        "Resistividade da brita [ÃÂ©ÃÂ·m]",
        options=[1200, 2500, 3000, 5000, 10000],
        index=2,  # 3000
        format_func=lambda v: {
            1200: "1200 (brita molhada)",
            2500: "2500 (brita mÃÂ©dia)",
            3000: "3000 (brita seca - padrÃÂ£o IEEE 80)",
            5000: "5000 (brita lavada)",
            10000: "10000 (asfalto)",
        }[v],
    )

    st.subheader("Condutor da malha")
    col1, col2 = st.columns(2)
    condutor_material = col1.selectbox(
        "Material do condutor",
        options=["cobre_nu", "cobre_comercial", "copperweld_40",
                 "copperweld_30", "aluminio_5005", "aco_galvanizado"],
        index=0,
        format_func=lambda v: {
            "cobre_nu": "Cobre nu (100% IACS) - padrÃÂ£o",
            "cobre_comercial": "Cobre comercial (97% IACS)",
            "copperweld_40": "Copperweld 40% IACS",
            "copperweld_30": "Copperweld 30% IACS",
            "aluminio_5005": "AlumÃÂ­nio liga 5005",
            "aco_galvanizado": "AÃÂ§o galvanizado",
        }[v],
        help="Cobre nu ÃÂ© o mais comum em SE no Brasil",
    )
    bitolas_disponiveis = [16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]
    bitola_default_idx = (
        bitolas_disponiveis.index(int(float(de.condutor_bitola_mm2)))
        if (de and de.condutor_bitola_mm2
            and int(float(de.condutor_bitola_mm2)) in bitolas_disponiveis)
        else 3  # 50 mmÃÂ² (mÃÂ­nimo prÃÂ¡tico BK)
    )
    bitola_cabo = col2.selectbox(
        "Bitola do cabo [mmÃÂ²]",
        options=bitolas_disponiveis,
        index=bitola_default_idx,
        format_func=lambda v: f"{v} mmÃÂ²" + (" (mÃÂ­n. BK)" if v == 50 else ""),
        help="Bitola que serÃÂ¡ adotada. O app verifica se atende Sverak "
             "no cÃÂ¡lculo. Se a calculada exceder a escolhida, aparecerÃÂ¡ "
             "alerta para vocÃÂª revisar.",
    )

    st.subheader("Hastes copperweld")
    col1, col2 = st.columns(2)
    haste_l = col1.number_input(
        "Comprimento da haste Lr [m]",
        min_value=1.5, max_value=10.0,
        value=float(de.haste_comprimento_m) if de else 3.0, step=0.5,
    )
    haste_d_opt = col2.selectbox(
        "DiÃÂ¢metro da haste",
        options=[12.7, 14.3, 15.875, 19.05],
        index=2,  # 5/8"
        format_func=lambda v: {
            12.7: '1/2" (12.7 mm)',
            14.3: '9/16" (14.3 mm)',
            15.875: '5/8" (15.875 mm) - padrÃÂ£o',
            19.05: '3/4" (19.05 mm)',
        }[v],
    )

    if st.button("Ã°ÂÂÂ¾ Salvar geometria", type="primary"):
        try:
            campos_existentes_outros = {}
            if de:
                campos_existentes_outros = {
                    "i_falta_3i0_ka": float(de.i_falta_3i0_ka),
                    "tempo_eliminacao_s": float(de.tempo_eliminacao_s),
                    "sf_div_corrente": float(de.sf_div_corrente),
                    "xr_ratio": float(de.xr_ratio) if de.xr_ratio else 10.0,
                    "peso_pessoa_kg": int(de.peso_pessoa_kg),
                }
            else:
                # placeholders - serÃÂ£o preenchidos na aba curto
                campos_existentes_outros = {
                    "i_falta_3i0_ka": 5.0,
                    "tempo_eliminacao_s": 0.5,
                    "sf_div_corrente": 0.6,
                    "xr_ratio": 10.0,
                    "peso_pessoa_kg": 50,
                }

            repo.salva_dados_entrada(
                pid, tenant_id=tenant_id_atual(),
                largura_m=largura,
                comprimento_m=comprimento,
                profundidade_malha_m=profundidade,
                espac_malha_principal_m=espac_principal,
                espac_malha_juncao_m=espac_juncao,
                brita_espessura_m=brita_h,
                brita_resistividade_ohm=float(brita_rho),
                haste_comprimento_m=haste_l,
                haste_diametro_mm=float(haste_d_opt),
                condutor_material=condutor_material,
                condutor_bitola_mm2=float(bitola_cabo),
                **campos_existentes_outros,
            )
            st.success("Geometria salva.")
        except Exception as e:
            st.error(f"Erro: {e}")

    # PrÃÂ©-visualizaÃÂ§ÃÂ£o da malha
    st.subheader("PrÃÂ©-visualizaÃÂ§ÃÂ£o")
    cabos, n_h, n_v = gera_cabos_malha(
        largura, comprimento, espac_principal, espac_juncao
    )
    fig = plot_planta_malha(largura, comprimento, cabos, hastes=[],
                              titulo=f"PrÃÂ©-visualizaÃÂ§ÃÂ£o ({n_h}ÃÂ{n_v} cabos)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Cabos paralelos a L: {n_h} ÃÂ· Cabos paralelos a W: {n_v} ÃÂ· "
        f"Comprimento total estimado: {sum(np.hypot(c[2]-c[0], c[3]-c[1]) for c in cabos):.0f} m"
    )


# ============================================================
# ABA 4 - CURTO-CIRCUITO
# ============================================================

def aba_curto():
    st.header("4. Dados ElÃÂ©tricos do Curto-Circuito")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificaÃÂ§ÃÂ£o primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())
    de = p.dados_entrada if p else None

    st.markdown("""
    Dados do estudo de curto-circuito (extrair do estudo elÃÂ©trico). Para SE
    de distribuiÃÂ§ÃÂ£o tÃÂ­pica, use a corrente fase-terra no barramento de AT.
    """)

    col1, col2 = st.columns(2)
    i_falta = col1.number_input(
        "Corrente simÃÂ©trica de falta 3IÃ¢ÂÂ [kA]",
        min_value=0.5, max_value=80.0,
        value=float(de.i_falta_3i0_ka) if de else 8.0, step=0.5,
    )
    tempo = col2.number_input(
        "Tempo de eliminaÃÂ§ÃÂ£o tc [s]",
        min_value=0.05, max_value=3.0,
        value=float(de.tempo_eliminacao_s) if de else 0.5, step=0.05,
        help="ProteÃÂ§ÃÂ£o primÃÂ¡ria + tempo de abertura do disjuntor",
    )

    col1, col2 = st.columns(2)
    sf = col1.slider(
        "Fator de divisÃÂ£o Sf",
        min_value=0.05, max_value=1.0,
        value=float(de.sf_div_corrente) if de else 0.6, step=0.05,
        help="Tabela 10 IEEE 80. SE com cabo guarda + neutro: 0.4-0.6. Isolada: 1.0.",
    )
    xr = col2.number_input(
        "RelaÃÂ§ÃÂ£o X/R no ponto de falta",
        min_value=0.5, max_value=80.0,
        value=float(de.xr_ratio) if de and de.xr_ratio else 10.0, step=1.0,
    )

    peso = st.radio(
        "Peso da pessoa (Dalziel)",
        options=[50, 70],
        index=0 if (not de or de.peso_pessoa_kg == 50) else 1,
        horizontal=True,
        help="50kg ÃÂ© mais conservador, padrÃÂ£o das concessionÃÂ¡rias BR.",
    )

    # Ã¢ÂÂÃ¢ÂÂ Fator Cp (P0 do relatÃÂ³rio tÃÂ©cnico) Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    st.markdown("---")
    st.subheader("Fator de crescimento da corrente (Cp)")
    st.caption(
        "IEEE 80 ÃÂ§15 recomenda usar a mÃÂ¡xima corrente futura do sistema. "
        "Cp ÃÂ© um fator de projeto Ã¢ÂÂ nÃÂ£o ÃÂ© parÃÂ¢metro direto da norma, mas boa prÃÂ¡tica para sistemas em expansÃÂ£o."
    )
    cp_opcoes = {
        "1,00 Ã¢ÂÂ Sistema atual, sem expansÃÂ£o prevista": 1.00,
        "1,10 Ã¢ÂÂ ExpansÃÂ£o moderada (~10%)": 1.10,
        "1,20 Ã¢ÂÂ ExpansÃÂ£o relevante (~20%) Ã¢ÂÂ conservador": 1.20,
        "1,30 Ã¢ÂÂ Estudo muito conservador": 1.30,
        "Personalizado": None,
    }
    cp_sel = st.selectbox(
        "Cp Ã¢ÂÂ Fator de crescimento",
        list(cp_opcoes.keys()),
        index=0 if not de else (
            0 if float(de.cp_crescimento or 1.0) == 1.00 else
            1 if float(de.cp_crescimento or 1.0) == 1.10 else
            2 if float(de.cp_crescimento or 1.0) == 1.20 else
            3 if float(de.cp_crescimento or 1.0) == 1.30 else 4
        ),
    )
    cp_val = cp_opcoes[cp_sel]
    if cp_val is None:
        cp_val = st.number_input(
            "Cp personalizado", value=float(de.cp_crescimento or 1.0) if de else 1.0,
            min_value=1.0, max_value=2.0, step=0.05,
        )

    if cp_val > 1.0:
        st.info(
            f"IG serÃÂ¡ multiplicado por Cp = {cp_val:.2f}. "
            f"Ex.: se 3IÃ¢ÂÂ = {i_falta:.1f} kA Ã¢ÂÂ IG = Df ÃÂ Sf ÃÂ {cp_val:.2f} ÃÂ 3IÃ¢ÂÂ "
            f"Ã¢ÂÂ {i_falta * cp_val:.2f} kA (estimativa sem Df/Sf)."
        )

    if st.button("Ã°ÂÂÂ¾ Salvar dados elÃÂ©tricos", type="primary"):
        try:
            # mantÃÂ©m geometria existente
            campos_geom = {}
            if de:
                campos_geom = {
                    "largura_m": float(de.largura_m),
                    "comprimento_m": float(de.comprimento_m),
                    "profundidade_malha_m": float(de.profundidade_malha_m),
                    "espac_malha_principal_m": float(de.espac_malha_principal_m),
                    "espac_malha_juncao_m": float(de.espac_malha_juncao_m or 2.5),
                    "brita_espessura_m": float(de.brita_espessura_m),
                    "brita_resistividade_ohm": float(de.brita_resistividade_ohm),
                    "haste_comprimento_m": float(de.haste_comprimento_m),
                    "haste_diametro_mm": float(de.haste_diametro_mm),
                }
            else:
                st.error("Preencha geometria primeiro (aba 3).")
                return

            repo.salva_dados_entrada(
                pid,
                tenant_id=tenant_id_atual(),
                i_falta_3i0_ka=i_falta,
                tempo_eliminacao_s=tempo,
                sf_div_corrente=sf,
                xr_ratio=xr,
                peso_pessoa_kg=peso,
                cp_crescimento=cp_val,
                **campos_geom,
            )
            st.success("Dados elÃÂ©tricos salvos.")
        except Exception as e:
            st.error(f"Erro: {e}")


# ============================================================
# ABA 5 - CÃÂLCULO E RESULTADOS
# ============================================================

def aba_calculo():
    st.header("5. CÃÂ¡lculo IEEE 80 e Resultados")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificaÃÂ§ÃÂ£o primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())

    if not p or not p.dados_entrada or not p.medicoes_wenner:
        st.warning("Preencha solo (aba 2), geometria (aba 3) e dados elÃÂ©tricos (aba 4).")
        return

    de = p.dados_entrada

    st.subheader("Pipeline de cÃÂ¡lculo")
    st.caption(
        "Solo (Sunde) Ã¢ÂÂ IG (eq.70) Ã¢ÂÂ Condutor (eq.37) Ã¢ÂÂ "
        "Eadm (eqs.30-33) Ã¢ÂÂ Rg (Sverak/Schwarz) Ã¢ÂÂ Em/Es Ã¢ÂÂ VerificaÃÂ§ÃÂ£o"
    )

    if st.button("Ã¢ÂÂ¡ Executar cÃÂ¡lculo", type="primary"):
        with st.spinner("Calculando..."):
            try:
                # 1. Solo
                medicoes = [
                    MedicaoWenner(float(m.espacamento_m), float(m.resistencia_ohm))
                    for m in p.medicoes_wenner
                ]
                solo = estratifica_2_camadas(medicoes)
                # Usa rho aparente considerando malha + hastes (mais preciso
                # para solos estratificados que rho_equivalente_simplificado)
                rho_eq = rho_aparente_malha(
                    solo,
                    profundidade_malha=float(de.profundidade_malha_m),
                    comprimento_haste=float(de.haste_comprimento_m),
                )

                # 2. Corrente Ã¢ÂÂ com fator Cp (P0 do relatÃÂ³rio tÃÂ©cnico BK)
                corrente = corrente_malha_ig(
                    i_falta_3i0_a=float(de.i_falta_3i0_ka) * 1000.0,
                    sf_div_corrente=float(de.sf_div_corrente),
                    xr_ratio=float(de.xr_ratio),
                    tf_s=float(de.tempo_eliminacao_s),
                    cp_crescimento=float(de.cp_crescimento or 1.0),
                )

                # 3. Condutor Ã¢ÂÂ bitola mÃÂ­nima tÃÂ©rmica; usuÃÂ¡rio pode sobrescrever
                # P0: se bitola adotada < calculada, a aprovaÃÂ§ÃÂ£o serÃÂ¡ BLOQUEADA
                cond = dimensiona_condutor(
                    corrente_a=corrente.ig_a,
                    tempo_s=float(de.tempo_eliminacao_s),
                    material=Material(de.condutor_material),
                    temperatura_max_c=250.0,
                )
                bitola_usuario = float(de.condutor_bitola_mm2 or cond.bitola_adotada_mm2)
                cond.bitola_adotada_mm2 = bitola_usuario

                atende_condutor = bitola_usuario >= cond.bitola_calculada_mm2
                if not atende_condutor:
                    cond.observacoes.append(
                        f"Ã¢ÂÂ CONDUTOR REPROVADO: bitola adotada {bitola_usuario:.0f} mmÃÂ² "
                        f"< mÃÂ­nimo calculado {cond.bitola_calculada_mm2:.0f} mmÃÂ². "
                        "A aprovaÃÂ§ÃÂ£o do projeto serÃÂ¡ BLOQUEADA atÃÂ© a bitola ser corrigida."
                    )

                # 4. TensÃÂµes admissÃÂ­veis
                tensoes_adm = calcula_tensoes_admissiveis(
                    rho_solo=solo.rho1,
                    rho_brita=float(de.brita_resistividade_ohm),
                    h_brita=float(de.brita_espessura_m),
                    tempo_s=float(de.tempo_eliminacao_s),
                    peso_kg=int(de.peso_pessoa_kg),
                )

                # 5. Geometria + iteraÃÂ§ÃÂ£o
                geom_ini = GeometriaMalha(
                    largura_m=float(de.largura_m),
                    comprimento_m=float(de.comprimento_m),
                    profundidade_m=float(de.profundidade_malha_m),
                    espac_malha_m=float(de.espac_malha_principal_m),
                    bitola_cabo_mm2=bitola_usuario,
                    haste_comprimento_m=float(de.haste_comprimento_m),
                    haste_diametro_mm=float(de.haste_diametro_mm),
                    num_hastes=4,
                )
                iteracao = itera_num_hastes(
                    geom_inicial=geom_ini,
                    rho_eq=rho_eq,
                    ig_a=corrente.ig_a,
                    etoque_adm_v=tensoes_adm.etoque_v,
                    epasso_adm_v=tensoes_adm.epasso_v,
                    bitola_adotada_mm2=bitola_usuario,
                    bitola_calculada_mm2=cond.bitola_calculada_mm2,
                    n_hastes_min=4,
                    n_hastes_max=120,
                    incremento=4,
                )

                # Posiciona hastes
                hastes = posiciona_hastes(
                    largura=float(de.largura_m),
                    comprimento=float(de.comprimento_m),
                    n_hastes=iteracao.geometria_final.num_hastes,
                    haste_comprimento=float(de.haste_comprimento_m),
                )

                # Cabos para visualizaÃÂ§ÃÂ£o
                cabos, _, _ = gera_cabos_malha(
                    float(de.largura_m), float(de.comprimento_m),
                    float(de.espac_malha_principal_m),
                    float(de.espac_malha_juncao_m or 2.5),
                )

                # Salva no banco
                repo.salva_resultado(
                    pid, tenant_id=tenant_id_atual(),
                    rho1_ohm_m=solo.rho1, rho2_ohm_m=solo.rho2,
                    h1_m=solo.h1, rho_equivalente=rho_eq,
                    bitola_calculada_mm2=cond.bitola_calculada_mm2,
                    bitola_adotada_mm2=cond.bitola_adotada_mm2,
                    atende_condutor=atende_condutor,
                    cs_brita=tensoes_adm.cs_brita,
                    etoque_admissivel_v=tensoes_adm.etoque_v,
                    epasso_admissivel_v=tensoes_adm.epasso_v,
                    df_decremento=corrente.df_decremento,
                    cp_crescimento=corrente.cp_crescimento,
                    ig_corrente_malha_a=corrente.ig_a,
                    rg_sverak_ohm=iteracao.resultado.rg_sverak_ohm,
                    rg_schwarz_ohm=iteracao.resultado.rg_schwarz_ohm,
                    rg_adotado_ohm=iteracao.resultado.rg_adotado_ohm,
                    gpr_v=iteracao.resultado.gpr_v,
                    em_tensao_malha_v=iteracao.resultado.em_v,
                    es_tensao_passo_v=iteracao.resultado.es_v,
                    num_hastes=iteracao.geometria_final.num_hastes,
                    comprimento_total_cabo_m=iteracao.resultado.Lc_m,
                    posicoes_hastes_json={
                        "hastes": [{"x": h.x, "y": h.y, "rotulo": h.rotulo,
                                    "prioridade": h.prioridade} for h in hastes]
                    },
                    atende_toque=iteracao.verificacao.atende_toque,
                    atende_passo=iteracao.verificacao.atende_passo,
                    atende_geral=iteracao.verificacao.atende_geral,
                    margem_toque_pct=iteracao.verificacao.margem_toque_pct,
                    margem_passo_pct=iteracao.verificacao.margem_passo_pct,
                    json_completo={
                        "historico_iteracao": iteracao.historico,
                        "obs_corrente": corrente.observacoes,
                        "obs_condutor": cond.observacoes,
                        "obs_tensoes": tensoes_adm.observacoes,
                        "obs_verificacao": iteracao.verificacao.observacoes,
                    },
                )

                # Guarda em sessÃÂ£o para mostrar
                st.session_state["calc"] = {
                    "solo": solo, "rho_eq": rho_eq,
                    "corrente": corrente, "cond": cond,
                    "tensoes_adm": tensoes_adm,
                    "iteracao": iteracao,
                    "hastes": hastes, "cabos": cabos,
                    "geom_final": iteracao.geometria_final,
                }
                st.success("CÃÂ¡lculo executado e salvo.")
            except Exception as e:
                st.error(f"Erro no cÃÂ¡lculo: {e}")
                import traceback
                st.code(traceback.format_exc())

    # ---- Mostra resultados ----
    calc = st.session_state.get("calc")
    if not calc:
        return

    iteracao = calc["iteracao"]
    res = iteracao.resultado
    verif = iteracao.verificacao
    tensoes_adm = calc["tensoes_adm"]

    st.divider()
    st.subheader("Ã°ÂÂÂ Resultado final")

    # Status grande
    if verif.atende_geral:
        st.success("Ã¢ÂÂ MALHA ATENDE OS CRITÃÂRIOS DA IEEE 80-2013")
    else:
        st.error("Ã¢ÂÂ MALHA NÃÂO ATENDE - revisar projeto")

    # MÃÂ©tricas principais
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rg", f"{res.rg_adotado_ohm:.2f} ÃÂ©",
               help="Schwarz (mais preciso que Sverak)")
    c2.metric("GPR", f"{res.gpr_v:.0f} V")
    c3.metric("NÃÂº de hastes", f"{calc['geom_final'].num_hastes}")
    c4.metric("IteraÃÂ§ÃÂµes", f"{iteracao.iteracoes}")

    c1, c2 = st.columns(2)
    c1.metric(
        "Em (toque)",
        f"{res.em_v:.0f} V",
        f"adm {tensoes_adm.etoque_v:.0f} V ÃÂ· margem {verif.margem_toque_pct:+.1f}%",
        delta_color=("normal" if verif.atende_toque else "inverse"),
    )
    c2.metric(
        "Es (passo)",
        f"{res.es_v:.0f} V",
        f"adm {tensoes_adm.epasso_v:.0f} V ÃÂ· margem {verif.margem_passo_pct:+.1f}%",
        delta_color=("normal" if verif.atende_passo else "inverse"),
    )

    # ObservaÃÂ§ÃÂµes
    obs_all = (calc["corrente"].observacoes + calc["cond"].observacoes +
               tensoes_adm.observacoes + verif.observacoes)
    if obs_all:
        with st.expander("Ã¢ÂÂ Ã¯Â¸Â ObservaÃÂ§ÃÂµes tÃÂ©cnicas"):
            for o in obs_all:
                st.markdown(f"- {o}")

    # AnÃÂ¡lise de sensibilidade quando NÃÂO atende
    if not verif.atende_geral:
        with st.expander("Ã°ÂÂÂ§ AnÃÂ¡lise de sensibilidade Ã¢ÂÂ o que faria atender?",
                          expanded=True):
            st.caption(
                "CÃÂ¡lculos hipotÃÂ©ticos variando UM parÃÂ¢metro de cada vez "
                "para identificar a alavanca mais eficaz."
            )
            de_atual = repo.busca_projeto(pid, tenant_id=tenant_id_atual()).dados_entrada
            geom_base = calc["geom_final"]
            ig_atual = calc["corrente"].ig_a

            cenarios = []

            # 1. Reduzir tempo de eliminaÃÂ§ÃÂ£o
            for tc_novo in [0.3, 0.2, 0.1]:
                if tc_novo < float(de_atual.tempo_eliminacao_s):
                    tens_novo = calcula_tensoes_admissiveis(
                        rho_solo=calc["solo"].rho1,
                        rho_brita=float(de_atual.brita_resistividade_ohm),
                        h_brita=float(de_atual.brita_espessura_m),
                        tempo_s=tc_novo,
                        peso_kg=int(de_atual.peso_pessoa_kg),
                    )
                    res_novo = calcula_resistencia_e_tensoes(
                        calc["rho_eq"], ig_atual, geom_base
                    )
                    atende = (res_novo.em_v <= tens_novo.etoque_v
                              and res_novo.es_v <= tens_novo.epasso_v)
                    cenarios.append({
                        "MudanÃÂ§a": f"tc: {de_atual.tempo_eliminacao_s}s Ã¢ÂÂ {tc_novo}s",
                        "Em [V]": f"{res_novo.em_v:.0f}",
                        "Etoque adm [V]": f"{tens_novo.etoque_v:.0f}",
                        "Atende?": "Ã¢ÂÂ" if atende else "Ã¢ÂÂ",
                    })

            # 2. Aumentar brita
            for h_brita_nova in [0.15, 0.20]:
                if h_brita_nova > float(de_atual.brita_espessura_m):
                    tens_novo = calcula_tensoes_admissiveis(
                        rho_solo=calc["solo"].rho1,
                        rho_brita=float(de_atual.brita_resistividade_ohm),
                        h_brita=h_brita_nova,
                        tempo_s=float(de_atual.tempo_eliminacao_s),
                        peso_kg=int(de_atual.peso_pessoa_kg),
                    )
                    res_novo = calcula_resistencia_e_tensoes(
                        calc["rho_eq"], ig_atual, geom_base
                    )
                    atende = (res_novo.em_v <= tens_novo.etoque_v
                              and res_novo.es_v <= tens_novo.epasso_v)
                    cenarios.append({
                        "MudanÃÂ§a": f"brita: {de_atual.brita_espessura_m}m Ã¢ÂÂ {h_brita_nova}m",
                        "Em [V]": f"{res_novo.em_v:.0f}",
                        "Etoque adm [V]": f"{tens_novo.etoque_v:.0f}",
                        "Atende?": "Ã¢ÂÂ" if atende else "Ã¢ÂÂ",
                    })

            # 3. Hastes mais profundas
            for Lr_novo in [5.0, 8.0, 10.0]:
                if Lr_novo > float(de_atual.haste_comprimento_m):
                    rho_novo = rho_aparente_malha(
                        calc["solo"],
                        profundidade_malha=float(de_atual.profundidade_malha_m),
                        comprimento_haste=Lr_novo,
                    )
                    geom_novo = GeometriaMalha(
                        largura_m=geom_base.largura_m,
                        comprimento_m=geom_base.comprimento_m,
                        profundidade_m=geom_base.profundidade_m,
                        espac_malha_m=geom_base.espac_malha_m,
                        bitola_cabo_mm2=geom_base.bitola_cabo_mm2,
                        haste_comprimento_m=Lr_novo,
                        haste_diametro_mm=geom_base.haste_diametro_mm,
                        num_hastes=geom_base.num_hastes,
                    )
                    res_novo = calcula_resistencia_e_tensoes(
                        rho_novo, ig_atual, geom_novo
                    )
                    atende = (res_novo.em_v <= tensoes_adm.etoque_v
                              and res_novo.es_v <= tensoes_adm.epasso_v)
                    cenarios.append({
                        "MudanÃÂ§a": f"haste: {de_atual.haste_comprimento_m}m Ã¢ÂÂ {Lr_novo}m "
                                   f"(ÃÂ_eq: {calc['rho_eq']:.0f}Ã¢ÂÂ{rho_novo:.0f})",
                        "Em [V]": f"{res_novo.em_v:.0f}",
                        "Etoque adm [V]": f"{tensoes_adm.etoque_v:.0f}",
                        "Atende?": "Ã¢ÂÂ" if atende else "Ã¢ÂÂ",
                    })

            # 4. Reduzir espaÃÂ§amento da malha
            for D_novo in [2.5, 2.0, 1.5]:
                if D_novo < float(de_atual.espac_malha_principal_m):
                    geom_novo = GeometriaMalha(
                        largura_m=geom_base.largura_m,
                        comprimento_m=geom_base.comprimento_m,
                        profundidade_m=geom_base.profundidade_m,
                        espac_malha_m=D_novo,
                        bitola_cabo_mm2=geom_base.bitola_cabo_mm2,
                        haste_comprimento_m=geom_base.haste_comprimento_m,
                        haste_diametro_mm=geom_base.haste_diametro_mm,
                        num_hastes=geom_base.num_hastes,
                    )
                    res_novo = calcula_resistencia_e_tensoes(
                        calc["rho_eq"], ig_atual, geom_novo
                    )
                    atende = (res_novo.em_v <= tensoes_adm.etoque_v
                              and res_novo.es_v <= tensoes_adm.epasso_v)
                    cenarios.append({
                        "MudanÃÂ§a": f"D: {de_atual.espac_malha_principal_m}m Ã¢ÂÂ {D_novo}m",
                        "Em [V]": f"{res_novo.em_v:.0f}",
                        "Etoque adm [V]": f"{tensoes_adm.etoque_v:.0f}",
                        "Atende?": "Ã¢ÂÂ" if atende else "Ã¢ÂÂ",
                    })

            if cenarios:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(cenarios), use_container_width=True,
                    hide_index=True,
                )
            st.info(
                "Ã°ÂÂÂ¡ **Dica:** se nenhum cenÃÂ¡rio individual atende, "
                "combine 2-3 mudanÃÂ§as (ex: hastes 5m + brita 0,15m + tc 0,3s). "
                "O cÃÂ¡lculo isolado mostra qual alavanca ÃÂ© mais eficaz."
            )

    # GrÃÂ¡ficos
    st.divider()
    st.subheader("Ã°ÂÂÂ VisualizaÃÂ§ÃÂµes")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["VerificaÃÂ§ÃÂ£o", "Planta da malha", "Mapa 3D de tensÃÂ£o", "IteraÃÂ§ÃÂ£o"]
    )

    with tab1:
        st.plotly_chart(
            plot_verificacao(res.em_v, res.es_v,
                              tensoes_adm.etoque_v, tensoes_adm.epasso_v),
            use_container_width=True,
        )

    with tab2:
        de = repo.busca_projeto(pid, tenant_id=tenant_id_atual()).dados_entrada
        st.plotly_chart(
            plot_planta_malha(
                largura=float(de.largura_m),
                comprimento=float(de.comprimento_m),
                cabos=calc["cabos"],
                hastes=calc["hastes"],
                titulo=f"Malha proposta - {calc['geom_final'].num_hastes} hastes",
            ),
            use_container_width=True,
        )

    with tab3:
        de = repo.busca_projeto(pid, tenant_id=tenant_id_atual()).dados_entrada
        st.plotly_chart(
            plot_mapa_tensao_3d(
                largura=float(de.largura_m),
                comprimento=float(de.comprimento_m),
                rg_ohm=res.rg_adotado_ohm,
                ig_a=calc["corrente"].ig_a,
                em_v=res.em_v,
                etoque_adm_v=tensoes_adm.etoque_v,
            ),
            use_container_width=True,
        )
        st.caption(
            "Ã¢ÂÂ Ã¯Â¸Â AproximaÃÂ§ÃÂ£o visual da distribuiÃÂ§ÃÂ£o de tensÃÂ£o. "
            "CÃÂ¡lculo rigoroso do perfil de tensÃÂ£o requer FEM (CDEGS, COMSOL)."
        )

    with tab4:
        st.plotly_chart(
            plot_iteracao_hastes(iteracao.historico,
                                  tensoes_adm.etoque_v,
                                  tensoes_adm.epasso_v),
            use_container_width=True,
        )


# ============================================================
# ABA 6 - RELATÃÂRIO WORD
# ============================================================

def aba_relatorio():
    st.header("6. RelatÃÂ³rio Word (.docx)")

    pid = st.session_state.get("projeto_id")
    if not pid:
        st.warning("Selecione ou crie um projeto primeiro.")
        return

    p = repo.busca_projeto(pid, tenant_id=tenant_id_atual())
    if not p or not p.resultado or not p.dados_entrada:
        st.warning("Execute o cÃÂ¡lculo (aba 5) antes de gerar o relatÃÂ³rio.")
        return

    # Resumo do que serÃÂ¡ gerado
    st.markdown(f"""
    O relatÃÂ³rio conterÃÂ¡:
    
    1. **Capa** com identificaÃÂ§ÃÂ£o ({p.cliente} ÃÂ· {p.numero_projeto} R{p.revisao})
    2. **Objetivo** do estudo
    3. **Metodologia** com equaÃÂ§ÃÂµes IEEE 80/NBR 15751 e prÃÂ¡ticas construtivas
    4. **Dados de entrada** (solo, geometria, brita, hastes, curto)
    5. **Resultados** com tabelas e grÃÂ¡ficos exportados
    6. **ConclusÃÂ£o** ({"Ã¢ÂÂ Atende" if p.resultado.atende_geral else "Ã¢ÂÂ NÃÂ£o atende"})
    7. **ReferÃÂªncias** bibliogrÃÂ¡ficas
    """)

    # Verifica se hÃÂ¡ cÃÂ¡lculo em sessÃÂ£o para exportar grÃÂ¡ficos
    calc = st.session_state.get("calc")
    if not calc:
        st.warning(
            "Ã¢ÂÂ Ã¯Â¸Â Os grÃÂ¡ficos sÃÂ³ sÃÂ£o exportados se o cÃÂ¡lculo foi executado "
            "**nesta sessÃÂ£o** (aba 5). Execute o cÃÂ¡lculo novamente para "
            "incluir grÃÂ¡ficos no relatÃÂ³rio."
        )

    if st.button("Ã°ÂÂÂ Gerar relatÃÂ³rio Word", type="primary"):
        from relatorio.gerador_word import gera_relatorio_word, nome_arquivo_padrao
        from relatorio.exportador_imagens import (
            exporta_curva_wenner, exporta_planta_malha,
            exporta_verificacao, exporta_mapa_tensao,
        )
        from ui.visualizacoes import (
            plot_curva_wenner, plot_planta_malha,
            plot_mapa_tensao_3d, plot_verificacao,
        )

        with st.spinner("Gerando relatÃÂ³rio..."):
            try:
                imagens = {}
                falhas_export = []

                if calc:
                    de = p.dados_entrada
                    res = calc["iteracao"].resultado
                    tensoes_adm = calc["tensoes_adm"]

                    # 1. Curva Wenner
                    medicoes_sess = st.session_state.get("medicoes")
                    if medicoes_sess and calc.get("solo"):
                        fig_w = plot_curva_wenner(medicoes_sess, calc["solo"])
                        img = exporta_curva_wenner(
                            fig_w, medicoes_sess, calc["solo"]
                        )
                        if img:
                            imagens["wenner"] = img
                        else:
                            falhas_export.append("Curva de Wenner")

                    # 2. Planta da malha
                    fig_p = plot_planta_malha(
                        float(de.largura_m), float(de.comprimento_m),
                        calc["cabos"], calc["hastes"],
                        titulo=f"Malha proposta - {calc['geom_final'].num_hastes} hastes",
                    )
                    img = exporta_planta_malha(
                        fig_p,
                        float(de.largura_m), float(de.comprimento_m),
                        calc["cabos"], calc["hastes"],
                        f"Malha proposta - {calc['geom_final'].num_hastes} hastes",
                    )
                    if img:
                        imagens["planta"] = img
                    else:
                        falhas_export.append("Planta da malha")

                    # 3. VerificaÃÂ§ÃÂ£o
                    fig_v = plot_verificacao(
                        res.em_v, res.es_v,
                        tensoes_adm.etoque_v, tensoes_adm.epasso_v,
                    )
                    img = exporta_verificacao(
                        fig_v, res.em_v, res.es_v,
                        tensoes_adm.etoque_v, tensoes_adm.epasso_v,
                    )
                    if img:
                        imagens["verif"] = img
                    else:
                        falhas_export.append("GrÃÂ¡fico de verificaÃÂ§ÃÂ£o")

                    # 4. Mapa 3D (fallback ÃÂ© 2D contour - aceitÃÂ¡vel para Word)
                    fig_3d = plot_mapa_tensao_3d(
                        float(de.largura_m), float(de.comprimento_m),
                        res.rg_adotado_ohm, calc["corrente"].ig_a,
                        res.em_v, tensoes_adm.etoque_v,
                    )
                    img = exporta_mapa_tensao(
                        fig_3d,
                        float(de.largura_m), float(de.comprimento_m),
                        res.em_v, tensoes_adm.etoque_v,
                    )
                    if img:
                        imagens["mapa3d"] = img
                    else:
                        falhas_export.append("Mapa de tensÃÂ£o")

                if falhas_export:
                    st.warning(
                        f"Ã¢ÂÂ Ã¯Â¸Â NÃÂ£o foi possÃÂ­vel exportar: "
                        f"{', '.join(falhas_export)}. "
                        "O relatÃÂ³rio vai marcar como '[Figura ausente]'."
                    )

                # Logo BK (se existir)
                logo = os.getenv("BK_LOGO_PATH", "assets/bk_logo.png")
                logo_path = logo if os.path.exists(logo) else None

                # Gera doc
                docx_bytes = gera_relatorio_word(p, imagens, logo_path)
                nome_arq = nome_arquivo_padrao(p)

                # Registra no banco
                repo.registra_relatorio(pid, tenant_id=tenant_id_atual(), nome_arquivo=nome_arq, gerado_por=p.responsavel_tecnico)

                # Disponibiliza download
                st.success(
                    f"Ã¢ÂÂ RelatÃÂ³rio gerado ({len(docx_bytes)/1024:.0f} KB) ÃÂ· "
                    f"{len(imagens)} de 4 figuras incluÃÂ­das"
                )
                st.download_button(
                    label=f"Ã¢Â¬ÂÃ¯Â¸Â Baixar {nome_arq}",
                    data=docx_bytes,
                    file_name=nome_arq,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception as e:
                st.error(f"Erro ao gerar relatÃÂ³rio: {e}")
                import traceback
                st.code(traceback.format_exc())

    # HistÃÂ³rico de relatÃÂ³rios gerados (busca em sessÃÂ£o nova - evita
    # DetachedInstanceError ao acessar relacionamento de objeto ORM
    # de sessÃÂ£o jÃÂ¡ fechada)
    relatorios = repo.lista_relatorios_de(pid)
    if relatorios:
        st.divider()
        st.subheader("Ã°ÂÂÂ HistÃÂ³rico de relatÃÂ³rios gerados")
        for r in relatorios:
            st.text(
                f"  {r['gerado_em'].strftime('%d/%m/%Y %H:%M')} Ã¢ÂÂ "
                f"{r['nome_arquivo']}"
                + (f" (por {r['gerado_por']})" if r['gerado_por'] else "")
            )


# ============================================================
# MAIN
# ============================================================

def main():
    # Ã¢ÂÂÃ¢ÂÂ AUTH GATE Ã¢ÂÂ deve ser a primeira coisa executada Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    # Se nÃÂ£o autenticado, mostra apenas a tela de login e para.
    autenticado = render_login()
    if not autenticado:
        st.stop()

    # Ã¢ÂÂÃ¢ÂÂ PÃÂ¡gina de administraÃÂ§ÃÂ£o (admin only) Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    if st.session_state.get("pagina_admin"):
        render_admin()
        st.stop()

    # Ã¢ÂÂÃ¢ÂÂ App principal (apenas para usuÃÂ¡rios autenticados) Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ
    # Bloqueia ediÃÂ§ÃÂ£o para viewers
    if is_viewer():
        st.info("Ã°ÂÂÂ VocÃÂª estÃÂ¡ em modo de visualizaÃÂ§ÃÂ£o. Contate o administrador para editar projetos.")

    sidebar_projetos()

    abas = st.tabs([
        "1. Projeto",
        "2. Solo (Wenner)",
        "3. Geometria",
        "4. Curto",
        "5. CÃÂ¡lculo",
        "6. RelatÃÂ³rio",
    ])
    with abas[0]: aba_projeto()
    with abas[1]: aba_solo()
    with abas[2]: aba_geometria()
    with abas[3]: aba_curto()
    with abas[4]: aba_calculo()
    with abas[5]: aba_relatorio()

    st.sidebar.divider()
    st.sidebar.caption(
        "BK Malha de Terra v2.0\n\n"
        "IEEE 80-2013 ÃÂ· NBR 15751 ÃÂ· NBR 7117\n"
        "Multi-tenant SaaS ÃÂ· BK Engenharia"
    )


if __name__ == "__main__":
    main()
