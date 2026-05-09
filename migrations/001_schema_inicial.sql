-- =========================================================
-- BK Malha de Terra - Schema inicial
-- Migration 001 - Criação do schema e tabelas base
-- =========================================================
-- Como rodar:
--   psql "$DATABASE_URL" -f migrations/001_schema_inicial.sql
-- =========================================================

CREATE SCHEMA IF NOT EXISTS bk_malha_terra;
SET search_path TO bk_malha_terra;

-- ---------------------------------------------------------
-- Tabela: projetos
-- Identificação do projeto e cliente
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS projetos (
    id                  SERIAL PRIMARY KEY,
    cliente             VARCHAR(200) NOT NULL,
    nome_projeto        VARCHAR(300) NOT NULL,
    numero_projeto      VARCHAR(50)  NOT NULL,
    revisao             VARCHAR(10)  NOT NULL DEFAULT '00',
    responsavel_tecnico VARCHAR(200),
    crea_responsavel    VARCHAR(50),
    concessionaria      VARCHAR(50),
    data_calculo        DATE NOT NULL DEFAULT CURRENT_DATE,
    observacoes         TEXT,
    criado_em           TIMESTAMP NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uk_projeto_revisao UNIQUE (numero_projeto, revisao)
);

CREATE INDEX IF NOT EXISTS idx_projetos_cliente ON projetos(cliente);
CREATE INDEX IF NOT EXISTS idx_projetos_numero  ON projetos(numero_projeto);

-- ---------------------------------------------------------
-- Tabela: solos_wenner
-- Medições de resistividade pelo método de Wenner (NBR 7117)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS solos_wenner (
    id                  SERIAL PRIMARY KEY,
    projeto_id          INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    ponto               INTEGER NOT NULL,         -- ordem da medição
    espacamento_m       NUMERIC(6,2) NOT NULL,    -- a [m]
    resistencia_ohm     NUMERIC(10,4) NOT NULL,   -- R [Ω]
    rho_aparente        NUMERIC(10,4),            -- ρ = 2πaR [Ω·m]
    
    CONSTRAINT chk_espac_pos CHECK (espacamento_m > 0),
    CONSTRAINT chk_resist_pos CHECK (resistencia_ohm > 0)
);

CREATE INDEX IF NOT EXISTS idx_wenner_projeto ON solos_wenner(projeto_id);

-- ---------------------------------------------------------
-- Tabela: dados_entrada
-- Parâmetros de projeto (geometria, brita, hastes, curto)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS dados_entrada (
    id                      SERIAL PRIMARY KEY,
    projeto_id              INTEGER NOT NULL UNIQUE REFERENCES projetos(id) ON DELETE CASCADE,
    
    -- Geometria
    largura_m               NUMERIC(8,2) NOT NULL,
    comprimento_m           NUMERIC(8,2) NOT NULL,
    profundidade_malha_m    NUMERIC(5,2) NOT NULL DEFAULT 0.50,
    espac_malha_principal_m NUMERIC(5,2) NOT NULL,
    espac_malha_juncao_m    NUMERIC(5,2),  -- malha mais densa nas bordas
    
    -- Brita superficial
    brita_espessura_m       NUMERIC(5,3) NOT NULL DEFAULT 0.10,
    brita_resistividade_ohm NUMERIC(8,1) NOT NULL DEFAULT 3000.0,
    
    -- Hastes
    haste_comprimento_m     NUMERIC(5,2) NOT NULL DEFAULT 3.0,
    haste_diametro_mm       NUMERIC(6,3) NOT NULL DEFAULT 15.875,  -- 5/8"
    
    -- Condutor
    condutor_material       VARCHAR(20) NOT NULL DEFAULT 'cobre_nu',
    condutor_bitola_mm2     NUMERIC(6,2),  -- calculado se NULL
    
    -- Dados elétricos
    i_falta_3i0_ka          NUMERIC(8,3) NOT NULL,
    tempo_eliminacao_s      NUMERIC(5,3) NOT NULL DEFAULT 0.5,
    sf_div_corrente         NUMERIC(4,3) NOT NULL DEFAULT 0.6,
    xr_ratio                NUMERIC(6,2),
    df_decremento           NUMERIC(5,3),  -- calculado pelo app
    peso_pessoa_kg          INTEGER NOT NULL DEFAULT 50,
    
    criado_em               TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT chk_largura_pos     CHECK (largura_m > 0),
    CONSTRAINT chk_comprimento_pos CHECK (comprimento_m > 0),
    CONSTRAINT chk_peso            CHECK (peso_pessoa_kg IN (50, 70))
);

-- ---------------------------------------------------------
-- Tabela: resultados
-- Saída completa do cálculo
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS resultados (
    id                      SERIAL PRIMARY KEY,
    projeto_id              INTEGER NOT NULL UNIQUE REFERENCES projetos(id) ON DELETE CASCADE,
    
    -- Estratificação
    rho1_ohm_m              NUMERIC(10,2),
    rho2_ohm_m              NUMERIC(10,2),
    h1_m                    NUMERIC(6,2),
    rho_equivalente         NUMERIC(10,2),
    
    -- Dimensionamento condutor
    bitola_calculada_mm2    NUMERIC(8,2),
    bitola_adotada_mm2      NUMERIC(8,2),
    
    -- Tensões admissíveis
    cs_brita                NUMERIC(5,3),
    etoque_admissivel_v     NUMERIC(10,2),
    epasso_admissivel_v     NUMERIC(10,2),
    
    -- Corrente de malha
    df_decremento           NUMERIC(5,3),
    ig_corrente_malha_a     NUMERIC(10,2),
    
    -- Resistência da malha
    rg_sverak_ohm           NUMERIC(8,4),
    rg_schwarz_ohm          NUMERIC(8,4),
    rg_adotado_ohm          NUMERIC(8,4),
    gpr_v                   NUMERIC(12,2),
    
    -- Tensões calculadas
    em_tensao_malha_v       NUMERIC(10,2),
    es_tensao_passo_v       NUMERIC(10,2),
    
    -- Geometria final
    num_hastes              INTEGER,
    comprimento_total_cabo_m NUMERIC(10,2),
    posicoes_hastes_json    JSONB,  -- [{x,y}, ...]
    
    -- Verificação
    atende_toque            BOOLEAN,
    atende_passo            BOOLEAN,
    atende_geral            BOOLEAN,
    margem_toque_pct        NUMERIC(6,2),
    margem_passo_pct        NUMERIC(6,2),
    
    -- Bruto
    json_completo           JSONB,  -- todos os intermediários
    
    calculado_em            TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Tabela: relatorios_gerados
-- Histórico de relatórios Word gerados
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS relatorios_gerados (
    id              SERIAL PRIMARY KEY,
    projeto_id      INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    nome_arquivo    VARCHAR(300) NOT NULL,
    gerado_em       TIMESTAMP NOT NULL DEFAULT NOW(),
    gerado_por      VARCHAR(200)
);

-- ---------------------------------------------------------
-- Trigger para atualizar campo atualizado_em
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projetos_atualizado ON projetos;
CREATE TRIGGER trg_projetos_atualizado
    BEFORE UPDATE ON projetos
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_atualizado_em();

-- ---------------------------------------------------------
-- Comentários (documentação no banco)
-- ---------------------------------------------------------
COMMENT ON SCHEMA bk_malha_terra IS 'Memórias de cálculo de malha de aterramento - BK Engenharia';
COMMENT ON TABLE  projetos        IS 'Cadastro de projetos com revisão';
COMMENT ON TABLE  solos_wenner    IS 'Medições Wenner conforme NBR 7117';
COMMENT ON TABLE  dados_entrada   IS 'Parâmetros do projeto da malha';
COMMENT ON TABLE  resultados      IS 'Resultados completos do cálculo IEEE 80-2013';
