-- Corrige o card "TOTAL TETO MAC" do Dashboard em "Todos os anos", que estava
-- fixo em R$ 0,00 porque dashboard_kpis_geral() (database.py) nunca calculava
-- esse valor no caminho Supabase — só retornava total_geral e total_unidades,
-- com total_teto_mac/total_incentivos/total_aih/total_sia hardcoded em 0.
--
-- Cria o equivalente de get_kpis() (usada para um único mês) sem filtro de
-- ano/mês, somando todos os períodos — mesma exclusão de DRS 99 (Reserva de
-- Recurso) já usada em get_estatisticas_gerais().

CREATE OR REPLACE FUNCTION get_kpis_geral()
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
  WHERE (drs IS NULL OR CAST(drs AS INTEGER) <> 99);
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;
