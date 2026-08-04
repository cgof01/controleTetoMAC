-- ============================================================
-- Registra em campo_config os campos que a importação (import_xls.py)
-- já reconhecia e gravava em campos_extras (JSONB) — Rede Alyne, PNCP e as
-- variantes "Custeio" de RCE/RAU/RCA — mas que nunca tinham sido cadastrados
-- em campo_config. Por isso não apareciam no formulário Novo/Editar Registro
-- nem em Admin > Campos, mesmo a importação já capturando o valor.
-- coluna_db = NULL: o valor continua salvo dentro de campos_extras, não numa
-- coluna nova da tabela teto_mac (sem precisar de ALTER TABLE).
-- Execute no Supabase: Dashboard -> SQL Editor -> New query. Idempotente.
-- ============================================================

INSERT INTO campo_config (secao_key, campo_key, label, tipo, ordem, coluna_db) VALUES
  ('incentivos', 'rede_alyne',           'Rede Alyne',                                        'moeda', 180, NULL),
  ('incentivos', 'pncp',                 'Política Nacional de Cuidados Paliativos - PNCP',    'moeda', 190, NULL),
  ('incentivos', 'rce_rceg_custeio',     'RCE/RCEG - Custeio UTI',                             'moeda', 200, NULL),
  ('incentivos', 'rau_hosp_sos_custeio', 'RAU/Hosp. SOS - Custeio UTI',                        'moeda', 210, NULL),
  ('incentivos', 'rca_rcan_custeio',     'RCA/RCAN - Custeio',                                 'moeda', 220, NULL)
ON CONFLICT (campo_key) DO NOTHING;

SELECT 'OK — campos rede_alyne, pncp e as 3 variantes Custeio cadastrados em campo_config.' AS status;
