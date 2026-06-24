-- ============================================================
-- SISTEMA TETO MAC - SES-SP
-- Execute este SQL no Supabase: Dashboard → SQL Editor → New query
-- ============================================================

-- Tabela principal
CREATE TABLE IF NOT EXISTS teto_mac (
    id BIGSERIAL PRIMARY KEY,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    drs NUMERIC,
    tipo TEXT,
    hu TEXT,
    municipio TEXT,
    cnes TEXT,
    cnpj TEXT,
    unidade TEXT,
    aih_fisico NUMERIC DEFAULT 0,
    aih_faec NUMERIC DEFAULT 0,
    sia_faec NUMERIC DEFAULT 0,
    equip_hemodialise NUMERIC DEFAULT 0,
    limite_complementacao NUMERIC DEFAULT 0,
    aih_mc NUMERIC DEFAULT 0,
    aih_ac NUMERIC DEFAULT 0,
    aih_total NUMERIC DEFAULT 0,
    sia_mc NUMERIC DEFAULT 0,
    sia_ac NUMERIC DEFAULT 0,
    sia_total NUMERIC DEFAULT 0,
    teto_global NUMERIC DEFAULT 0,
    teto_mc NUMERIC DEFAULT 0,
    teto_ac NUMERIC DEFAULT 0,
    teto_mac NUMERIC DEFAULT 0,
    total_teto_mac NUMERIC DEFAULT 0,
    portaria_ms_gm_8516 NUMERIC DEFAULT 0,
    integrasus NUMERIC DEFAULT 0,
    iac NUMERIC DEFAULT 0,
    sus_100 NUMERIC DEFAULT 0,
    opo NUMERIC DEFAULT 0,
    rede_viver_sem_limite NUMERIC DEFAULT 0,
    rede_brasil_miseria NUMERIC DEFAULT 0,
    rsme NUMERIC DEFAULT 0,
    rce_rceg NUMERIC DEFAULT 0,
    rau_hosp_sos NUMERIC DEFAULT 0,
    rca_rcan NUMERIC DEFAULT 0,
    iapi NUMERIC DEFAULT 0,
    residencia_medica NUMERIC DEFAULT 0,
    melhor_em_casa NUMERIC DEFAULT 0,
    cer NUMERIC DEFAULT 0,
    doencas_raras NUMERIC DEFAULT 0,
    oficina_ortopedica NUMERIC DEFAULT 0,
    ihac NUMERIC DEFAULT 0,
    total_mc_ac_incentivos NUMERIC DEFAULT 0,
    arquivo_origem TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_teto_ano_mes ON teto_mac(ano, mes);
CREATE INDEX IF NOT EXISTS idx_teto_cnes ON teto_mac(cnes);
CREATE INDEX IF NOT EXISTS idx_teto_municipio ON teto_mac(municipio);
CREATE INDEX IF NOT EXISTS idx_teto_drs ON teto_mac(drs);

-- Tabela de histórico de importações
CREATE TABLE IF NOT EXISTS importacoes (
    id BIGSERIAL PRIMARY KEY,
    arquivo TEXT NOT NULL,
    ano INTEGER,
    mes INTEGER,
    total_registros INTEGER DEFAULT 0,
    registros_importados INTEGER DEFAULT 0,
    registros_erro INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pendente',
    mensagem TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- FUNÇÕES RPC para relatórios e gráficos (chamadas via HTTPS)
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
      integrasus + iac + sus_100 + opo + rede_viver_sem_limite +
      rsme + rce_rceg + rau_hosp_sos + rca_rcan + iapi +
      residencia_medica + melhor_em_casa + cer + doencas_raras +
      oficina_ortopedica + ihac
    ), 0)
  ) INTO resultado
  FROM teto_mac
  WHERE ano = p_ano AND mes = p_mes;
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
    GROUP BY ano, mes
    ORDER BY ano, mes
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Dados por DRS para um mês
CREATE OR REPLACE FUNCTION get_por_drs(p_ano INTEGER, p_mes INTEGER)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT CAST(drs AS INTEGER) AS drs,
      COALESCE(SUM(total_mc_ac_incentivos), 0) AS total,
      COUNT(*) AS unidades
    FROM teto_mac
    WHERE ano = p_ano AND mes = p_mes AND drs IS NOT NULL
    GROUP BY CAST(drs AS INTEGER)
    ORDER BY total DESC
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Top unidades
CREATE OR REPLACE FUNCTION get_top_unidades(p_ano INTEGER, p_mes INTEGER, p_limite INTEGER DEFAULT 15)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT unidade, municipio,
      COALESCE(total_mc_ac_incentivos, 0) AS total
    FROM teto_mac
    WHERE ano = p_ano AND mes = p_mes AND total_mc_ac_incentivos > 0
    ORDER BY total_mc_ac_incentivos DESC
    LIMIT p_limite
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Distribuição por tipo
CREATE OR REPLACE FUNCTION get_por_tipo(p_ano INTEGER, p_mes INTEGER)
RETURNS JSON AS $$
DECLARE resultado JSON;
BEGIN
  SELECT json_agg(row_to_json(t)) INTO resultado FROM (
    SELECT
      CASE
        WHEN tipo ILIKE '%PRÓPRIOS%' OR tipo ILIKE '%PROPRIOS%' THEN 'Rede Própria'
        WHEN tipo ILIKE '%PRIVADOS%' THEN 'Privados'
        ELSE COALESCE(tipo, 'Outros')
      END AS tipo_agrupado,
      COALESCE(SUM(total_mc_ac_incentivos), 0) AS total,
      COUNT(*) AS unidades
    FROM teto_mac
    WHERE ano = p_ano AND mes = p_mes
    GROUP BY tipo_agrupado
    ORDER BY total DESC
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Resumo por DRS detalhado
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
      COALESCE(SUM(
        integrasus + iac + sus_100 + opo + rede_viver_sem_limite +
        rsme + rce_rceg + rau_hosp_sos + rca_rcan + iapi +
        residencia_medica + melhor_em_casa + cer + doencas_raras +
        oficina_ortopedica + ihac
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
  ) INTO resultado FROM teto_mac;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- Histórico de uma unidade por CNES
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
      COALESCE(sus_100, 0) AS sus_100
    FROM teto_mac
    WHERE cnes = p_cnes
    ORDER BY ano, mes
  ) t;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TABELA DE USUÁRIOS
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT DEFAULT 'usuario',   -- 'admin' ou 'usuario'
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    ultimo_acesso TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- Desabilitar RLS para acesso interno
ALTER TABLE teto_mac DISABLE ROW LEVEL SECURITY;
ALTER TABLE importacoes DISABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;

-- ============================================================
-- USUÁRIO ADMIN INICIAL
-- Senha: 123456 (hash werkzeug pbkdf2:sha256)
-- Para gerar novo hash: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('123456'))"
-- ============================================================

INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
VALUES (
    'Adan Freire Pereira',
    'afpereira@saude.sp.gov.br',
    'scrypt:32768:8:1$LBwmdFHofSakmCW6$5ed4f3b42c515f03e7e364590034c7e2804f133531afadac98a75c3b0a7f027479a3a352da74f74b9c026feaa59a507cbe4bfe4a345126d4e39b918522ec25bd',
    'admin',
    TRUE
)
ON CONFLICT (email) DO NOTHING;

-- Confirmar
SELECT 'Schema criado com sucesso! Tabelas: teto_mac, importacoes, usuarios. Funcoes: 7 RPCs.' AS status;
