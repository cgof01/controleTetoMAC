-- ============================================================
-- Exclui DRS 99 (Reserva de Recurso) do Dashboard
-- ============================================================
-- DRS 99 é uma linha orçamentária de reserva (não uma unidade de saúde) que
-- aparece nas planilhas importadas com TIPO/CNES = 'RESREC' e
-- UNIDADE = 'RESERVA DE RECURSO'. A partir desta migração ela some dos KPIs,
-- da evolução mensal e das estatísticas gerais do Dashboard — continua
-- aparecendo normalmente no Resumo por DRS e na Central de Relatórios.
-- Rode este arquivo manualmente no SQL Editor do Supabase.

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
  WHERE ano = p_ano AND mes = p_mes
    AND (drs IS NULL OR CAST(drs AS INTEGER) <> 99);
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Evolução mensal (todos os anos)
CREATE OR REPLACE FUNCTION get_evolucao_mensal()
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT ano, mes,
      COALESCE(SUM(total_mc_ac_incentivos), 0) AS total,
      COUNT(*) AS unidades
    FROM teto_mac
    WHERE (drs IS NULL OR CAST(drs AS INTEGER) <> 99)
    GROUP BY ano, mes
    ORDER BY ano, mes
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Estatísticas gerais
CREATE OR REPLACE FUNCTION get_estatisticas_gerais()
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_build_object(
    'total_registros', COUNT(*),
    'total_unidades', COUNT(DISTINCT cnes),
    'total_municipios', COUNT(DISTINCT municipio),
    'total_drs', COUNT(DISTINCT CAST(drs AS INTEGER)),
    'ano_min', MIN(ano),
    'ano_max', MAX(ano),
    'total_competencias', COUNT(DISTINCT ano * 100 + mes)
  ) INTO resultado
  FROM teto_mac
  WHERE (drs IS NULL OR CAST(drs AS INTEGER) <> 99);
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;
