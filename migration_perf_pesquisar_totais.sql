-- ============================================================
-- Performance: soma dos totais da tela Consultar/Editar (Pesquisa) no banco
-- ============================================================
-- Hoje pesquisar_totais() baixa TODAS as linhas que batem com o filtro (paginando
-- de 1000 em 1000) só para somar os campos numéricos em Python. Com filtros fracos
-- (ou nenhum) isso baixa a tabela `teto_mac` inteira a cada carregamento da tela
-- de Consultar/Editar — a tela mais usada do sistema. Esta função faz a soma
-- direto no Postgres (uma única chamada, sem trafegar linha nenhuma pela rede).
--
-- O código em database.py tenta chamar esta RPC e, se ela ainda não existir
-- (função não aplicada / erro), cai automaticamente no caminho antigo — então é
-- seguro fazer o deploy do código antes de rodar esta migração, só não fica
-- rápido até você rodar este arquivo manualmente no SQL Editor do Supabase.

CREATE OR REPLACE FUNCTION pesquisar_totais(p_filtros JSONB DEFAULT '{}'::jsonb)
RETURNS JSON AS $$
DECLARE
  resultado JSON;
  where_sql TEXT := 'WHERE (drs IS NULL OR CAST(drs AS INTEGER) <> 99)';
BEGIN
  IF p_filtros ? 'ano' AND p_filtros->>'ano' <> '' THEN
    where_sql := where_sql || format(' AND ano = %L', (p_filtros->>'ano')::int);
  END IF;
  IF p_filtros ? 'mes' AND p_filtros->>'mes' <> '' THEN
    where_sql := where_sql || format(' AND mes = %L', (p_filtros->>'mes')::int);
  END IF;
  IF p_filtros ? 'drs' AND p_filtros->>'drs' <> '' THEN
    where_sql := where_sql || format(' AND drs = %L', (p_filtros->>'drs')::numeric);
  END IF;
  IF p_filtros ? 'municipio' AND p_filtros->>'municipio' <> '' THEN
    where_sql := where_sql || format(' AND municipio ILIKE %L', '%' || (p_filtros->>'municipio') || '%');
  END IF;
  IF p_filtros ? 'unidade' AND p_filtros->>'unidade' <> '' THEN
    where_sql := where_sql || format(' AND unidade ILIKE %L', '%' || (p_filtros->>'unidade') || '%');
  END IF;
  IF p_filtros ? 'cnes' AND p_filtros->>'cnes' <> '' THEN
    where_sql := where_sql || format(' AND cnes = %L', p_filtros->>'cnes');
  END IF;
  IF p_filtros ? 'cnpj' AND p_filtros->>'cnpj' <> '' THEN
    where_sql := where_sql || format(' AND cnpj ILIKE %L', '%' || (p_filtros->>'cnpj') || '%');
  END IF;
  IF p_filtros ? 'tipo' AND p_filtros->>'tipo' <> '' THEN
    where_sql := where_sql || format(' AND tipo ILIKE %L', '%' || (p_filtros->>'tipo') || '%');
  END IF;

  EXECUTE format('
    SELECT json_build_object(
      ''registros'', COUNT(*),
      ''aih_fisico'', COALESCE(SUM(aih_fisico),0),
      ''aih_faec'', COALESCE(SUM(aih_faec),0),
      ''sia_faec'', COALESCE(SUM(sia_faec),0),
      ''aih_mc'', COALESCE(SUM(aih_mc),0),
      ''aih_ac'', COALESCE(SUM(aih_ac),0),
      ''aih_total'', COALESCE(SUM(aih_total),0),
      ''sia_mc'', COALESCE(SUM(sia_mc),0),
      ''sia_ac'', COALESCE(SUM(sia_ac),0),
      ''sia_total'', COALESCE(SUM(sia_total),0),
      ''teto_mac'', COALESCE(SUM(teto_mac),0),
      ''total_teto_mac'', COALESCE(SUM(total_teto_mac),0),
      ''total_mc_ac_incentivos'', COALESCE(SUM(total_mc_ac_incentivos),0)
    ) FROM teto_mac %s', where_sql) INTO resultado;

  RETURN resultado;
END;
$$ LANGUAGE plpgsql;
