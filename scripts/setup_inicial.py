#!/usr/bin/env python3
"""
scripts/setup_inicial.py
========================

Inicializa o banco e cria o primeiro tenant + admin.
Executar UMA VEZ no primeiro deploy em produção.

Uso:
    python scripts/setup_inicial.py

O script pergunta os dados interativamente ou lê de variáveis de ambiente:
    BK_ADMIN_EMPRESA, BK_ADMIN_EMAIL, BK_ADMIN_SENHA, BK_ADMIN_NOME
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from data.db import inicializa_banco, testa_conexao
from auth.auth import registrar_empresa, hash_senha
from data.db import get_session
from data.models import Tenant, Usuario


def main():
    print("=" * 60)
    print("BK Malha de Terra v2 — Setup inicial")
    print("=" * 60)

    # 1. Testar conexão
    print("\n1. Testando conexão com o banco...")
    r = testa_conexao()
    if r["status"] != "ok":
        print(f"❌ Banco indisponível: {r.get('erro')}")
        sys.exit(1)
    print(f"   ✅ {r['backend']} conectado ({r['tabelas_existentes']} tabelas)")

    # 2. Inicializar tabelas
    print("\n2. Criando tabelas (se não existirem)...")
    try:
        resultado = inicializa_banco(forcar=False)
        print(f"   ✅ {resultado['n_tabelas']} tabelas no banco")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        sys.exit(1)

    # 3. Verificar se já existe algum tenant
    with get_session() as s:
        n_tenants = s.query(Tenant).count()

    if n_tenants > 0:
        print(f"\n⚠️  Já existem {n_tenants} tenant(s) no banco.")
        resp = input("   Criar outro tenant admin mesmo assim? (s/N): ").strip().lower()
        if resp != "s":
            print("   Abortado.")
            sys.exit(0)

    # 4. Coletar dados do primeiro admin
    print("\n3. Criar primeiro tenant e administrador:")
    empresa = os.getenv("BK_ADMIN_EMPRESA") or input("   Nome da empresa: ").strip()
    nome    = os.getenv("BK_ADMIN_NOME")    or input("   Nome do admin: ").strip()
    email   = os.getenv("BK_ADMIN_EMAIL")   or input("   E-mail do admin: ").strip()
    senha   = os.getenv("BK_ADMIN_SENHA")   or input("   Senha (min 8 chars + número): ")

    if not all([empresa, nome, email, senha]):
        print("❌ Todos os campos são obrigatórios.")
        sys.exit(1)

    # 5. Criar
    ok, msg = registrar_empresa(
        nome_empresa=empresa,
        email_admin=email,
        senha=senha,
        nome_admin=nome,
    )

    if not ok:
        print(f"\n❌ Erro ao criar: {msg}")
        sys.exit(1)

    # 6. Mudar plano trial → enterprise (primeiro setup é a própria BK)
    with get_session() as s:
        t = s.query(Tenant).filter_by(email_contato=email.lower()).first()
        if t:
            t.plano = "enterprise"
            t.max_projetos = 9999
            t.max_usuarios = 999
            t.trial_expira_em = None

    print(f"""
✅ Setup concluído com sucesso!

   Empresa : {empresa}
   Admin   : {nome} ({email})
   Plano   : enterprise (sem limite de projetos/usuários)

   Próximos passos:
   1. Deploy no Railway: git push
   2. Acesse a URL do app e faça login com {email}
   3. Crie usuários para a equipe em "Gerenciar usuários"
   4. Para novos clientes: eles se cadastram via "Criar conta"
      (plano trial 14 dias) e você ativa o plano pro manualmente.
""")


if __name__ == "__main__":
    main()
