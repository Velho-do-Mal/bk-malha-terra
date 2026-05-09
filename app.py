"""
app.py
======

BK Malha de Terra - Aplicação Streamlit principal.

Estrutura em abas:
    1. Projeto      - identificação (cliente, número, revisão)
    2. Solo         - medições Wenner + estratificação
    3. Geometria    - dimensões SE, malha, brita, hastes
    4. Curto-circuito - 3I0, X/R, tempo, Sf
    5. Cálculo      - executa pipeline IEEE 80 e mostra resultados
    6. Relatório    - gera Word (.docx) - ATIVADO NA FATIA 4

Rodar:
    streamlit run app.py
"""

from __future__ import annotations

import io
import json
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

# ---- Core ----
from core.condutor import Material, dimensiona_condutor
from core.corrente import corrente_malha_ig
from core.geometria import gera_cabos_malha, posiciona_hastes
from core.resistencia import GeometriaMalha, calcula_resistencia_e_tensoes
from core.solo import (
    MedicaoWenner, estratifica_2_camadas, rho_equivalente_simplificado,
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
# CONFIGURAÇÃO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="BK Malha de Terra",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SIDEBAR - SELEÇÃO/CRIAÇÃO DE PROJETO
# ============================================================

def sidebar_projetos():
    st.sidebar.title("⚡ BK Malha de Terra")
    st.sidebar.caption("IEEE 80-2013 · NBR 15751 · NBR 7117")

    # Healthcheck do banco
    with st.sidebar.expander("🔌 Banco de dados", expanded=False):
        if st.button("Testar conexão"):
            r = testa_conexao()
            if r["status"] == "ok":
                st.success(f"OK · {r['schema']}")
                st.caption(r["versao_postgres"][:80])
            else:
                st.error(f"Erro: {r.get('erro', '?')}")

    st.sidebar.divider()
    st.sidebar.subheader("Projeto atual")

    # Lista projetos
    try:
        projetos = repo.lista_projetos(limit=50)
    except Exception as e:
        st.sidebar.error(f"Banco indisponível: {e}")
        projetos = []

    opcoes = ["➕ Novo projeto..."] + [
        f"#{p.id} · {p.numero_projeto} R{p.revisao} · {p.cliente[:30]}"
        for p in projetos
    ]
    escolha = st.sidebar.selectbox("Selecionar", opcoes, key="select_projeto")

    if escolha == "➕ Novo projeto...":
        st.session_state["projeto_id"] = None
    else:
        idx = opcoes.index(escolha) - 1
        st.session_state["projeto_id"] = projetos[idx].id

    if st.session_state.get("projeto_id"):
        if st.sidebar.button("🗑️ Excluir projeto", type="secondary"):
            repo.deleta_projeto(st.session_state["projeto_id"])
            st.session_state["projeto_id"] = None
            st.rerun()


# ============================================================
# ABA 1 - PROJETO
# ============================================================

def aba_projeto():
    st.header("1. Identificação do Projeto")

    pid = st.session_state.get("projeto_id")
    p = repo.busca_projeto(pid) if pid else None

    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input(
            "Cliente *", value=(p.cliente if p else ""), max_chars=200
        )
        nome = st.text_input(
            "Nome do projeto *", value=(p.nome_projeto if p else ""), max_chars=300
        )
        numero = st.text_input(
            "Número do projeto *", value=(p.numero_projeto if p else ""), max_chars=50
        )
        revisao = st.text_input(
            "Revisão", value=(p.revisao if p else "00"), max_chars=10
        )
    with col2:
        responsavel = st.text_input(
            "Responsável técnico", value=(p.responsavel_tecnico or "" if p else ""),
        )
        crea = st.text_input(
            "CREA do responsável", value=(p.crea_responsavel or "" if p else ""),
        )
        concessionaria = st.selectbox(
            "Concessionária",
            options=["", "Celesc", "Energisa", "Copel", "CPFL", "Enel",
                     "Neoenergia", "Equatorial", "Outra"],
            index=0,
        )
        data_calc = st.date_input(
            "Data do cálculo", value=(p.data_calculo if p else date.today())
        )

    obs = st.text_area("Observações", value=(p.observacoes or "" if p else ""))

    if st.button("💾 Salvar identificação", type="primary"):
        if not (cliente and nome and numero):
            st.error("Cliente, nome e número são obrigatórios.")
            return
        try:
            if pid:
                # Atualiza (criamos via cria_projeto pq não temos update direto)
                # Para v1 - simplificação: deletar e recriar mantendo id é complicado.
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
    st.header("2. Solo - Método de Wenner (NBR 7117)")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificação do projeto primeiro (aba 1).")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid)

    st.markdown("""
    Insira pelo menos **4 medições** com espaçamentos crescentes (recomendado:
    1, 2, 4, 8, 16, 32 m). O app calcula ρ aparente e ajusta um modelo de
    **2 camadas** por otimização (Sunde).
    """)

    # Carrega medições existentes ou template
    if p and p.medicoes_wenner:
        df_inicial = pd.DataFrame([
            {"Espaçamento a [m]": float(m.espacamento_m),
             "Resistência R [Ω]": float(m.resistencia_ohm)}
            for m in p.medicoes_wenner
        ])
    else:
        df_inicial = pd.DataFrame({
            "Espaçamento a [m]":  [1.0, 2.0, 4.0, 8.0, 16.0, 32.0],
            "Resistência R [Ω]":  [50.0, 25.0, 12.0, 6.0, 3.0, 1.5],
        })

    df_edit = st.data_editor(
        df_inicial,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Espaçamento a [m]": st.column_config.NumberColumn(
                format="%.2f", min_value=0.1, max_value=200.0
            ),
            "Resistência R [Ω]": st.column_config.NumberColumn(
                format="%.4f", min_value=0.001
            ),
        },
        key="editor_wenner",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧮 Calcular estratificação", type="primary"):
            try:
                medicoes = [
                    MedicaoWenner(
                        espacamento_m=float(row["Espaçamento a [m]"]),
                        resistencia_ohm=float(row["Resistência R [Ω]"]),
                    )
                    for _, row in df_edit.iterrows()
                    if row["Espaçamento a [m]"] > 0 and row["Resistência R [Ω]"] > 0
                ]
                if len(medicoes) < 3:
                    st.error("Insira pelo menos 3 medições válidas.")
                    return

                solo = estratifica_2_camadas(medicoes)
                st.session_state["solo"] = solo
                st.session_state["medicoes"] = medicoes

                # Persiste no banco
                repo.salva_medicoes_wenner(
                    pid,
                    [(m.espacamento_m, m.resistencia_ohm) for m in medicoes],
                )

                st.success("Estratificação calculada e salva.")
            except Exception as e:
                st.error(f"Erro: {e}")

    # Mostra resultados
    solo = st.session_state.get("solo")
    medicoes = st.session_state.get("medicoes")
    if solo and medicoes:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ρ₁", f"{solo.rho1:.0f} Ω·m")
        c2.metric("ρ₂", f"{solo.rho2:.0f} Ω·m")
        c3.metric("h₁", f"{solo.h1:.2f} m")
        c4.metric("Erro RMS", f"{solo.erro_rms:.2f}%")

        st.plotly_chart(plot_curva_wenner(medicoes, solo), use_container_width=True)

        if solo.erro_rms > 15:
            st.warning(
                f"Erro RMS de {solo.erro_rms:.1f}% é alto. Considere refazer "
                "as medições (várias direções, mesmo nível d'água) ou usar "
                "modelo de 3+ camadas em software dedicado."
            )


# ============================================================
# ABA 3 - GEOMETRIA
# ============================================================

def aba_geometria():
    st.header("3. Geometria, Brita e Hastes")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificação primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid)
    de = p.dados_entrada if p else None

    st.subheader("Dimensões da SE")
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
        "Espaçamento da malha principal D [m]",
        min_value=1.0, max_value=20.0,
        value=float(de.espac_malha_principal_m) if de else 5.0, step=0.5,
    )
    espac_juncao = col2.number_input(
        "Espaçamento da malha de junção (bordas) [m]",
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
        help="0.10m é o mínimo recomendado pela IEEE 80 §11.3",
    )
    brita_rho = col2.selectbox(
        "Resistividade da brita [Ω·m]",
        options=[1200, 2500, 3000, 5000, 10000],
        index=2,  # 3000
        format_func=lambda v: {
            1200: "1200 (brita molhada)",
            2500: "2500 (brita média)",
            3000: "3000 (brita seca - padrão IEEE 80)",
            5000: "5000 (brita lavada)",
            10000: "10000 (asfalto)",
        }[v],
    )

    st.subheader("Hastes copperweld")
    col1, col2 = st.columns(2)
    haste_l = col1.number_input(
        "Comprimento da haste Lr [m]",
        min_value=1.5, max_value=10.0,
        value=float(de.haste_comprimento_m) if de else 3.0, step=0.5,
    )
    haste_d_opt = col2.selectbox(
        "Diâmetro da haste",
        options=[12.7, 14.3, 15.875, 19.05],
        index=2,  # 5/8"
        format_func=lambda v: {
            12.7: '1/2" (12.7 mm)',
            14.3: '9/16" (14.3 mm)',
            15.875: '5/8" (15.875 mm) - padrão',
            19.05: '3/4" (19.05 mm)',
        }[v],
    )

    if st.button("💾 Salvar geometria", type="primary"):
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
                # placeholders - serão preenchidos na aba curto
                campos_existentes_outros = {
                    "i_falta_3i0_ka": 5.0,
                    "tempo_eliminacao_s": 0.5,
                    "sf_div_corrente": 0.6,
                    "xr_ratio": 10.0,
                    "peso_pessoa_kg": 50,
                }

            repo.salva_dados_entrada(
                pid,
                largura_m=largura,
                comprimento_m=comprimento,
                profundidade_malha_m=profundidade,
                espac_malha_principal_m=espac_principal,
                espac_malha_juncao_m=espac_juncao,
                brita_espessura_m=brita_h,
                brita_resistividade_ohm=float(brita_rho),
                haste_comprimento_m=haste_l,
                haste_diametro_mm=float(haste_d_opt),
                **campos_existentes_outros,
            )
            st.success("Geometria salva.")
        except Exception as e:
            st.error(f"Erro: {e}")

    # Pré-visualização da malha
    st.subheader("Pré-visualização")
    cabos, n_h, n_v = gera_cabos_malha(
        largura, comprimento, espac_principal, espac_juncao
    )
    fig = plot_planta_malha(largura, comprimento, cabos, hastes=[],
                              titulo=f"Pré-visualização ({n_h}×{n_v} cabos)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Cabos paralelos a L: {n_h} · Cabos paralelos a W: {n_v} · "
        f"Comprimento total estimado: {sum(np.hypot(c[2]-c[0], c[3]-c[1]) for c in cabos):.0f} m"
    )


# ============================================================
# ABA 4 - CURTO-CIRCUITO
# ============================================================

def aba_curto():
    st.header("4. Dados Elétricos do Curto-Circuito")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificação primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid)
    de = p.dados_entrada if p else None

    st.markdown("""
    Dados do estudo de curto-circuito (extrair do estudo elétrico). Para SE
    de distribuição típica, use a corrente fase-terra no barramento de AT.
    """)

    col1, col2 = st.columns(2)
    i_falta = col1.number_input(
        "Corrente simétrica de falta 3I₀ [kA]",
        min_value=0.5, max_value=80.0,
        value=float(de.i_falta_3i0_ka) if de else 8.0, step=0.5,
    )
    tempo = col2.number_input(
        "Tempo de eliminação tc [s]",
        min_value=0.05, max_value=3.0,
        value=float(de.tempo_eliminacao_s) if de else 0.5, step=0.05,
        help="Proteção primária + tempo de abertura do disjuntor",
    )

    col1, col2 = st.columns(2)
    sf = col1.slider(
        "Fator de divisão Sf",
        min_value=0.05, max_value=1.0,
        value=float(de.sf_div_corrente) if de else 0.6, step=0.05,
        help="Tabela 10 IEEE 80. SE com cabo guarda + neutro: 0.4-0.6. Isolada: 1.0.",
    )
    xr = col2.number_input(
        "Relação X/R no ponto de falta",
        min_value=0.5, max_value=80.0,
        value=float(de.xr_ratio) if de and de.xr_ratio else 10.0, step=1.0,
    )

    peso = st.radio(
        "Peso da pessoa (Dalziel)",
        options=[50, 70],
        index=0 if (not de or de.peso_pessoa_kg == 50) else 1,
        horizontal=True,
        help="50kg é mais conservador, padrão das concessionárias BR.",
    )

    if st.button("💾 Salvar dados elétricos", type="primary"):
        try:
            # mantém geometria existente
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
                i_falta_3i0_ka=i_falta,
                tempo_eliminacao_s=tempo,
                sf_div_corrente=sf,
                xr_ratio=xr,
                peso_pessoa_kg=peso,
                **campos_geom,
            )
            st.success("Dados elétricos salvos.")
        except Exception as e:
            st.error(f"Erro: {e}")


# ============================================================
# ABA 5 - CÁLCULO E RESULTADOS
# ============================================================

def aba_calculo():
    st.header("5. Cálculo IEEE 80 e Resultados")

    if not st.session_state.get("projeto_id"):
        st.warning("Salve a identificação primeiro.")
        return

    pid = st.session_state["projeto_id"]
    p = repo.busca_projeto(pid)

    if not p or not p.dados_entrada or not p.medicoes_wenner:
        st.warning("Preencha solo (aba 2), geometria (aba 3) e dados elétricos (aba 4).")
        return

    de = p.dados_entrada

    st.subheader("Pipeline de cálculo")
    st.caption(
        "Solo (Sunde) → IG (eq.70) → Condutor (eq.37) → "
        "Eadm (eqs.30-33) → Rg (Sverak/Schwarz) → Em/Es → Verificação"
    )

    if st.button("⚡ Executar cálculo", type="primary"):
        with st.spinner("Calculando..."):
            try:
                # 1. Solo
                medicoes = [
                    MedicaoWenner(float(m.espacamento_m), float(m.resistencia_ohm))
                    for m in p.medicoes_wenner
                ]
                solo = estratifica_2_camadas(medicoes)
                rho_eq = rho_equivalente_simplificado(solo, float(de.haste_comprimento_m))

                # 2. Corrente
                corrente = corrente_malha_ig(
                    i_falta_3i0_a=float(de.i_falta_3i0_ka) * 1000.0,
                    sf_div_corrente=float(de.sf_div_corrente),
                    xr_ratio=float(de.xr_ratio),
                    tf_s=float(de.tempo_eliminacao_s),
                )

                # 3. Condutor
                cond = dimensiona_condutor(
                    corrente_a=corrente.ig_a,
                    tempo_s=float(de.tempo_eliminacao_s),
                    material=Material(de.condutor_material),
                    temperatura_max_c=250.0,
                )

                # 4. Tensões admissíveis
                tensoes_adm = calcula_tensoes_admissiveis(
                    rho_solo=solo.rho1,
                    rho_brita=float(de.brita_resistividade_ohm),
                    h_brita=float(de.brita_espessura_m),
                    tempo_s=float(de.tempo_eliminacao_s),
                    peso_kg=int(de.peso_pessoa_kg),
                )

                # 5. Geometria + iteração
                geom_ini = GeometriaMalha(
                    largura_m=float(de.largura_m),
                    comprimento_m=float(de.comprimento_m),
                    profundidade_m=float(de.profundidade_malha_m),
                    espac_malha_m=float(de.espac_malha_principal_m),
                    bitola_cabo_mm2=cond.bitola_adotada_mm2,
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

                # Cabos para visualização
                cabos, _, _ = gera_cabos_malha(
                    float(de.largura_m), float(de.comprimento_m),
                    float(de.espac_malha_principal_m),
                    float(de.espac_malha_juncao_m or 2.5),
                )

                # Salva no banco
                repo.salva_resultado(
                    pid,
                    rho1_ohm_m=solo.rho1, rho2_ohm_m=solo.rho2,
                    h1_m=solo.h1, rho_equivalente=rho_eq,
                    bitola_calculada_mm2=cond.bitola_calculada_mm2,
                    bitola_adotada_mm2=cond.bitola_adotada_mm2,
                    cs_brita=tensoes_adm.cs_brita,
                    etoque_admissivel_v=tensoes_adm.etoque_v,
                    epasso_admissivel_v=tensoes_adm.epasso_v,
                    df_decremento=corrente.df_decremento,
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

                # Guarda em sessão para mostrar
                st.session_state["calc"] = {
                    "solo": solo, "rho_eq": rho_eq,
                    "corrente": corrente, "cond": cond,
                    "tensoes_adm": tensoes_adm,
                    "iteracao": iteracao,
                    "hastes": hastes, "cabos": cabos,
                    "geom_final": iteracao.geometria_final,
                }
                st.success("Cálculo executado e salvo.")
            except Exception as e:
                st.error(f"Erro no cálculo: {e}")
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
    st.subheader("📊 Resultado final")

    # Status grande
    if verif.atende_geral:
        st.success("✅ MALHA ATENDE OS CRITÉRIOS DA IEEE 80-2013")
    else:
        st.error("❌ MALHA NÃO ATENDE - revisar projeto")

    # Métricas principais
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rg", f"{res.rg_adotado_ohm:.2f} Ω",
               help="Schwarz (mais preciso que Sverak)")
    c2.metric("GPR", f"{res.gpr_v:.0f} V")
    c3.metric("Nº de hastes", f"{calc['geom_final'].num_hastes}")
    c4.metric("Iterações", f"{iteracao.iteracoes}")

    c1, c2 = st.columns(2)
    c1.metric(
        "Em (toque)",
        f"{res.em_v:.0f} V",
        f"adm {tensoes_adm.etoque_v:.0f} V · margem {verif.margem_toque_pct:+.1f}%",
        delta_color=("normal" if verif.atende_toque else "inverse"),
    )
    c2.metric(
        "Es (passo)",
        f"{res.es_v:.0f} V",
        f"adm {tensoes_adm.epasso_v:.0f} V · margem {verif.margem_passo_pct:+.1f}%",
        delta_color=("normal" if verif.atende_passo else "inverse"),
    )

    # Observações
    obs_all = (calc["corrente"].observacoes + calc["cond"].observacoes +
               tensoes_adm.observacoes + verif.observacoes)
    if obs_all:
        with st.expander("⚠️ Observações técnicas"):
            for o in obs_all:
                st.markdown(f"- {o}")

    # Gráficos
    st.divider()
    st.subheader("📈 Visualizações")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Verificação", "Planta da malha", "Mapa 3D de tensão", "Iteração"]
    )

    with tab1:
        st.plotly_chart(
            plot_verificacao(res.em_v, res.es_v,
                              tensoes_adm.etoque_v, tensoes_adm.epasso_v),
            use_container_width=True,
        )

    with tab2:
        de = repo.busca_projeto(pid).dados_entrada
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
        de = repo.busca_projeto(pid).dados_entrada
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
            "⚠️ Aproximação visual da distribuição de tensão. "
            "Cálculo rigoroso do perfil de tensão requer FEM (CDEGS, COMSOL)."
        )

    with tab4:
        st.plotly_chart(
            plot_iteracao_hastes(iteracao.historico,
                                  tensoes_adm.etoque_v,
                                  tensoes_adm.epasso_v),
            use_container_width=True,
        )


# ============================================================
# ABA 6 - RELATÓRIO WORD
# ============================================================

def aba_relatorio():
    st.header("6. Relatório Word (.docx)")

    pid = st.session_state.get("projeto_id")
    if not pid:
        st.warning("Selecione ou crie um projeto primeiro.")
        return

    p = repo.busca_projeto(pid)
    if not p or not p.resultado or not p.dados_entrada:
        st.warning("Execute o cálculo (aba 5) antes de gerar o relatório.")
        return

    # Resumo do que será gerado
    st.markdown(f"""
    O relatório conterá:
    
    1. **Capa** com identificação ({p.cliente} · {p.numero_projeto} R{p.revisao})
    2. **Objetivo** do estudo
    3. **Metodologia** com equações IEEE 80/NBR 15751 e práticas construtivas
    4. **Dados de entrada** (solo, geometria, brita, hastes, curto)
    5. **Resultados** com tabelas e gráficos exportados
    6. **Conclusão** ({"✓ Atende" if p.resultado.atende_geral else "✗ Não atende"})
    7. **Referências** bibliográficas
    """)

    # Verifica se há cálculo em sessão para exportar gráficos
    calc = st.session_state.get("calc")
    if not calc:
        st.warning(
            "⚠️ Os gráficos só são exportados se o cálculo foi executado "
            "**nesta sessão** (aba 5). Execute o cálculo novamente para "
            "incluir gráficos no relatório."
        )

    if st.button("📄 Gerar relatório Word", type="primary"):
        from relatorio.gerador_word import gera_relatorio_word, nome_arquivo_padrao
        with st.spinner("Gerando relatório..."):
            try:
                # Exporta gráficos como PNG
                imagens = {}
                if calc:
                    de = p.dados_entrada
                    res = calc["iteracao"].resultado
                    tensoes_adm = calc["tensoes_adm"]
                    try:
                        # 1. Curva Wenner
                        from ui.visualizacoes import (
                            plot_curva_wenner, plot_planta_malha,
                            plot_mapa_tensao_3d, plot_verificacao,
                        )
                        fig_w = plot_curva_wenner(calc["solo"] and st.session_state.get("medicoes") or [], calc["solo"]) \
                            if st.session_state.get("medicoes") else None
                        if fig_w:
                            imagens["wenner"] = fig_w.to_image(format="png", width=900, height=500, scale=2)

                        # 2. Planta
                        fig_p = plot_planta_malha(
                            float(de.largura_m), float(de.comprimento_m),
                            calc["cabos"], calc["hastes"],
                            titulo=f"Malha proposta - {calc['geom_final'].num_hastes} hastes",
                        )
                        imagens["planta"] = fig_p.to_image(format="png", width=900, height=700, scale=2)

                        # 3. Verificação
                        fig_v = plot_verificacao(
                            res.em_v, res.es_v,
                            tensoes_adm.etoque_v, tensoes_adm.epasso_v,
                        )
                        imagens["verif"] = fig_v.to_image(format="png", width=900, height=500, scale=2)

                        # 4. Mapa 3D
                        fig_3d = plot_mapa_tensao_3d(
                            float(de.largura_m), float(de.comprimento_m),
                            res.rg_adotado_ohm, calc["corrente"].ig_a,
                            res.em_v, tensoes_adm.etoque_v,
                        )
                        imagens["mapa3d"] = fig_3d.to_image(format="png", width=900, height=600, scale=2)
                    except Exception as e:
                        st.warning(
                            f"Não foi possível exportar gráficos como imagem: {e}. "
                            "Instale `kaleido` (já está em requirements.txt). "
                            "Relatório será gerado sem figuras."
                        )

                # Logo BK (se existir)
                logo = os.getenv("BK_LOGO_PATH", "assets/bk_logo.png")
                logo_path = logo if os.path.exists(logo) else None

                # Gera doc
                docx_bytes = gera_relatorio_word(p, imagens, logo_path)
                nome_arq = nome_arquivo_padrao(p)

                # Registra no banco
                repo.registra_relatorio(pid, nome_arq, p.responsavel_tecnico)

                # Disponibiliza download
                st.success(f"✅ Relatório gerado ({len(docx_bytes)/1024:.0f} KB)")
                st.download_button(
                    label=f"⬇️ Baixar {nome_arq}",
                    data=docx_bytes,
                    file_name=nome_arq,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {e}")
                import traceback
                st.code(traceback.format_exc())

    # Histórico de relatórios gerados
    if p.relatorios:
        st.divider()
        st.subheader("📁 Histórico de relatórios gerados")
        for r in sorted(p.relatorios, key=lambda x: x.gerado_em, reverse=True):
            st.text(
                f"  {r.gerado_em.strftime('%d/%m/%Y %H:%M')} — "
                f"{r.nome_arquivo}"
                + (f" (por {r.gerado_por})" if r.gerado_por else "")
            )


# ============================================================
# MAIN
# ============================================================

def main():
    sidebar_projetos()

    abas = st.tabs([
        "1. Projeto",
        "2. Solo (Wenner)",
        "3. Geometria",
        "4. Curto",
        "5. Cálculo",
        "6. Relatório",
    ])
    with abas[0]: aba_projeto()
    with abas[1]: aba_solo()
    with abas[2]: aba_geometria()
    with abas[3]: aba_curto()
    with abas[4]: aba_calculo()
    with abas[5]: aba_relatorio()

    st.sidebar.divider()
    st.sidebar.caption(
        "BK Malha de Terra v1.0\n\n"
        "IEEE 80-2013 · NBR 15751 · NBR 7117"
    )


if __name__ == "__main__":
    main()
