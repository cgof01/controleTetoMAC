-- ═══════════════════════════════════════════════════════════════════
-- schema_sistema_config.sql — Configurações gerais do sistema (chave/valor)
-- Execute este script no Supabase Dashboard (SQL Editor) UMA ÚNICA VEZ
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sistema_config (
  id          SERIAL PRIMARY KEY,
  chave       TEXT UNIQUE NOT NULL,
  valor       TEXT,
  descricao   TEXT,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Seed ──────────────────────────────────────────────────────────────────────
-- competencia_offset_meses: deslocamento em meses (relativo ao mês corrente do
-- servidor) usado para pré-selecionar a competência (ano/mês) na tela
-- "Inserir Novo Registro". -1 = mês anterior, 0 = mês atual, 1 = mês seguinte.
-- Editável em /admin/campos (card "Configurações do Sistema").
INSERT INTO sistema_config (chave, valor, descricao) VALUES
  ('competencia_offset_meses', '-1',
   'Deslocamento em meses (relativo ao mês corrente) usado para pré-selecionar '
   'a competência ao inserir um novo registro. -1 = mês anterior, 0 = mês atual, 1 = mês seguinte.')
ON CONFLICT (chave) DO NOTHING;
