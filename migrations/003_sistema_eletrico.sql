-- ============================================================
-- Migration 003: Sistema Elétrico e Proteção
-- BK Malha de Terra v2.1
-- Compatível com PostgreSQL (Railway/Neon) e SQLite
-- ============================================================

BEGIN;

-- ── Barras do sistema elétrico ─────────────────────────────────────────────
-- Armazena impedâncias de sequência e correntes de curto-circuito por barra.
-- Uma subestação tipicamente tem 2+ barras (AT, MT, BT).

CREATE TABLE IF NOT EXISTS barra_sistema (
    id              SERIAL PRIMARY KEY,
    projeto_id      INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    ordem           INTEGER NOT NULL DEFAULT 0,        -- para ordenação na exibição
    nome            VARCHAR(100) NOT NULL,              -- ex: "Barra AT 138 kV", "Barra MT 13,8 kV"
    tensao_kv       DECIMAL(10, 3) NOT NULL,           -- tensão nominal em kV
    tipo            VARCHAR(50),                       -- "AT", "MT", "BT", "GD"
    base_mva        DECIMAL(10, 3) DEFAULT 100.0,      -- base MVA (para conversão pu)
    unidade_z       VARCHAR(10) DEFAULT 'Ohm',         -- 'Ohm' ou 'pu'

    -- Impedâncias de sequência positiva Z1 = R1 + jX1
    z1_r_ohm        DECIMAL(15, 6),
    z1_x_ohm        DECIMAL(15, 6),
    z1_mod_ohm      DECIMAL(15, 6),                    -- |Z1|
    z1_ang_grau     DECIMAL(8, 3),                     -- ângulo Z1

    -- Impedâncias de sequência negativa Z2 (geralmente = Z1 em sistemas sem máquinas)
    z2_r_ohm        DECIMAL(15, 6),
    z2_x_ohm        DECIMAL(15, 6),

    -- Impedâncias de sequência zero Z0 = R0 + jX0
    z0_r_ohm        DECIMAL(15, 6),
    z0_x_ohm        DECIMAL(15, 6),
    z0_mod_ohm      DECIMAL(15, 6),
    z0_ang_grau     DECIMAL(8, 3),

    -- Correntes de curto-circuito
    icc_3f_ka       DECIMAL(12, 4),                    -- Icc trifásico simétrico [kA]
    icc_2f_ka       DECIMAL(12, 4),                    -- Icc bifásico [kA]
    icc_1f_ka       DECIMAL(12, 4),                    -- Icc fase-terra (= 3I0) [kA]
    icc_2f1f_ka     DECIMAL(12, 4),                    -- Icc bifásico-terra [kA]
    ip_pico_ka      DECIMAL(12, 4),                    -- Corrente de pico ip = κ√2 × Icc [kA]
    xr_ratio        DECIMAL(8, 3),                     -- Relação X/R no ponto de falta
    kappa           DECIMAL(6, 4),                     -- Fator de pico κ (IEC 60909)

    -- Flags
    e_barra_projeto BOOLEAN DEFAULT FALSE,             -- marca a barra usada no cálculo da malha
    observacoes     TEXT,
    criado_em       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_barra_projeto ON barra_sistema(projeto_id);


-- ── Relés de proteção ──────────────────────────────────────────────────────
-- Armazena configuração dos relés e tempos de eliminação por barra.
-- Permite justificar o tc adotado no estudo de malha de terra.

CREATE TABLE IF NOT EXISTS rele_protecao (
    id                  SERIAL PRIMARY KEY,
    projeto_id          INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    barra_nome          VARCHAR(100),                  -- barra protegida
    nome                VARCHAR(150) NOT NULL,         -- identificação do relé, ex: "87T - Proteção diferencial TR1"
    fabricante          VARCHAR(100),                 -- ex: "SEL", "Siemens", "GE", "ABB"
    modelo              VARCHAR(100),                 -- ex: "SEL-487E", "7UT87"
    funcoes_ansi        VARCHAR(200),                 -- ex: "87T, 51, 50"
    tipo_protecao       VARCHAR(100),                 -- "Primária", "Backup 1°", "Backup 2°", "Emergência"
    nivel               INTEGER DEFAULT 1,            -- 1=primária, 2=1ºbackup, 3=2ºbackup
    tempo_rele_s        DECIMAL(10, 4),               -- tempo de atuação do relé [s]
    tempo_abertura_dj_s DECIMAL(10, 4) DEFAULT 0.05,  -- tempo de abertura do disjuntor [s]
    tempo_total_tc_s    DECIMAL(10, 4),               -- tc = t_relé + t_DJ [s]
    e_tc_adotado        BOOLEAN DEFAULT FALSE,        -- TRUE: este tc é o adotado no estudo de malha
    ajuste_pickup_pu    DECIMAL(10, 4),               -- pickup em pu da corrente nominal
    curva               VARCHAR(100),                 -- "Standard Inverse", "Very Inverse", etc.
    observacoes         TEXT,
    criado_em           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rele_projeto ON rele_protecao(projeto_id);


-- ── Dados do transformador (opcional, melhora a capa do relatório) ─────────

CREATE TABLE IF NOT EXISTS transformador_se (
    id                  SERIAL PRIMARY KEY,
    projeto_id          INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    tag                 VARCHAR(50),                  -- ex: "TR-01"
    potencia_mva        DECIMAL(10, 3),               -- potência nominal [MVA]
    tensao_at_kv        DECIMAL(10, 3),               -- tensão AT [kV]
    tensao_mt_kv        DECIMAL(10, 3),               -- tensão MT [kV]
    tensao_bt_kv        DECIMAL(10, 3),               -- tensão BT (se trifásico, ou 0)
    grupo_ligacao       VARCHAR(20),                  -- ex: "YNyn0", "Dyn11", "YNd11"
    zcc_pct             DECIMAL(6, 3),                -- impedância de curto-circuito [%]
    corrente_nom_at_a   DECIMAL(10, 2),
    corrente_nom_mt_a   DECIMAL(10, 2),
    fabricante          VARCHAR(100),
    numero_serie        VARCHAR(100),
    observacoes         TEXT,
    criado_em           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trafo_projeto ON transformador_se(projeto_id);

COMMIT;
