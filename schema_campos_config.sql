-- ═══════════════════════════════════════════════════════════════════
-- schema_campos_config.sql — Configuração dinâmica de campos do formulário
-- Execute este script no Supabase Dashboard (SQL Editor) UMA ÚNICA VEZ
-- ═══════════════════════════════════════════════════════════════════

-- Tabela de seções do formulário
CREATE TABLE IF NOT EXISTS secao_config (
  id          SERIAL PRIMARY KEY,
  secao_key   TEXT UNIQUE NOT NULL,
  label       TEXT NOT NULL,
  cor         TEXT NOT NULL DEFAULT 'primary',
  icone       TEXT NOT NULL DEFAULT 'list',
  ordem       INT  NOT NULL DEFAULT 0,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de configuração de campos
CREATE TABLE IF NOT EXISTS campo_config (
  id          SERIAL PRIMARY KEY,
  secao_key   TEXT NOT NULL,
  campo_key   TEXT NOT NULL UNIQUE,
  label       TEXT NOT NULL,
  -- tipo: 'moeda' | 'numero' | 'texto' | 'alfanumerico' | 'calculado'
  tipo        TEXT NOT NULL DEFAULT 'moeda',
  ordem       INT  NOT NULL DEFAULT 0,
  ativo       BOOLEAN NOT NULL DEFAULT TRUE,
  obrigatorio BOOLEAN NOT NULL DEFAULT FALSE,
  -- formula: chaves separadas por vírgula para auto-soma (somente tipo 'calculado')
  formula     TEXT DEFAULT NULL,
  -- coluna_db: coluna real em teto_mac; NULL = salvo em campos_extras JSONB
  coluna_db   TEXT DEFAULT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Coluna para campos personalizados extras em teto_mac
ALTER TABLE teto_mac ADD COLUMN IF NOT EXISTS campos_extras JSONB DEFAULT '{}';

-- ── Seed: Seções ────────────────────────────────────────────────────────────────
INSERT INTO secao_config (secao_key, label, cor, icone, ordem) VALUES
  ('aih',       'AIH — Autorização de Internação Hospitalar', 'success',   'cash-stack',     1),
  ('sia',       'SIA — Sistema de Informações Ambulatoriais', 'info',      'clipboard-data', 2),
  ('teto_mac',  'Teto MAC',                                   'secondary', 'bank',           3),
  ('incentivos','Incentivos',                                  'warning',   'award',          4)
ON CONFLICT (secao_key) DO NOTHING;

-- ── Seed: Campos AIH ────────────────────────────────────────────────────────────
INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db, formula) VALUES
  ('aih', 'aih_fisico', 'AIH Físico',               'moeda',     10, 'aih_fisico', NULL),
  ('aih', 'aih_faec',   'AIH FAEC',                 'moeda',     20, 'aih_faec',   NULL),
  ('aih', 'aih_mc',     'AIH MC (Média Complexidade)','moeda',   30, 'aih_mc',     NULL),
  ('aih', 'aih_ac',     'AIH AC (Alta Complexidade)', 'moeda',   40, 'aih_ac',     NULL),
  ('aih', 'aih_total',  'AIH Total',                'calculado', 50, 'aih_total',  'aih_fisico,aih_faec,aih_mc,aih_ac')
ON CONFLICT (campo_key) DO NOTHING;

-- ── Seed: Campos SIA ────────────────────────────────────────────────────────────
INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db) VALUES
  ('sia', 'sia_faec',             'SIA FAEC',                        'moeda', 10, 'sia_faec'),
  ('sia', 'sia_mc',               'SIA MC (Média Complexidade)',      'moeda', 20, 'sia_mc'),
  ('sia', 'sia_ac',               'SIA AC (Alta Complexidade)',       'moeda', 30, 'sia_ac'),
  ('sia', 'sia_total',            'SIA Total',                       'moeda', 40, 'sia_total'),
  ('sia', 'equip_hemodialise',    'Equip. Hemodiálise (DRC)',         'moeda', 50, 'equip_hemodialise'),
  ('sia', 'limite_complementacao','Limite Complementação Tabela SUS', 'moeda', 60, 'limite_complementacao')
ON CONFLICT (campo_key) DO NOTHING;

-- ── Seed: Campos Teto MAC ───────────────────────────────────────────────────────
INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db) VALUES
  ('teto_mac', 'teto_global',        'Teto Global',        'moeda', 10, 'teto_global'),
  ('teto_mac', 'teto_mc',            'Teto MC',            'moeda', 20, 'teto_mc'),
  ('teto_mac', 'teto_ac',            'Teto AC',            'moeda', 30, 'teto_ac'),
  ('teto_mac', 'teto_mac_campo',     'Teto MAC',           'moeda', 40, 'teto_mac'),
  ('teto_mac', 'total_teto_mac',     'Total Teto MAC',     'moeda', 50, 'total_teto_mac'),
  ('teto_mac', 'portaria_ms_gm_8516','Portaria MS/GM 8.516','moeda',60, 'portaria_ms_gm_8516')
ON CONFLICT (campo_key) DO NOTHING;

-- ── Seed: Campos Incentivos ─────────────────────────────────────────────────────
INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db) VALUES
  ('incentivos', 'integrasus',          'IntegraSUS',            'moeda', 10,  'integrasus'),
  ('incentivos', 'iac',                 'IAC',                   'moeda', 20,  'iac'),
  ('incentivos', 'sus_100',             '100% SUS',              'moeda', 30,  'sus_100'),
  ('incentivos', 'opo',                 'OPO',                   'moeda', 40,  'opo'),
  ('incentivos', 'rede_viver_sem_limite','Rede Viver Sem Limite', 'moeda', 50, 'rede_viver_sem_limite'),
  ('incentivos', 'rede_brasil_miseria', 'Rede Brasil Sem Miséria','moeda', 60, 'rede_brasil_miseria'),
  ('incentivos', 'rsme',                'RSME',                  'moeda', 70,  'rsme'),
  ('incentivos', 'rce_rceg',            'RCE/RCEG',              'moeda', 80,  'rce_rceg'),
  ('incentivos', 'rau_hosp_sos',        'RAU/HOSP SOS',          'moeda', 90,  'rau_hosp_sos'),
  ('incentivos', 'rca_rcan',            'RCA/RCAN',              'moeda', 100, 'rca_rcan'),
  ('incentivos', 'iapi',                'IAPI',                  'moeda', 110, 'iapi'),
  ('incentivos', 'residencia_medica',   'Residência Médica',     'moeda', 120, 'residencia_medica'),
  ('incentivos', 'melhor_em_casa',      'Melhor em Casa',        'moeda', 130, 'melhor_em_casa'),
  ('incentivos', 'cer',                 'CER',                   'moeda', 140, 'cer'),
  ('incentivos', 'doencas_raras',       'Doenças Raras',         'moeda', 150, 'doencas_raras'),
  ('incentivos', 'oficina_ortopedica',  'Oficina Ortopédica',    'moeda', 160, 'oficina_ortopedica'),
  ('incentivos', 'ihac',                'IHAC',                  'moeda', 170, 'ihac')
ON CONFLICT (campo_key) DO NOTHING;

-- Campo total calculado (deve ser o último na seção incentivos)
INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db, formula) VALUES
  ('incentivos', 'total_mc_ac_incentivos', 'TOTAL MC + AC + INCENTIVOS', 'calculado', 999, 'total_mc_ac_incentivos',
   'aih_mc,aih_ac,sia_mc,sia_ac,integrasus,iac,sus_100,opo,rede_viver_sem_limite,rede_brasil_miseria,rsme,rce_rceg,rau_hosp_sos,rca_rcan,iapi,residencia_medica,melhor_em_casa,cer,doencas_raras,oficina_ortopedica,ihac')
ON CONFLICT (campo_key) DO NOTHING;

-- Índices
CREATE INDEX IF NOT EXISTS idx_campo_config_secao ON campo_config(secao_key);
CREATE INDEX IF NOT EXISTS idx_campo_config_ordem ON campo_config(secao_key, ordem);
