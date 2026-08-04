-- ============================================================
-- Apaga TODOS os registros de teto_mac (dados importados das planilhas) e o
-- histórico de importações, para reimportar do zero (ex: após corrigir o
-- mapeamento de uma coluna na importação, como o PNCP).
--
-- O que é apagado:  teto_mac (todos os registros), importacoes (histórico)
-- O que é preservado: usuarios, secao_config, campo_config, sistema_config,
--                      portarias — configuração do sistema, não dado importado
--
-- Execute no Supabase: Dashboard -> SQL Editor -> New query.
-- ATENÇÃO: irreversível. Confirme que é o banco certo antes de rodar.
-- ============================================================

TRUNCATE TABLE teto_mac RESTART IDENTITY;
TRUNCATE TABLE importacoes RESTART IDENTITY;

SELECT 'OK — teto_mac e importacoes zerados. Pronto para reimportar.' AS status;
