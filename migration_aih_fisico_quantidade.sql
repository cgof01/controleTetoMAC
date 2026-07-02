-- ═══════════════════════════════════════════════════════════════════
-- migration_aih_fisico_quantidade.sql
-- Corrige o campo "AIH Físico" para ser tratado como QUANTIDADE, não valor (R$).
-- Execute este script no Supabase Dashboard (SQL Editor) UMA ÚNICA VEZ.
-- Idempotente: pode ser executado mais de uma vez sem efeitos colaterais.
-- ═══════════════════════════════════════════════════════════════════

-- 1) Garante que a tabela de configurações gerais existe (ver schema_sistema_config.sql)
CREATE TABLE IF NOT EXISTS sistema_config (
  id          SERIAL PRIMARY KEY,
  chave       TEXT UNIQUE NOT NULL,
  valor       TEXT,
  descricao   TEXT,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sistema_config (chave, valor, descricao) VALUES
  ('competencia_offset_meses', '-1',
   'Deslocamento em meses (relativo ao mês corrente) usado para pré-selecionar '
   'a competência ao inserir um novo registro. -1 = mês anterior, 0 = mês atual, 1 = mês seguinte.')
ON CONFLICT (chave) DO NOTHING;

-- 2) Corrige o tipo do campo "AIH Físico" em campo_config: de 'moeda' para 'numero'.
--    Os valores numéricos já salvos em teto_mac.aih_fisico não precisam de conversão
--    (são inteiros, ex: 600, 1970, 2309 — nunca tiveram casas decimais reais).
UPDATE campo_config
   SET tipo = 'numero', updated_at = NOW()
 WHERE campo_key = 'aih_fisico';

-- 3) Remove aih_fisico da fórmula de "AIH Total" (que soma apenas valores em R$;
--    misturar uma contagem de AIHs com valores monetários estava incorreto).
UPDATE campo_config
   SET formula = 'aih_faec,aih_mc,aih_ac', updated_at = NOW()
 WHERE campo_key = 'aih_total';

-- 4) IMPORTANTE — recalcula o valor JÁ SALVO de "AIH Total" em TODOS os registros
--    históricos de teto_mac, removendo a contagem de aih_fisico que havia sido
--    somada indevidamente no momento do cadastro/edição de cada linha (o campo
--    calculado é gravado como valor estático, não recalculado automaticamente).
--    Esse UPDATE afeta a tabela de produção inteira — revise antes de rodar.
UPDATE teto_mac
   SET aih_total = COALESCE(aih_faec,0) + COALESCE(aih_mc,0) + COALESCE(aih_ac,0)
 WHERE aih_total IS DISTINCT FROM (COALESCE(aih_faec,0) + COALESCE(aih_mc,0) + COALESCE(aih_ac,0));
