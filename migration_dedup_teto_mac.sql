-- ============================================================
-- Corrige duplicação de registros em reimportações de planilha
-- Execute no Supabase: Dashboard -> SQL Editor -> New query
-- ============================================================

-- 1) Remove duplicatas já existentes (mesma competência + cnes + unidade),
--    mantendo apenas o registro mais recente (maior id) de cada grupo
DELETE FROM teto_mac a USING teto_mac b
WHERE a.id < b.id
  AND a.ano = b.ano
  AND a.mes = b.mes
  AND a.cnes = b.cnes
  AND a.unidade = b.unidade;

-- 2) Cria o índice único que passa a impedir novas duplicações e habilita
--    o upsert usado pela importação (insere o que é novo, atualiza o que já existe)
CREATE UNIQUE INDEX IF NOT EXISTS idx_teto_ano_mes_cnes_unidade_uidx
    ON teto_mac(ano, mes, cnes, unidade);

-- 3) Coluna nova para o histórico de importações mostrar quantos registros
--    foram atualizados (em vez de contar tudo como "importado")
ALTER TABLE importacoes ADD COLUMN IF NOT EXISTS registros_atualizados INTEGER DEFAULT 0;
