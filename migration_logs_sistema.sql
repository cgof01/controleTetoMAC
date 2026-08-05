-- ============================================================
-- Log de auditoria do sistema — grava ações administrativas sensíveis
-- (exclusão de competência, de um ano inteiro, ou de toda a base) com quem
-- fez, quando e quantos registros foram afetados. Usado pela Zona de Risco
-- na tela de Importar Dados.
-- Execute no Supabase: Dashboard -> SQL Editor -> New query.
-- ============================================================

CREATE TABLE IF NOT EXISTS logs_sistema (
    id                 BIGSERIAL PRIMARY KEY,
    usuario_nome       TEXT,
    acao               TEXT NOT NULL,
    detalhes           TEXT,
    registros_afetados INTEGER DEFAULT 0,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_sistema_created_at ON logs_sistema(created_at DESC);

ALTER TABLE logs_sistema DISABLE ROW LEVEL SECURITY;

SELECT 'OK — tabela logs_sistema criada.' AS status;
