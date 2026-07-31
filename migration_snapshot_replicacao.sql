-- ═══════════════════════════════════════════════════════════════════
-- migration_snapshot_replicacao.sql
-- Adiciona o rastreamento de "o que foi alterado" em registros criados
-- por Replicar Competência (copiar todos os registros de um mês para outro).
-- Execute este script no Supabase Dashboard (SQL Editor) UMA ÚNICA VEZ.
-- Idempotente: pode ser executado mais de uma vez sem efeitos colaterais.
-- ═══════════════════════════════════════════════════════════════════

-- snapshot_replicacao: foto (JSON) de todos os campos de negócio do registro de
-- origem no momento em que ele foi copiado. Usada para destacar em vermelho, na
-- tela do registro, os campos que foram alterados depois da cópia.
ALTER TABLE teto_mac ADD COLUMN IF NOT EXISTS snapshot_replicacao JSONB;

-- origem_replicacao_ano/mes: de qual competência o registro foi copiado, só para
-- exibir "copiado de Março/2026" na tela do registro.
ALTER TABLE teto_mac ADD COLUMN IF NOT EXISTS origem_replicacao_ano INTEGER;
ALTER TABLE teto_mac ADD COLUMN IF NOT EXISTS origem_replicacao_mes INTEGER;
