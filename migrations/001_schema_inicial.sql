-- =========================================================
-- BK Malha de Terra v2 -- Schema Multi-Tenant
-- Migration 001 -- Criacao do schema completo v2
-- =========================================================
-- Fresh install:
--   psql "$DATABASE_URL" -f migrations/001_schema_inicial.sql
-- =========================================================

CREATE SCHEMA IF NOT EXISTS bk_malha_terra;
SET search_path TO bk_malha_terra;

-- ---------------------------------------------------------
-- Tabela: tenants
-- Empresas/clientes (isolamento multi-tenant)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id              SERIAL PRIMARY KEY,
    nome_empresa    VARCHAR(300) NOT NULL,
    cnpj            VARCHAR(18),
    email_contato   VARCHAR(254) NOT NULL UNIQUE,
    telefone        VARCHAR(20),
    plano           VARCHAR(20)  NOT NULL DEFAULT 'trial',
    ativo           BOOLEAN      NOT NULL DEFAULT TRUE,
    max_projetos    INTEGER      NOT NULL DEFAULT 3,
    max_usuarios    INTEGER      NOT NULL DEFAULT 2,
    trial_expira_em TIMESTAMP,
    criado_em       TIMESTAMP    NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Tabela: usuarios
-- Usuarios por tenant (roles: admin / engenheiro / viewer)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id            SERIAL PRIMARY KEY,
    tenant_id     INTEGER      NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    nome          VARCHAR(200) NOT NULL,
    email         VARCHAR(254) NOT NULL UNIQUE,
    senha_hash    VARCHAR(72)  NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'engenheiro',
    crea          VARCHAR(50),
    ativo         BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMP    NOT NULL DEFAULT NOW(),
    ultimo_acesso TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant ON usuarios(tenant_id);

-- ---------------------------------------------------------
-- Tabela: projetos
-- Identificacao do projeto e cliente (isolado por tenant)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS projetos (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INTEGER      NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    criado_por_id       INTEGER      REFERENCES usuarios(id) ON DELETE SET NULL,
    cliente             VARCHAR(200) NOT NULL,
    nome_projeto        VARCHAR(300) NOT NULL,
    numero_projeto      VARCHAR(50)  NOT NULL,
    revisao             VARCHAR(10)  NOT NULL DEFAULT '00',
    responsavel_tecnico VARCHAR(200),
    crea_responsavel    VARCHAR(50),
    concessionaria      VARCHAR(50),
    data_calculo        DATE         NOT NULL DEFAULT CURRENT_DATE,
    observacoes         TEXT,
    criado_em           TIMESTAMP    NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uk_projeto_revisao UNIQUE (tenant_id, numero_projeto, revisao)
);

CREATE INDEX IF NOT EXISTS idx_projetos_tenant  ON projetos(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projetos_cliente ON projetos(cliente);
CREATE INDEX IF NOT EXISTS idx_projetos_numero  ON projetos(numero_projeto);

-- ---------------------------------------------------------
-- Tabela: solos_wenner
-- Medicoes de resistividade pelo metodo de Wenner (NBR 7117)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS solos_wenner (
    id              SERIAL PRIMARY KEY,
    projeto_id      INTEGER       NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    ponto           INTEGER       NOT NULL,
    espacamento_m   NUMERIC(6,2)  NOT NULL,
    resistencia_ohm NUMERIC(10,4) NOT NULL,
    rho_aparente    NUMERIC(10,4),

    CONSTRAINT chk_espac_pos  CHECK (espacamento_m > 0),
    CONSTRAINT chk_resist_pos CHECK (resistencia_ohm > 0)
);

CREATE INDEX IF NOT EXISTS idx_wenner_projeto ON solos_wenner(projeto_id);

-- ---------------------------------------------------------
-- Tabela: dados_entrada
-- Parametros de projeto (geometria, brita, hastes, curto)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS dados_entrada (
    id                      SERIAL PRIMARY KEY,
    projeto_id              INTEGER      NOT NULL UNIQUE REFERENCES projetos(id) ON DELETE CASCADE,

    largura_m               NUMERIC(8,2) NOT NULL,
    comprimento_m           NUMERIC(8,2) NOT NULL,
    profundidade_malha_m    NUMERIC(5,2) NOT NULL DEFAULT 0.50,
    espac_malha_principal_m NUMERIC(5,2) NOT NULL,
    espac_malha_juncao_m    NUMERIC(5,2),

    brita_espessura_m       NUMERIC(5,3) NOT NULL DEFAULT 0.10,
    brita_resistividade_ohm NUMERIC(8,1) NOT NULL DEFAULT 3000.0,

    haste_comprimento_m     NUMERIC(5,2) NOT NULL DEFAULT 3.0,
    haste_diametro_mm       NUMERIC(6,3) NOT NULL DEFAULT 15.875,

    condutor_material       VARCHAR(20)  NOT NULL DEFAULT 'cobre_nu',
    condutor_bitola_mm2     NUMERIC(6,2),

    i_falta_3i0_ka          NUMERIC(8,3) NOT NULL,
    tempo_eliminacao_s      NUMERIC(5,3) NOT NULL DEFAULT 0.5,
    sf_div_corrente         NUMERIC(4,3) NOT NULL DEFAULT 0.6,
    xr_ratio                NUMERIC(6,2),
    df_decremento           NUMERIC(5,3),
    peso_pessoa_kg          INTEGER      NOT NULL DEFAULT 50,
    cp_crescimento          NUMERIC(4,2) NOT NULL DEFAULT 1.00,

    criado_em               TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_largura_pos     CHECK (largura_m > 0),
    CONSTRAINT chk_comprimento_pos CHECK (comprimento_m > 0),
    CONSTRAINT chk_peso            CHECK (peso_pessoa_kg IN (50, 70))
);

-- ---------------------------------------------------------
-- Tabela: resultados
-- Saida completa do calculo IEEE 80-2013 / NBR 15751
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS resultados (
    id                       SERIAL PRIMARY KEY,
    projeto_id               INTEGER       NOT NULL UNIQUE REFERENCES projetos(id) ON DELETE CASCADE,

    rho1_ohm_m               NUMERIC(10,2),
    rho2_ohm_m               NUMERIC(10,2),
    h1_m                     NUMERIC(6,2),
    rho_equivalente          NUMERIC(10,2),

    bitola_calculada_mm2     NUMERIC(8,2),
    bitola_adotada_mm2       NUMERIC(8,2),
    atende_condutor          BOOLEAN,

    cs_brita                 NUMERIC(5,3),
    etoque_admissivel_v      NUMERIC(10,2),
    epasso_admissivel_v      NUMERIC(10,2),

    df_decremento            NUMERIC(5,3),
    cp_crescimento           NUMERIC(4,2),
    ig_corrente_malha_a      NUMERIC(10,2),

    rg_sverak_ohm            NUMERIC(8,4),
    rg_schwarz_ohm           NUMERIC(8,4),
    rg_adotado_ohm           NUMERIC(8,4),
    gpr_v                    NUMERIC(12,2),

    em_tensao_malha_v        NUMERIC(10,2),
    es_tensao_passo_v        NUMERIC(10,2),

    num_hastes               INTEGER,
    comprimento_total_cabo_m NUMERIC(10,2),
    posicoes_hastes_json     JSON,

    atende_toque             BOOLEAN,
    atende_passo             BOOLEAN,
    atende_geral             BOOLEAN,
    margem_toque_pct         NUMERIC(6,2),
    margem_passo_pct         NUMERIC(6,2),

    json_completo            JSON,

    calculado_em             TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Tabela: relatorios_gerados
-- Historico de relatorios Word gerados
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS relatorios_gerados (
    id           SERIAL PRIMARY KEY,
    projeto_id   INTEGER      NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    nome_arquivo VARCHAR(300) NOT NULL,
    gerado_em    TIMESTAMP    NOT NULL DEFAULT NOW(),
    gerado_por   VARCHAR(200)
);

CREATE INDEX IF NOT EXISTS idx_relatorios_projeto ON relatorios_gerados(projeto_id);

-- ---------------------------------------------------------
-- Trigger: atualiza atualizado_em em projetos e tenants
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_atualizado_em()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projetos_atualizado ON projetos;
CREATE TRIGGER trg_projetos_atualizado
    BEFORE UPDATE ON projetos
    FOR EACH ROW EXECUTE FUNCTION trigger_set_atualizado_em();

DROP TRIGGER IF EXISTS trg_tenants_atualizado ON tenants;
CREATE TRIGGER trg_tenants_atualizado
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION trigger_set_atualizado_em();

-- ---------------------------------------------------------
-- Comentarios (documentacao no banco)
-- ---------------------------------------------------------
COMMENT ON SCHEMA bk_malha_terra IS 'BK Malha de Terra v2 - Multi-Tenant';
COMMENT ON TABLE tenants            IS 'Empresas/clientes (isolamento multi-tenant)';
COMMENT ON TABLE usuarios           IS 'Usuarios por tenant (roles: admin/engenheiro/viewer)';
COMMENT ON TABLE projetos           IS 'Projetos de malha de aterramento por tenant';
COMMENT ON TABLE solos_wenner       IS 'Medicoes Wenner conforme NBR 7117';
COMMENT ON TABLE dados_entrada      IS 'Parametros do projeto da malha';
COMMENT ON TABLE resultados         IS 'Resultados completos IEEE 80-2013 / NBR 15751';
COMMENT ON TABLE relatorios_gerados IS 'Historico de relatorios Word gerados';
