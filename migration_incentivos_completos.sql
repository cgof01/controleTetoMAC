-- ============================================================
-- Corrige as somas de incentivos nas RPCs do Supabase, que hoje esquecem
-- rede_brasil_miseria e os 5 campos guardados em campos_extras (rede_alyne,
-- pncp, rce_rceg_custeio, rau_hosp_sos_custeio, rca_rcan_custeio) — por isso o
-- "Total Incentivos" do Dashboard/Relatório por DRS podia divergir do total da
-- Central de Relatórios Analíticos para competências com esses campos preenchidos.
-- Também expande get_resumo_drs e get_historico_unidade para trazer cada
-- incentivo em coluna própria (antes só somavam tudo num único total, ou só
-- traziam integrasus/iac/sus_100).
-- Execute no Supabase: Dashboard -> SQL Editor -> New query. Idempotente
-- (CREATE OR REPLACE).
-- ============================================================

-- KPIs do dashboard
CREATE OR REPLACE FUNCTION get_kpis(p_ano INTEGER, p_mes INTEGER)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_build_object(
    'total_unidades', COUNT(*),
    'total_geral', COALESCE(SUM(total_mc_ac_incentivos), 0),
    'total_aih', COALESCE(SUM(aih_mc + aih_ac), 0),
    'total_sia', COALESCE(SUM(sia_mc + sia_ac), 0),
    'total_teto_mac', COALESCE(SUM(teto_mac + total_teto_mac), 0),
    'total_incentivos', COALESCE(SUM(
      integrasus + iac + sus_100 + opo + rede_viver_sem_limite + rede_brasil_miseria +
      rsme + rce_rceg + rau_hosp_sos + rca_rcan + iapi +
      residencia_medica + melhor_em_casa + cer + doencas_raras +
      oficina_ortopedica + ihac +
      COALESCE((campos_extras->>'rede_alyne')::numeric,0) +
      COALESCE((campos_extras->>'pncp')::numeric,0) +
      COALESCE((campos_extras->>'rce_rceg_custeio')::numeric,0) +
      COALESCE((campos_extras->>'rau_hosp_sos_custeio')::numeric,0) +
      COALESCE((campos_extras->>'rca_rcan_custeio')::numeric,0)
    ), 0)
  ) INTO resultado
  FROM teto_mac
  WHERE ano = p_ano AND mes = p_mes;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Resumo por DRS detalhado — cada incentivo (nativo + campos_extras) em coluna própria,
-- além de total_incentivos/total_geral (mesmo formato usado pela versão SQLite em database.py)
CREATE OR REPLACE FUNCTION get_resumo_drs(p_ano INTEGER, p_mes INTEGER)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT
      CAST(drs AS INTEGER) AS drs,
      COUNT(*) AS total_unidades,
      COALESCE(SUM(aih_fisico), 0) AS aih_fisico,
      COALESCE(SUM(aih_mc + aih_ac), 0) AS total_aih,
      COALESCE(SUM(sia_mc + sia_ac), 0) AS total_sia,
      COALESCE(SUM(teto_mac + total_teto_mac), 0) AS teto_mac,
      COALESCE(SUM(integrasus), 0) AS integrasus,
      COALESCE(SUM(iac), 0) AS iac,
      COALESCE(SUM(sus_100), 0) AS sus_100,
      COALESCE(SUM(opo), 0) AS opo,
      COALESCE(SUM(rede_viver_sem_limite), 0) AS rede_viver_sem_limite,
      COALESCE(SUM(rede_brasil_miseria), 0) AS rede_brasil_miseria,
      COALESCE(SUM(rsme), 0) AS rsme,
      COALESCE(SUM(rce_rceg), 0) AS rce_rceg,
      COALESCE(SUM(rau_hosp_sos), 0) AS rau_hosp_sos,
      COALESCE(SUM(rca_rcan), 0) AS rca_rcan,
      COALESCE(SUM(iapi), 0) AS iapi,
      COALESCE(SUM(residencia_medica), 0) AS residencia_medica,
      COALESCE(SUM(melhor_em_casa), 0) AS melhor_em_casa,
      COALESCE(SUM(cer), 0) AS cer,
      COALESCE(SUM(doencas_raras), 0) AS doencas_raras,
      COALESCE(SUM(oficina_ortopedica), 0) AS oficina_ortopedica,
      COALESCE(SUM(ihac), 0) AS ihac,
      COALESCE(SUM((campos_extras->>'rede_alyne')::numeric), 0) AS rede_alyne,
      COALESCE(SUM((campos_extras->>'pncp')::numeric), 0) AS pncp,
      COALESCE(SUM((campos_extras->>'rce_rceg_custeio')::numeric), 0) AS rce_rceg_custeio,
      COALESCE(SUM((campos_extras->>'rau_hosp_sos_custeio')::numeric), 0) AS rau_hosp_sos_custeio,
      COALESCE(SUM((campos_extras->>'rca_rcan_custeio')::numeric), 0) AS rca_rcan_custeio,
      COALESCE(SUM(
        integrasus + iac + sus_100 + opo + rede_viver_sem_limite + rede_brasil_miseria +
        rsme + rce_rceg + rau_hosp_sos + rca_rcan + iapi +
        residencia_medica + melhor_em_casa + cer + doencas_raras +
        oficina_ortopedica + ihac +
        COALESCE((campos_extras->>'rede_alyne')::numeric,0) +
        COALESCE((campos_extras->>'pncp')::numeric,0) +
        COALESCE((campos_extras->>'rce_rceg_custeio')::numeric,0) +
        COALESCE((campos_extras->>'rau_hosp_sos_custeio')::numeric,0) +
        COALESCE((campos_extras->>'rca_rcan_custeio')::numeric,0)
      ), 0) AS total_incentivos,
      COALESCE(SUM(total_mc_ac_incentivos), 0) AS total_geral
    FROM teto_mac
    WHERE ano = p_ano AND mes = p_mes AND drs IS NOT NULL
    GROUP BY CAST(drs AS INTEGER)
    ORDER BY CAST(drs AS INTEGER)
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Histórico de uma unidade por CNES — todos os incentivos individuais (nativos +
-- campos_extras), não só integrasus/iac/sus_100 (mesmo formato da versão SQLite
-- em database.py comparativo_unidade)
CREATE OR REPLACE FUNCTION get_historico_unidade(p_cnes TEXT)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT ano, mes, unidade, municipio, drs,
      COALESCE(total_mc_ac_incentivos, 0) AS total,
      COALESCE(aih_mc, 0) AS aih_mc,
      COALESCE(aih_ac, 0) AS aih_ac,
      COALESCE(sia_mc, 0) AS sia_mc,
      COALESCE(sia_ac, 0) AS sia_ac,
      COALESCE(teto_mac + total_teto_mac, 0) AS teto,
      COALESCE(integrasus, 0) AS integrasus,
      COALESCE(iac, 0) AS iac,
      COALESCE(sus_100, 0) AS sus_100,
      COALESCE(opo, 0) AS opo,
      COALESCE(rede_viver_sem_limite, 0) AS rede_viver_sem_limite,
      COALESCE(rede_brasil_miseria, 0) AS rede_brasil_miseria,
      COALESCE(rsme, 0) AS rsme,
      COALESCE(rce_rceg, 0) AS rce_rceg,
      COALESCE(rau_hosp_sos, 0) AS rau_hosp_sos,
      COALESCE(rca_rcan, 0) AS rca_rcan,
      COALESCE(iapi, 0) AS iapi,
      COALESCE(residencia_medica, 0) AS residencia_medica,
      COALESCE(melhor_em_casa, 0) AS melhor_em_casa,
      COALESCE(cer, 0) AS cer,
      COALESCE(doencas_raras, 0) AS doencas_raras,
      COALESCE(oficina_ortopedica, 0) AS oficina_ortopedica,
      COALESCE(ihac, 0) AS ihac,
      COALESCE((campos_extras->>'rede_alyne')::numeric, 0) AS rede_alyne,
      COALESCE((campos_extras->>'pncp')::numeric, 0) AS pncp,
      COALESCE((campos_extras->>'rce_rceg_custeio')::numeric, 0) AS rce_rceg_custeio,
      COALESCE((campos_extras->>'rau_hosp_sos_custeio')::numeric, 0) AS rau_hosp_sos_custeio,
      COALESCE((campos_extras->>'rca_rcan_custeio')::numeric, 0) AS rca_rcan_custeio
    FROM teto_mac
    WHERE cnes = p_cnes
    ORDER BY ano, mes
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

SELECT 'OK — get_kpis, get_resumo_drs e get_historico_unidade atualizados.' AS status;
