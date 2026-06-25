-- ═══════════════════════════════════════════════════════════════════════════
-- PORTARIAS — Migração Supabase
-- Executar no Supabase Dashboard → SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. Tabela de metadados das portarias
CREATE TABLE IF NOT EXISTS portarias (
    id                  BIGSERIAL PRIMARY KEY,
    cnes                TEXT        NOT NULL,
    nome_original       TEXT        NOT NULL,
    storage_path        TEXT        NOT NULL UNIQUE,
    descricao           TEXT        DEFAULT '',
    tamanho_kb          INTEGER     DEFAULT 0,
    tamanho_original_kb INTEGER     DEFAULT 0,
    validado            BOOLEAN     DEFAULT FALSE,
    validado_em         TEXT,
    validado_por        TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portarias_cnes ON portarias(cnes);

-- 2. Desabilitar RLS (consistente com as demais tabelas do sistema)
ALTER TABLE portarias DISABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════════════════
-- STORAGE BUCKET
-- Após executar este SQL, crie o bucket via Python (setup_portarias.py)
-- OU manualmente no Supabase Dashboard:
--   Storage → New bucket → Name: portarias → Private (desmarcar "Public bucket")
-- ═══════════════════════════════════════════════════════════════════════════
