-- ============================================================
-- Ledger de ajustes por campo — sustenta a trava de "Editar Registro": os
-- valores dos campos de negócio (AIH/SIA/Teto MAC/Incentivos) ficam travados
-- (não editáveis diretamente); para mudar um valor, o usuário lança um ajuste
-- (adição ou subtração de uma quantia, referente a uma Portaria/SIB específica)
-- com justificativa obrigatória. Um campo pode acumular vários ajustes ao
-- longo do tempo. A coluna em teto_mac continua sendo o "valor atual"
-- (original + soma de todos os ajustes) — nenhum relatório/RPC existente
-- precisa mudar para enxergar o efeito de um ajuste.
-- Execute no Supabase: Dashboard -> SQL Editor -> New query.
-- ============================================================

CREATE TABLE IF NOT EXISTS ajustes_campo (
    id             BIGSERIAL PRIMARY KEY,
    registro_id    BIGINT      NOT NULL REFERENCES teto_mac(id) ON DELETE CASCADE,
    campo_key      TEXT        NOT NULL,      -- campo_config.campo_key
    tipo           TEXT        NOT NULL CHECK (tipo IN ('adicao','subtracao')),
    valor          NUMERIC     NOT NULL CHECK (valor > 0),   -- magnitude; sinal vem de `tipo`
    justificativa  TEXT        NOT NULL,
    usuario_nome   TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ajustes_registro_campo ON ajustes_campo(registro_id, campo_key);

ALTER TABLE ajustes_campo DISABLE ROW LEVEL SECURITY;

SELECT 'OK — tabela ajustes_campo criada.' AS status;
