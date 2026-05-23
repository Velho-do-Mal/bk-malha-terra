"""
auth/auth.py
============

Autenticação e gerenciamento de sessão para o BK Malha de Terra SaaS.

Modelo:
    Tenant (empresa) → 1:N → Usuarios
    Cada usuário tem role: 'admin' | 'engenheiro' | 'viewer'

    - admin      : gerencia usuários do mesmo tenant, acessa tudo
    - engenheiro : cria/edita projetos, gera relatórios
    - viewer     : somente leitura

Uso no Streamlit:
    from auth.auth import verificar_sessao, login, logout

    # No topo de cada página/main():
    user = verificar_sessao()
    if not user:
        render_pagina_login()
        st.stop()
    tenant_id = user["tenant_id"]
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import bcrypt
import streamlit as st

from data.db import get_session
from data.models import Tenant, Usuario

# ─── Chaves de session_state ──────────────────────────────────────────────────
_KEY_AUTH    = "bk_autenticado"
_KEY_USER_ID = "bk_usuario_id"
_KEY_NOME    = "bk_usuario_nome"
_KEY_EMAIL   = "bk_usuario_email"
_KEY_ROLE    = "bk_usuario_role"
_KEY_CREA    = "bk_usuario_crea"
_KEY_TENANT  = "bk_tenant_id"
_KEY_EMPRESA = "bk_tenant_nome"
_KEY_PLANO   = "bk_tenant_plano"


# ─── Helpers de senha ────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    """Gera hash bcrypt da senha."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verifica_senha(senha: str, hash_armazenado: str) -> bool:
    """Verifica senha contra hash bcrypt armazenado."""
    try:
        return bcrypt.checkpw(
            senha.encode("utf-8"),
            hash_armazenado.encode("utf-8"),
        )
    except Exception:
        return False


def _senha_valida(senha: str) -> tuple[bool, str]:
    """Valida requisitos mínimos de senha."""
    if len(senha) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres."
    if not re.search(r"[A-Za-z]", senha):
        return False, "Senha deve conter pelo menos uma letra."
    if not re.search(r"\d", senha):
        return False, "Senha deve conter pelo menos um número."
    return True, ""


def _email_valido(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


# ─── Login / Logout ───────────────────────────────────────────────────────────

def login(email: str, senha: str) -> tuple[bool, str]:
    """
    Autentica email + senha.

    Returns:
        (True, "")         se autenticado
        (False, "mensagem") se falhou
    """
    email = email.strip().lower()
    if not email or not senha:
        return False, "Preencha email e senha."

    try:
        with get_session() as s:
            usuario = (
                s.query(Usuario)
                .filter_by(email=email, ativo=True)
                .first()
            )
            if not usuario:
                return False, "Usuário não encontrado ou inativo."

            if not verifica_senha(senha, usuario.senha_hash):
                return False, "Senha incorreta."

            tenant = s.query(Tenant).filter_by(id=usuario.tenant_id, ativo=True).first()
            if not tenant:
                return False, "Empresa não encontrada ou inativa."

            # Verifica trial expirado
            if tenant.plano == "trial" and tenant.trial_expira_em:
                if datetime.utcnow() > tenant.trial_expira_em:
                    return False, "Período de trial expirado. Entre em contato com a BK Engenharia."

            # Salvar última data de acesso
            usuario.ultimo_acesso = datetime.utcnow()

            # Preencher session_state
            st.session_state[_KEY_AUTH]    = True
            st.session_state[_KEY_USER_ID] = usuario.id
            st.session_state[_KEY_NOME]    = usuario.nome
            st.session_state[_KEY_EMAIL]   = usuario.email
            st.session_state[_KEY_ROLE]    = usuario.role
            st.session_state[_KEY_CREA]    = usuario.crea or ""
            st.session_state[_KEY_TENANT]  = tenant.id
            st.session_state[_KEY_EMPRESA] = tenant.nome_empresa
            st.session_state[_KEY_PLANO]   = tenant.plano

            return True, ""

    except Exception as e:
        return False, f"Erro de sistema: {e}"


def logout():
    """Limpa sessão e força reload."""
    for key in list(st.session_state.keys()):
        if key.startswith("bk_"):
            del st.session_state[key]
    # Limpa também o projeto atual
    for key in ["projeto_id", "projeto_nome"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def verificar_sessao() -> Optional[dict]:
    """
    Retorna dict com dados do usuário logado, ou None se não autenticado.

    Use no topo de cada função de aba/página:
        user = verificar_sessao()
        if not user: st.stop()
    """
    if not st.session_state.get(_KEY_AUTH):
        return None
    return {
        "usuario_id": st.session_state[_KEY_USER_ID],
        "nome":       st.session_state[_KEY_NOME],
        "email":      st.session_state[_KEY_EMAIL],
        "role":       st.session_state[_KEY_ROLE],
        "crea":       st.session_state.get(_KEY_CREA, ""),
        "tenant_id":  st.session_state[_KEY_TENANT],
        "empresa":    st.session_state[_KEY_EMPRESA],
        "plano":      st.session_state[_KEY_PLANO],
    }


def tenant_id_atual() -> Optional[int]:
    """Atalho: retorna tenant_id do usuário logado."""
    return st.session_state.get(_KEY_TENANT)


def usuario_id_atual() -> Optional[int]:
    """Atalho: retorna usuario_id do usuário logado."""
    return st.session_state.get(_KEY_USER_ID)


def is_admin() -> bool:
    """True se o usuário logado é admin do tenant."""
    return st.session_state.get(_KEY_ROLE) == "admin"


def is_viewer() -> bool:
    """True se o usuário logado é apenas viewer (somente leitura)."""
    return st.session_state.get(_KEY_ROLE) == "viewer"


# ─── Criação de tenant + admin (onboarding) ──────────────────────────────────

def registrar_empresa(
    nome_empresa: str,
    email_admin:  str,
    senha:        str,
    nome_admin:   str,
    crea_admin:   str = "",
) -> tuple[bool, str]:
    """
    Cria um novo tenant + usuário admin (fluxo de auto-cadastro).

    Returns:
        (True, "")         se criado com sucesso
        (False, "mensagem") se falhou
    """
    # Validações
    if not nome_empresa.strip():
        return False, "Nome da empresa é obrigatório."
    if not _email_valido(email_admin):
        return False, "E-mail inválido."
    if not nome_admin.strip():
        return False, "Nome do responsável é obrigatório."

    ok, msg = _senha_valida(senha)
    if not ok:
        return False, msg

    try:
        with get_session() as s:
            # Verifica e-mail duplicado
            existe = s.query(Usuario).filter_by(email=email_admin.strip().lower()).first()
            if existe:
                return False, "E-mail já cadastrado."

            # Cria tenant (plano trial — ativar pro após pagamento)
            from datetime import timedelta
            tenant = Tenant(
                nome_empresa   = nome_empresa.strip(),
                email_contato  = email_admin.strip().lower(),
                plano          = "trial",
                max_projetos   = 3,
                max_usuarios   = 2,
                trial_expira_em= datetime.utcnow() + timedelta(days=14),
                ativo          = True,
            )
            s.add(tenant)
            s.flush()  # gera tenant.id

            # Cria usuário admin
            admin = Usuario(
                tenant_id  = tenant.id,
                nome       = nome_admin.strip(),
                email      = email_admin.strip().lower(),
                senha_hash = hash_senha(senha),
                role       = "admin",
                crea       = crea_admin.strip() or None,
                ativo      = True,
            )
            s.add(admin)

        return True, ""

    except Exception as e:
        return False, f"Erro ao criar conta: {e}"


# ─── Gerenciamento de usuários (admin do tenant) ─────────────────────────────

def criar_usuario(
    tenant_id:  int,
    nome:       str,
    email:      str,
    senha:      str,
    role:       str = "engenheiro",
    crea:       str = "",
) -> tuple[bool, str]:
    """Cria usuário dentro de um tenant. Requer chamada por admin."""
    if not _email_valido(email):
        return False, "E-mail inválido."
    ok, msg = _senha_valida(senha)
    if not ok:
        return False, msg
    if role not in ("admin", "engenheiro", "viewer"):
        return False, "Role inválida."

    try:
        with get_session() as s:
            # Verifica limite do plano
            tenant = s.query(Tenant).filter_by(id=tenant_id).first()
            if not tenant:
                return False, "Tenant não encontrado."
            n_usuarios = s.query(Usuario).filter_by(tenant_id=tenant_id, ativo=True).count()
            if n_usuarios >= tenant.max_usuarios:
                return False, (
                    f"Limite de usuários do plano {tenant.plano} atingido "
                    f"({tenant.max_usuarios}). Faça upgrade para adicionar mais."
                )

            existe = s.query(Usuario).filter_by(email=email.strip().lower()).first()
            if existe:
                return False, "E-mail já cadastrado."

            u = Usuario(
                tenant_id  = tenant_id,
                nome       = nome.strip(),
                email      = email.strip().lower(),
                senha_hash = hash_senha(senha),
                role       = role,
                crea       = crea.strip() or None,
                ativo      = True,
            )
            s.add(u)

        return True, ""

    except Exception as e:
        return False, f"Erro: {e}"


def listar_usuarios_tenant(tenant_id: int) -> list[dict]:
    """Lista usuários ativos do tenant."""
    try:
        with get_session() as s:
            usuarios = (
                s.query(Usuario)
                .filter_by(tenant_id=tenant_id)
                .order_by(Usuario.nome)
                .all()
            )
            return [
                {
                    "id":            u.id,
                    "nome":          u.nome,
                    "email":         u.email,
                    "role":          u.role,
                    "crea":          u.crea or "",
                    "ativo":         u.ativo,
                    "ultimo_acesso": u.ultimo_acesso,
                }
                for u in usuarios
            ]
    except Exception:
        return []


def alterar_senha(usuario_id: int, senha_atual: str, nova_senha: str) -> tuple[bool, str]:
    """Permite que o usuário altere sua própria senha."""
    ok, msg = _senha_valida(nova_senha)
    if not ok:
        return False, msg

    try:
        with get_session() as s:
            u = s.query(Usuario).filter_by(id=usuario_id, ativo=True).first()
            if not u:
                return False, "Usuário não encontrado."
            if not verifica_senha(senha_atual, u.senha_hash):
                return False, "Senha atual incorreta."
            u.senha_hash = hash_senha(nova_senha)
        return True, ""
    except Exception as e:
        return False, f"Erro: {e}"


def desativar_usuario(tenant_id: int, usuario_id: int) -> tuple[bool, str]:
    """Admin desativa usuário do mesmo tenant."""
    try:
        with get_session() as s:
            u = s.query(Usuario).filter_by(id=usuario_id, tenant_id=tenant_id).first()
            if not u:
                return False, "Usuário não encontrado."
            # Não pode desativar o único admin
            if u.role == "admin":
                n_admins = (
                    s.query(Usuario)
                    .filter_by(tenant_id=tenant_id, role="admin", ativo=True)
                    .count()
                )
                if n_admins <= 1:
                    return False, "Não é possível desativar o único administrador."
            u.ativo = False
        return True, ""
    except Exception as e:
        return False, f"Erro: {e}"
