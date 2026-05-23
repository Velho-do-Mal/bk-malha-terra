"""
auth/pagina_login.py
====================

Renderiza a tela de login/cadastro do BK Malha de Terra SaaS.
Chamada no topo do main() antes de qualquer conteúdo do app.
"""

from __future__ import annotations

import streamlit as st
from auth.auth import login, registrar_empresa, verificar_sessao, logout


def render_login() -> bool:
    """
    Renderiza login/cadastro.
    Retorna True se o usuário está autenticado após a interação.
    """
    # Já autenticado?
    if verificar_sessao():
        return True

    # Header
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1F497D 0%, #2E75B6 100%);
        padding: 40px 24px 32px; border-radius: 12px;
        text-align: center; margin-bottom: 32px;
    ">
        <div style="font-size: 3rem; margin-bottom: 8px;">⚡</div>
        <h1 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 700;">
            BK Malha de Terra
        </h1>
        <p style="color: #cce0f0; margin: 8px 0 0; font-size: 0.95rem;">
            Dimensionamento de malhas de aterramento · IEEE 80 · NBR 15751
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_center = st.columns([1, 2, 1])[1]

    with col_center:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "🏢 Criar conta"])

        # ── TAB LOGIN ────────────────────────────────────────────────────────
        with tab_login:
            st.markdown("#### Acesso ao sistema")
            with st.form("form_login", clear_on_submit=False):
                email = st.text_input("E-mail", placeholder="engenheiro@empresa.com.br")
                senha = st.text_input("Senha", type="password")
                entrar = st.form_submit_button("Entrar →", use_container_width=True, type="primary")

            if entrar:
                if not email or not senha:
                    st.error("Preencha e-mail e senha.")
                else:
                    ok, msg = login(email, senha)
                    if ok:
                        st.success("Login realizado!")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # ── TAB CADASTRO ─────────────────────────────────────────────────────
        with tab_cadastro:
            st.markdown("#### Criar conta — trial 14 dias grátis")
            st.caption("Até 3 projetos e 2 usuários durante o trial. Plano Pro para uso comercial.")

            with st.form("form_cadastro", clear_on_submit=True):
                nome_empresa = st.text_input("Nome da empresa *", placeholder="BK Engenharia")
                col1, col2 = st.columns(2)
                nome_admin = col1.text_input("Seu nome *", placeholder="Márcio Knopp")
                crea       = col2.text_input("CREA", placeholder="PR-32397/D")
                email_adm  = st.text_input("E-mail *", placeholder="marcio@bkengenharia.com.br")
                col3, col4 = st.columns(2)
                senha_nov  = col3.text_input("Senha *", type="password",
                                              help="Mínimo 8 caracteres, letras e números")
                senha_conf = col4.text_input("Confirmar senha *", type="password")
                criar = st.form_submit_button("Criar conta →", use_container_width=True, type="primary")

            if criar:
                if senha_nov != senha_conf:
                    st.error("Senhas não conferem.")
                else:
                    ok, msg = registrar_empresa(
                        nome_empresa=nome_empresa,
                        email_admin=email_adm,
                        senha=senha_nov,
                        nome_admin=nome_admin,
                        crea_admin=crea,
                    )
                    if ok:
                        st.success("✅ Conta criada! Faça login na aba 'Entrar'.")
                    else:
                        st.error(f"❌ {msg}")

    st.markdown("---")
    st.caption(
        "BK Engenharia e Tecnologia · "
        "Dúvidas: contato@bkengenharia.com.br"
    )
    return False


def render_sidebar_usuario():
    """Renderiza info do usuário logado na sidebar."""
    sess = verificar_sessao()
    if not sess:
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{sess['nome']}**")
    st.sidebar.caption(f"📧 {sess['email']}")
    st.sidebar.caption(f"🏢 {sess['empresa']}")
    st.sidebar.caption(f"📋 Plano: **{sess['plano'].upper()}**")
    if sess["crea"]:
        st.sidebar.caption(f"🔖 CREA: {sess['crea']}")

    if sess["role"] == "admin":
        if st.sidebar.button("👥 Gerenciar usuários", use_container_width=True):
            st.session_state["pagina_admin"] = True
            st.rerun()

    if st.sidebar.button("🚪 Sair", use_container_width=True):
        logout()
