-- ============================================================
-- Corrige AIH Total e SIA Total, que estavam sempre R$ 0,00.
--
-- Causa: a planilha fonte NUNCA traz uma coluna "AIH TOTAL"/"SIA TOTAL"
-- pronta (só traz AIH/SIA separados em FAEC, MC e AC) — a importação lia uma
-- coluna que não existe e sempre gravava 0. AIH Total já era um campo
-- 'calculado' em campo_config (soma automática ao editar), mas SIA Total
-- nunca tinha sido configurado assim. A importação (import_xls.py) e o
-- campo_config já foram corrigidos no código; este script só:
--   1) conserta o cadastro de sia_total em campo_config (calculado, com
--      fórmula sia_faec+sia_mc+sia_ac, igual ao aih_total);
--   2) recalcula aih_total e sia_total de TODOS os registros já importados,
--      que continuam com o valor errado até rodar isto.
-- Execute no Supabase: Dashboard -> SQL Editor -> New query. Idempotente.
-- ============================================================

-- 1) Corrige o cadastro do campo (só entra em vigor se ainda estiver como
--    'moeda' sem fórmula — não sobrescreve se alguém já tiver mexido nele)
UPDATE campo_config
SET tipo = 'calculado', formula = 'sia_faec,sia_mc,sia_ac'
WHERE campo_key = 'sia_total' AND tipo <> 'calculado';

-- 2) Recalcula os valores já gravados em todos os registros
UPDATE teto_mac
SET aih_total = COALESCE(aih_faec, 0) + COALESCE(aih_mc, 0) + COALESCE(aih_ac, 0),
    sia_total = COALESCE(sia_faec, 0) + COALESCE(sia_mc, 0) + COALESCE(sia_ac, 0);

SELECT 'OK — sia_total corrigido em campo_config e aih_total/sia_total recalculados em ' ||
       (SELECT COUNT(*) FROM teto_mac) || ' registros.' AS status;
