-- =========================================================
-- BK Malha de Terra - Migration 002 - Multi-Tenancy
-- =========================================================
-- Como rodar:
--   psql "$DATABASE_URL" -f migrations/002_multitenancy.sql
--
-- Adiciona:
--   - tenants      : empresas clientes (um tenant = uma empresa)
--   - usuarios     : usuários por tenant com roles e auth
--   - Altera projetos: tenant_id + criado_por_id
--   - Altera dados_entrada: cp_crescimento (fator P0 do relatório)
-- =========================================================

SET search_path TO bk_malha_terra;

-- ---------------------------------------------------------
-- Tabela: tenants (empresas clientes)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id                  SERIAL PRIMARY KEY,
    nome_empresa        VARCHAR(300) NOT NULL,
    cnpj                VARCHAR(18),
    email_contato       VARCHAR(254) NOT NULL UNIQUE,
    telefone            VARCHAR(20),
    plano               VARCHAR(20)  NOT NULL DEFAULT 'pro'
                            CHECK (plano IN ('trial','pro','enterprise')),
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    max_projetos        INTEGER NOT NULL DEFAULT 50,
    max_usuarios        INTEGER NOT NULL DEFAULT 5,
    trial_expira_em     TIMESTAMP,
    criado_em           TIMESTAMP NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email_contato);
CREATE INDEX IF NOT EXISTS idx_tenants_plano ON tenants(plano);

COMMENT ON TABLE tenants IS
    'Empresas clientes do BK Malha de Terra (modelo SaaS multi-tenant).';

-- ---------------------------------------------------------
-- Tabela: usuarios
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    nome                VARCHAR(200) NOT NULL,
    email               VARCHAR(254) NOT NULL UNIQUE,
    senha_hash          VARCHAR(72)  NOT NULL,   -- bcrypt 60 chars + margem
    role                VARCHAR(20)  NOT NULL DEFAULT 'engenheiro'
                            CHECK (role IN ('admin','engenheiro','viewer')),
    crea                VARCHAR(50),
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em           TIMESTAMP NOT NULL DEFAULT NOW(),
    ultimo_acesso       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant  ON usuarios(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_email   ON usuarios(email);

COMMENT ON TABLE usuarios IS
    'Usuários por tenant. role admin pode gerenciar usuários do mesmo tenant.';

-- ---------------------------------------------------------
-- Altera: projetos → adiciona tenant_id + criado_por_id
-- ---------------------------------------------------------
ALTER TABLE projetos
    ADD COLUMN IF NOT EXISTS tenant_id      INTEGER REFERENCES tenants(id)  ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS criado_por_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;

-- Para instalações existentes: cria um tenant padrão e migra projetos
DO $$
DECLARE
    v_tenant_id INTEGER;
BEGIN
    -- Só migra se existirem projetos sem tenant
    IF EXISTS (SELECT 1 FROM projetos WHERE tenant_id IS NULL LIMIT 1) THEN
        -- Cria tenant "BK Engenharia" padrão para migração
        INSERT INTO tenants (nome_empresa, email_contato, plano, max_projetos, max_usuarios)
        VALUES ('BK Engenharia (migração)', 'admin@bkengenharia.com.br', 'enterprise', 9999, 999)
        ON CONFLICT (email_contato) DO NOTHING
        RETURNING id INTO v_tenant_id;

        IF v_tenant_id IS NULL THEN
            SELECT id INTO v_tenant_id FROM tenants
            WHERE email_contato = 'admin@bkengenharia.com.br';
        END IF;

        -- Migra projetos órfãos para o tenant padrão
        UPDATE projetos SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;

        RAISE NOTICE 'Migrados projetos para tenant_id=%', v_tenant_id;
    END IF;
END $$;

-- Agora torna obrigatório (após migração)
ALTER TABLE projetos
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_projetos_tenant ON projetos(tenant_id);

-- Remove constraint única de numero_projeto+revisao (era global, agora é por tenant)
ALTER TABLE projetos DROP CONSTRAINT IF EXISTS uk_projeto_revisao;
ALTER TABLE projetos ADD CONSTRAINT uk_projeto_revisao_tenant
    UNIQUE (tenant_id, numero_projeto, revisao);

-- ---------------------------------------------------------
-- Altera: dados_entrada → adiciona cp_crescimento (P0 do relatório)
-- ---------------------------------------------------------
ALTER TABLE dados_entrada
    ADD COLUMN IF NOT EXISTS cp_crescimento NUMERIC(4,2) NOT NULL DEFAULT 1.00;

COMMENT ON COLUMN dados_entrada.cp_crescimento IS
    'Fator de crescimento da corrente de falta (projeção futura). '
    'IEEE 80 §15 recomenda usar corrente máxima futura. '
    'Cp = 1.0 = sem crescimento, 1.2 = crescimento conservador.';

-- ---------------------------------------------------------
-- Índices adicionais de performance
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_projetos_criado_por ON projetos(criado_por_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_role       ON usuarios(tenant_id, role);

-- ---------------------------------------------------------
-- View: projetos_completos (facilita queries no app)
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW vw_projetos_completos AS
SELECT
    p.*,
    t.nome_empresa,
    t.plano AS tenant_plano,
    u.nome  AS criado_por_nome,
    u.email AS criado_por_email
FROM projetos p
JOIN tenants  t ON t.id = p.tenant_id
LEFT JOIN usuarios u ON u.id = p.criado_por_id;

-- ---------------------------------------------------------
-- Função utilitária: conta projetos por tenant
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_conta_projetos_tenant(p_tenant_id INTEGER)
RETURNS INTEGER AS $$
    SELECT COUNT(*)::INTEGER FROM projetos WHERE tenant_id = p_tenant_id;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------
-- Atualiza timestamp automaticamente
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_atualiza_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tenants_updated ON tenants;
CREATE TRIGGER trg_tenants_updated
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION fn_atualiza_timestamp();

-- =========================================================
-- FIM DA MIGRATION 002
-- =========================================================
COMMENT ON SCHEMA bk_malha_terra IS
    'BK Malha de Terra v2 - Multi-tenant SaaS. '
    'Migration 002 aplicada em: ' || NOW()::TEXT;
