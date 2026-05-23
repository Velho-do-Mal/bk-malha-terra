"""
auth/pagina_admin.py
====================
Tela de gerenciamento de usuários (acessível apenas por admins do tenant).
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st
import pandas as pd

from auth.auth import (
    criar_usuario, listar_usuarios_tenant, desativar_usuario,
    alterar_senha, is_admin, verificar_sessao, tenant_id_atual, usuario_id_atual,
)
from data.repository import info_tenant


def render_admin():
    """Renderiza a página de administração do tenant."""
    sess = verificar_sessao()
    if not sess or not is_admin():
        st.error("Acesso restrito a administradores.")
        return

    tenant_id = sess["tenant_id"]
    info = info_tenant(tenant_id) or {}

    st.header("👥 Gerenciamento da Empresa")

    # ── Resumo do plano ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plano atual", info.get("plano_label", "—"))
    c2.metric("Projetos", f"{info.get('n_projetos',0)} / {info.get('max_projetos','∞')}")
    c3.metric("Usuários", f"{info.get('n_usuarios',0)} / {info.get('max_usuarios','∞')}")
    trial = info.get("trial_expira")
    if trial and info.get("plano") == "trial":
        dias = (trial - datetime.utcnow()).days
        cor = "normal" if dias > 5 else "inverse"
        c4.metric("Trial expira em", f"{dias} dias", delta_color=cor)

    st.markdown("---")

    # ── Lista de usuários ─────────────────────────────────────────────────────
    st.subheader("Usuários da empresa")
    usuarios = listar_usuarios_tenant(tenant_id)

    if usuarios:
        df = pd.DataFrame([
            {
                "Nome":          u["nome"],
                "E-mail":        u["email"],
                "Perfil":        u["role"],
                "CREA":          u["crea"] or "—",
                "Ativo":         "✅" if u["ativo"] else "❌",
                "Último acesso": u["ultimo_acesso"].strftime("%d/%m/%Y %H:%M")
                                 if u["ultimo_acesso"] else "Nunca",
                "_id":           u["id"],
            }
            for u in usuarios
        ])
        st.dataframe(df.drop(columns=["_id"]), use_container_width=True, hide_index=True)

        # Desativar usuário
        with st.expander("🗑️ Desativar usuário"):
            opcoes = {f"{u['nome']} ({u['email']})": u["id"]
                      for u in usuarios if u["id"] != usuario_id_atual()}
            if opcoes:
                sel = st.selectbox("Selecionar usuário", list(opcoes.keys()))
                if st.button("Desativar", type="secondary"):
                    ok, msg = desativar_usuario(tenant_id, opcoes[sel])
                    if ok:
                        st.success("Usuário desativado.")
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.caption("Nenhum outro usuário para desativar.")
    else:
        st.info("Nenhum usuário encontrado.")

    st.markdown("---")

    # ── Criar novo usuário ────────────────────────────────────────────────────
    st.subheader("Convidar novo usuário")
    with st.form("form_novo_usuario"):
        col1, col2 = st.columns(2)
        nome_u  = col1.text_input("Nome completo *")
        crea_u  = col2.text_input("CREA (opcional)")
        email_u = st.text_input("E-mail *")
        col3, col4 = st.columns(2)
        role_u  = col3.selectbox("Perfil", ["engenheiro", "viewer", "admin"])
        senha_u = col4.text_input("Senha inicial *", type="password",
                                   help="Mínimo 8 caracteres, letras e números")
        criar = st.form_submit_button("Criar usuário →", type="primary")

    if criar:
        ok, msg = criar_usuario(
            tenant_id=tenant_id,
            nome=nome_u, email=email_u,
            senha=senha_u, role=role_u, crea=crea_u,
        )
        if ok:
            st.success(f"✅ Usuário {nome_u} criado com sucesso!")
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    st.markdown("---")

    # ── Alterar minha senha ───────────────────────────────────────────────────
    st.subheader("🔒 Alterar minha senha")
    with st.form("form_senha"):
        s_atual = st.text_input("Senha atual", type="password")
        col5, col6 = st.columns(2)
        s_nova  = col5.text_input("Nova senha", type="password")
        s_conf  = col6.text_input("Confirmar nova senha", type="password")
        alterar = st.form_submit_button("Alterar senha →")

    if alterar:
        if s_nova != s_conf:
            st.error("Novas senhas não conferem.")
        else:
            ok, msg = alterar_senha(usuario_id_atual(), s_atual, s_nova)
            if ok:
                st.success("✅ Senha alterada com sucesso!")
            else:
                st.error(f"❌ {msg}")

    if st.button("← Voltar ao app"):
        if "pagina_admin" in st.session_state:
            del st.session_state["pagina_admin"]
        st.rerun()
