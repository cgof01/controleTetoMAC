"""
database.py — Camada de dados usando Supabase (HTTPS/REST)
Fallback automático para SQLite em desenvolvimento.
"""
import os
from config import SUPABASE_URL, SUPABASE_KEY, USE_SUPABASE

MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}
MESES_PT = {v.upper(): k for k, v in MESES.items()}
MESES_PT.update({v: k for k, v in MESES.items()})

# ── Backend ────────────────────────────────────────────────────────────────────

if USE_SUPABASE:
    import httpx as _httpx
    _orig_httpx_init = _httpx.Client.__init__
    def _httpx_no_ssl(self, *args, **kwargs):
        kwargs['verify'] = False
        _orig_httpx_init(self, *args, **kwargs)
    _httpx.Client.__init__ = _httpx_no_ssl

    from supabase import create_client
    _sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    def get_sb():
        return _sb

    def init_db():
        pass  # tabelas criadas via schema_supabase.sql no dashboard

else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'teto_mac.db')

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db():
        _init_sqlite()

# ── Utilitários ────────────────────────────────────────────────────────────────

def _clean(row):
    """Normaliza None para 0 em campos numéricos."""
    if not row:
        return row
    num_fields = {
        'drs','aih_fisico','aih_faec','sia_faec','equip_hemodialise',
        'limite_complementacao','aih_mc','aih_ac','aih_total','sia_mc','sia_ac',
        'sia_total','teto_global','teto_mc','teto_ac','teto_mac','total_teto_mac',
        'portaria_ms_gm_8516','integrasus','iac','sus_100','opo',
        'rede_viver_sem_limite','rede_brasil_miseria','rsme','rce_rceg',
        'rau_hosp_sos','rca_rcan','iapi','residencia_medica','melhor_em_casa',
        'cer','doencas_raras','oficina_ortopedica','ihac','total_mc_ac_incentivos'
    }
    result = dict(row)
    for f in num_fields:
        if f in result and result[f] is None:
            result[f] = 0.0
    return result

# ── CRUD ───────────────────────────────────────────────────────────────────────

def inserir_registro(dados):
    dados_clean = {k: v for k, v in dados.items() if k not in ('id','created_at','updated_at')}
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').insert(dados_clean).execute()
        return r.data[0]['id'] if r.data else None
    else:
        conn = get_db()
        campos = list(dados_clean.keys())
        placeholders = ','.join(['?' for _ in campos])
        cur = conn.execute(
            f"INSERT INTO teto_mac ({','.join(campos)}) VALUES ({placeholders})",
            [dados_clean[k] for k in campos]
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

def atualizar_registro(id, dados):
    dados_clean = {k: v for k, v in dados.items() if k not in ('id','created_at','updated_at')}
    if USE_SUPABASE:
        get_sb().table('teto_mac').update(dados_clean).eq('id', id).execute()
    else:
        conn = get_db()
        campos = list(dados_clean.keys())
        set_clause = ', '.join([f'{k} = ?' for k in campos])
        conn.execute(
            f"UPDATE teto_mac SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [dados_clean[k] for k in campos] + [id]
        )
        conn.commit()
        conn.close()

def deletar_registro(id):
    if USE_SUPABASE:
        get_sb().table('teto_mac').delete().eq('id', id).execute()
    else:
        conn = get_db()
        conn.execute("DELETE FROM teto_mac WHERE id = ?", (id,))
        conn.commit()
        conn.close()

def buscar_registro(id):
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('*').eq('id', id).execute()
        return _clean(r.data[0]) if r.data else None
    else:
        conn = get_db()
        row = conn.execute("SELECT * FROM teto_mac WHERE id = ?", (id,)).fetchone()
        conn.close()
        return _clean(dict(row)) if row else None

# ── Pesquisa ───────────────────────────────────────────────────────────────────

def pesquisar(filtros=None, page=1, per_page=50):
    if USE_SUPABASE:
        return _pesquisar_supabase(filtros, page, per_page)
    else:
        return _pesquisar_sqlite(filtros, page, per_page)

def _pesquisar_supabase(filtros, page, per_page):
    sb = get_sb()
    q = sb.table('teto_mac').select('*', count='exact')

    if filtros:
        if filtros.get('ano'):
            q = q.eq('ano', int(filtros['ano']))
        if filtros.get('mes'):
            q = q.eq('mes', int(filtros['mes']))
        if filtros.get('drs'):
            q = q.eq('drs', float(filtros['drs']))
        if filtros.get('municipio'):
            q = q.ilike('municipio', f"%{filtros['municipio']}%")
        if filtros.get('unidade'):
            q = q.ilike('unidade', f"%{filtros['unidade']}%")
        if filtros.get('cnes'):
            q = q.eq('cnes', str(filtros['cnes']))
        if filtros.get('cnpj'):
            q = q.ilike('cnpj', f"%{filtros['cnpj']}%")
        if filtros.get('tipo'):
            q = q.ilike('tipo', f"%{filtros['tipo']}%")

    offset = (page - 1) * per_page
    q = q.order('ano', desc=True).order('mes', desc=True).order('unidade')
    q = q.range(offset, offset + per_page - 1)

    r = q.execute()
    total = r.count if r.count is not None else len(r.data)
    return [_clean(row) for row in r.data], total

def _pesquisar_sqlite(filtros, page, per_page):
    conn = get_db()
    where_parts = []
    params = []

    if filtros:
        if filtros.get('ano'):
            where_parts.append("ano = ?")
            params.append(int(filtros['ano']))
        if filtros.get('mes'):
            where_parts.append("mes = ?")
            params.append(int(filtros['mes']))
        if filtros.get('drs'):
            where_parts.append("CAST(drs AS INTEGER) = ?")
            params.append(int(filtros['drs']))
        if filtros.get('tipo'):
            where_parts.append("tipo LIKE ?")
            params.append(f"%{filtros['tipo']}%")
        if filtros.get('municipio'):
            where_parts.append("municipio LIKE ?")
            params.append(f"%{filtros['municipio'].upper()}%")
        if filtros.get('unidade'):
            where_parts.append("unidade LIKE ?")
            params.append(f"%{filtros['unidade'].upper()}%")
        if filtros.get('cnes'):
            where_parts.append("cnes = ?")
            params.append(str(filtros['cnes']))
        if filtros.get('cnpj'):
            where_parts.append("cnpj LIKE ?")
            params.append(f"%{filtros['cnpj']}%")

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    total = conn.execute(f"SELECT COUNT(*) FROM teto_mac {where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM teto_mac {where} ORDER BY ano DESC, mes DESC, unidade LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    conn.close()
    return [_clean(dict(r)) for r in rows], total

# ── Lookups ────────────────────────────────────────────────────────────────────

def obter_anos_meses():
    if USE_SUPABASE:
        # Reusa o RPC get_evolucao_mensal que retorna todos os pares ano/mes sem limite de linhas
        r = get_sb().rpc('get_evolucao_mensal', {}).execute()
        data = r.data if isinstance(r.data, list) else []
        result = sorted(
            [{'ano': d['ano'], 'mes': d['mes']} for d in data],
            key=lambda x: (x['ano'], x['mes']), reverse=True
        )
        return result
    else:
        conn = get_db()
        rows = conn.execute(
            "SELECT DISTINCT ano, mes FROM teto_mac ORDER BY ano DESC, mes DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def obter_drs_lista():
    if USE_SUPABASE:
        # Reutiliza get_por_drs com o mês mais recente para obter todos os DRS
        ams = obter_anos_meses()
        if ams:
            r = get_sb().rpc('get_por_drs', {'p_ano': ams[0]['ano'], 'p_mes': ams[0]['mes']}).execute()
            data = r.data if isinstance(r.data, list) else []
            return sorted(int(d['drs']) for d in data if d.get('drs') is not None)
        return []
    else:
        conn = get_db()
        rows = conn.execute(
            "SELECT DISTINCT CAST(drs AS INTEGER) as drs FROM teto_mac WHERE drs IS NOT NULL ORDER BY CAST(drs AS INTEGER)"
        ).fetchall()
        conn.close()
        return [r['drs'] for r in rows if r['drs']]

def obter_municipios():
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('municipio').order('municipio').limit(50000).execute()
        seen = set()
        result = []
        for row in r.data:
            m = row.get('municipio')
            if m and m not in seen:
                seen.add(m)
                result.append(m)
        return result
    else:
        conn = get_db()
        rows = conn.execute(
            "SELECT DISTINCT municipio FROM teto_mac WHERE municipio IS NOT NULL ORDER BY municipio"
        ).fetchall()
        conn.close()
        return [r['municipio'] for r in rows]

# ── Dashboard e Gráficos (via RPC) ────────────────────────────────────────────

def dashboard_kpis(ano=None, mes=None):
    if USE_SUPABASE:
        if not ano or not mes:
            ams = obter_anos_meses()
            if not ams:
                return {}
            ano, mes = ams[0]['ano'], ams[0]['mes']
        r = get_sb().rpc('get_kpis', {'p_ano': ano, 'p_mes': mes}).execute()
        return r.data if isinstance(r.data, dict) else {}
    else:
        return _dashboard_kpis_sqlite(ano, mes)

def _dashboard_kpis_sqlite(ano=None, mes=None):
    conn = get_db()
    if ano and mes:
        filtro = "WHERE ano = ? AND mes = ?"
        params = [ano, mes]
    else:
        ultimo = conn.execute("SELECT ano, mes FROM teto_mac ORDER BY ano DESC, mes DESC LIMIT 1").fetchone()
        if ultimo:
            filtro = "WHERE ano = ? AND mes = ?"
            params = [ultimo['ano'], ultimo['mes']]
        else:
            conn.close()
            return {}
    kpis = conn.execute(f"""
        SELECT COUNT(*) as total_unidades,
            SUM(total_mc_ac_incentivos) as total_geral,
            SUM(aih_mc + aih_ac) as total_aih,
            SUM(sia_mc + sia_ac) as total_sia,
            SUM(integrasus + iac + sus_100 + opo + rede_viver_sem_limite + rsme +
                rce_rceg + rau_hosp_sos + rca_rcan + iapi + residencia_medica +
                melhor_em_casa + cer + doencas_raras + oficina_ortopedica + ihac) as total_incentivos,
            SUM(teto_mac + total_teto_mac) as total_teto_mac
        FROM teto_mac {filtro}
    """, params).fetchone()
    conn.close()
    return dict(kpis) if kpis else {}

def grafico_evolucao_mensal(anos=None):
    if USE_SUPABASE:
        r = get_sb().rpc('get_evolucao_mensal', {}).execute()
        data = r.data if isinstance(r.data, list) else []
        if anos:
            data = [d for d in data if d.get('ano') in anos]
        return data
    else:
        conn = get_db()
        if anos:
            placeholders = ','.join(['?' for _ in anos])
            rows = conn.execute(f"""
                SELECT ano, mes, SUM(total_mc_ac_incentivos) as total, COUNT(*) as unidades
                FROM teto_mac WHERE ano IN ({placeholders})
                GROUP BY ano, mes ORDER BY ano, mes
            """, anos).fetchall()
        else:
            rows = conn.execute("""
                SELECT ano, mes, SUM(total_mc_ac_incentivos) as total, COUNT(*) as unidades
                FROM teto_mac GROUP BY ano, mes ORDER BY ano, mes
            """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def grafico_por_drs(ano, mes):
    if USE_SUPABASE:
        r = get_sb().rpc('get_por_drs', {'p_ano': ano, 'p_mes': mes}).execute()
        return r.data if isinstance(r.data, list) else []
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT CAST(drs AS INTEGER) as drs,
                SUM(total_mc_ac_incentivos) as total, COUNT(*) as unidades
            FROM teto_mac WHERE ano = ? AND mes = ? AND drs IS NOT NULL
            GROUP BY CAST(drs AS INTEGER) ORDER BY total DESC
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

_EXCLUIR_UNIDADES = ('TOTAL', 'SUBTOTAL', 'TOTAL GERAL', 'GERAL')

def _filtrar_totais(dados):
    return [
        d for d in dados
        if not any(
            ex == (d.get('unidade') or '').upper().strip()
            for ex in _EXCLUIR_UNIDADES
        )
    ]

def grafico_top_unidades(ano, mes, limite=15):
    if USE_SUPABASE:
        r = get_sb().rpc('get_top_unidades', {'p_ano': ano, 'p_mes': mes, 'p_limite': limite + 5}).execute()
        dados = r.data if isinstance(r.data, list) else []
        return _filtrar_totais(dados)[:limite]
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT unidade, municipio, total_mc_ac_incentivos as total
            FROM teto_mac
            WHERE ano = ? AND mes = ? AND total_mc_ac_incentivos > 0
              AND UPPER(TRIM(unidade)) NOT IN ('TOTAL','SUBTOTAL','TOTAL GERAL','GERAL')
            ORDER BY total DESC LIMIT ?
        """, (ano, mes, limite)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def grafico_por_tipo(ano, mes):
    if USE_SUPABASE:
        r = get_sb().rpc('get_por_tipo', {'p_ano': ano, 'p_mes': mes}).execute()
        return r.data if isinstance(r.data, list) else []
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT
              CASE
                WHEN tipo LIKE '%PRÓPRIOS%' OR tipo LIKE '%PROPRIOS%' THEN 'Rede Própria'
                WHEN tipo LIKE '%PRIVADOS%' THEN 'Privados'
                ELSE COALESCE(tipo, 'Outros')
              END as tipo_agrupado,
              SUM(total_mc_ac_incentivos) as total, COUNT(*) as unidades
            FROM teto_mac WHERE ano = ? AND mes = ?
            GROUP BY tipo_agrupado ORDER BY total DESC
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def relatorio_por_unidade(ano, mes):
    """Ranking de unidades por total no período."""
    excl = "('TOTAL','SUBTOTAL','TOTAL GERAL','GERAL')"
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select(
            'unidade,cnes,municipio,drs,aih_mc,aih_ac,sia_mc,sia_ac,total_mc_ac_incentivos'
        ).eq('ano', ano).eq('mes', mes).order('total_mc_ac_incentivos', desc=True).limit(1000).execute()
        data = r.data or []
        seen = {}
        for row in data:
            un = (row.get('unidade') or '').strip().upper()
            if un in ('TOTAL', 'SUBTOTAL', 'TOTAL GERAL', 'GERAL'):
                continue
            key = (row.get('cnes') or '', row.get('unidade') or '')
            if key not in seen:
                seen[key] = {'unidade': row.get('unidade', ''), 'cnes': row.get('cnes', ''),
                             'municipio': row.get('municipio', ''), 'drs': row.get('drs', 0),
                             'total_aih': 0.0, 'total_sia': 0.0, 'total_geral': 0.0}
            seen[key]['total_aih'] += (row.get('aih_mc') or 0) + (row.get('aih_ac') or 0)
            seen[key]['total_sia'] += (row.get('sia_mc') or 0) + (row.get('sia_ac') or 0)
            seen[key]['total_geral'] += row.get('total_mc_ac_incentivos') or 0
        return sorted(seen.values(), key=lambda x: x['total_geral'], reverse=True)
    else:
        conn = get_db()
        rows = conn.execute(f"""
            SELECT unidade, cnes, municipio, CAST(drs AS INTEGER) as drs,
                SUM(aih_mc + aih_ac) as total_aih, SUM(sia_mc + sia_ac) as total_sia,
                SUM(total_mc_ac_incentivos) as total_geral
            FROM teto_mac WHERE ano=? AND mes=?
              AND UPPER(TRIM(COALESCE(unidade,''))) NOT IN {excl}
            GROUP BY cnes, unidade ORDER BY total_geral DESC
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def relatorio_por_municipio(ano, mes):
    """Totais agrupados por município."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select(
            'municipio,aih_mc,aih_ac,sia_mc,sia_ac,total_mc_ac_incentivos'
        ).eq('ano', ano).eq('mes', mes).execute()
        data = r.data or []
        seen = {}
        for row in data:
            mun = (row.get('municipio') or 'Não Informado').strip()
            if mun not in seen:
                seen[mun] = {'municipio': mun, 'unidades': 0,
                             'total_aih': 0.0, 'total_sia': 0.0, 'total_geral': 0.0}
            seen[mun]['unidades'] += 1
            seen[mun]['total_aih'] += (row.get('aih_mc') or 0) + (row.get('aih_ac') or 0)
            seen[mun]['total_sia'] += (row.get('sia_mc') or 0) + (row.get('sia_ac') or 0)
            seen[mun]['total_geral'] += row.get('total_mc_ac_incentivos') or 0
        return sorted(seen.values(), key=lambda x: x['total_geral'], reverse=True)
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(municipio),''), 'Não Informado') as municipio,
                COUNT(*) as unidades,
                SUM(aih_mc + aih_ac) as total_aih,
                SUM(sia_mc + sia_ac) as total_sia,
                SUM(total_mc_ac_incentivos) as total_geral
            FROM teto_mac WHERE ano=? AND mes=?
            GROUP BY COALESCE(NULLIF(TRIM(municipio),''), 'Não Informado')
            ORDER BY total_geral DESC
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def relatorio_fundo(ano, mes):
    """Componentes FAEC + MAC agrupados por DRS."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select(
            'drs,aih_fisico,aih_faec,sia_faec,equip_hemodialise,limite_complementacao,'
            'aih_mc,aih_ac,sia_mc,sia_ac,total_mc_ac_incentivos'
        ).eq('ano', ano).eq('mes', mes).execute()
        data = r.data or []
        seen = {}
        for row in data:
            drs = int(row.get('drs') or 0)
            if drs not in seen:
                seen[drs] = {k: 0.0 for k in ['aih_fisico','aih_faec','sia_faec',
                             'equip_hemodialise','limite_complementacao',
                             'aih_mc','aih_ac','sia_mc','sia_ac','total']}
                seen[drs]['drs'] = drs
            for k in ['aih_fisico','aih_faec','sia_faec','equip_hemodialise',
                      'limite_complementacao','aih_mc','aih_ac','sia_mc','sia_ac']:
                seen[drs][k] += row.get(k) or 0
            seen[drs]['total'] += row.get('total_mc_ac_incentivos') or 0
        return sorted(seen.values(), key=lambda x: x['drs'])
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT CAST(drs AS INTEGER) as drs,
                SUM(aih_fisico) as aih_fisico, SUM(aih_faec) as aih_faec,
                SUM(sia_faec) as sia_faec, SUM(equip_hemodialise) as equip_hemodialise,
                SUM(limite_complementacao) as limite_complementacao,
                SUM(aih_mc) as aih_mc, SUM(aih_ac) as aih_ac,
                SUM(sia_mc) as sia_mc, SUM(sia_ac) as sia_ac,
                SUM(total_mc_ac_incentivos) as total
            FROM teto_mac WHERE ano=? AND mes=? AND drs IS NOT NULL
            GROUP BY CAST(drs AS INTEGER) ORDER BY CAST(drs AS INTEGER)
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def relatorio_incentivos(ano, mes):
    """Totais de cada incentivo individual."""
    INCENTIVOS = [
        ('integrasus','IntegraSUS'), ('iac','IAC'), ('sus_100','100% SUS'),
        ('opo','OPO'), ('rede_viver_sem_limite','Rede Viver Sem Limite'),
        ('rede_brasil_miseria','Rede Brasil Sem Miséria'), ('rsme','RSME'),
        ('rce_rceg','RCE/RCEG'), ('rau_hosp_sos','RAU/Hosp. SOS'),
        ('rca_rcan','RCA/RCAN'), ('iapi','IAPI'), ('residencia_medica','Residência Médica'),
        ('melhor_em_casa','Melhor em Casa'), ('cer','CER'),
        ('doencas_raras','Doenças Raras'), ('oficina_ortopedica','Oficina Ortopédica'),
        ('ihac','IHAC'),
    ]
    if USE_SUPABASE:
        cols = ','.join(k for k, _ in INCENTIVOS)
        r = get_sb().table('teto_mac').select(cols).eq('ano', ano).eq('mes', mes).execute()
        data = r.data or []
        totais = {k: 0.0 for k, _ in INCENTIVOS}
        for row in data:
            for k, _ in INCENTIVOS:
                totais[k] += row.get(k) or 0
        return [{'campo': k, 'label': lbl, 'total': totais[k]} for k, lbl in INCENTIVOS]
    else:
        conn = get_db()
        sel = ', '.join(f'SUM(COALESCE({k},0)) as {k}' for k, _ in INCENTIVOS)
        row = conn.execute(f"SELECT {sel} FROM teto_mac WHERE ano=? AND mes=?",
                          (ano, mes)).fetchone()
        conn.close()
        if not row:
            return []
        r = dict(row)
        return [{'campo': k, 'label': lbl, 'total': r.get(k) or 0} for k, lbl in INCENTIVOS]


def relatorio_resumo_drs(ano, mes):
    if USE_SUPABASE:
        r = get_sb().rpc('get_resumo_drs', {'p_ano': ano, 'p_mes': mes}).execute()
        return r.data if isinstance(r.data, list) else []
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT CAST(drs AS INTEGER) as drs, COUNT(*) as total_unidades,
                SUM(aih_fisico) as aih_fisico, SUM(aih_mc + aih_ac) as total_aih,
                SUM(sia_mc + sia_ac) as total_sia, SUM(teto_mac + total_teto_mac) as teto_mac,
                SUM(integrasus + iac + sus_100 + opo + rede_viver_sem_limite + rsme +
                    rce_rceg + rau_hosp_sos + rca_rcan + iapi + residencia_medica +
                    melhor_em_casa + cer + doencas_raras + oficina_ortopedica + ihac) as total_incentivos,
                SUM(total_mc_ac_incentivos) as total_geral
            FROM teto_mac WHERE ano = ? AND mes = ? AND drs IS NOT NULL
            GROUP BY CAST(drs AS INTEGER) ORDER BY CAST(drs AS INTEGER)
        """, (ano, mes)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def relatorio_periodo(ano_ini, mes_ini, ano_fim, mes_fim):
    if USE_SUPABASE:
        r = (get_sb().table('teto_mac')
            .select('ano,mes,drs,tipo,municipio,cnes,cnpj,unidade,aih_mc,aih_ac,sia_mc,sia_ac,teto_mac,total_teto_mac,total_mc_ac_incentivos')
            .gte('ano', ano_ini)
            .lte('ano', ano_fim)
            .order('ano').order('mes').order('unidade')
            .limit(5000)
            .execute())
        # filtrar mes_ini e mes_fim
        result = []
        for row in r.data:
            val = row['ano'] * 100 + row['mes']
            if ano_ini * 100 + mes_ini <= val <= ano_fim * 100 + mes_fim:
                result.append(_clean(row))
        return result
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT ano, mes, drs, tipo, municipio, cnes, cnpj, unidade,
                aih_mc, aih_ac, sia_mc, sia_ac, teto_mac, total_teto_mac, total_mc_ac_incentivos
            FROM teto_mac
            WHERE (ano * 100 + mes) BETWEEN ? AND ?
            ORDER BY ano, mes, unidade
        """, (ano_ini * 100 + mes_ini, ano_fim * 100 + mes_fim)).fetchall()
        conn.close()
        return [_clean(dict(r)) for r in rows]

def comparativo_unidade(cnes, ano_ini=2022, ano_fim=2026):
    if USE_SUPABASE:
        r = (get_sb().rpc('get_historico_unidade', {'p_cnes': str(cnes)}).execute())
        return r.data if isinstance(r.data, list) else []
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT ano, mes, unidade, municipio, drs,
                total_mc_ac_incentivos as total, aih_mc, aih_ac, sia_mc, sia_ac,
                teto_mac + total_teto_mac as teto,
                integrasus, iac, sus_100
            FROM teto_mac WHERE cnes = ? AND ano BETWEEN ? AND ?
            ORDER BY ano, mes
        """, (str(cnes), ano_ini, ano_fim)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def buscar_unidades_autocomplete(termo):
    if USE_SUPABASE:
        r = (get_sb().table('teto_mac')
            .select('cnes,cnpj,unidade,municipio')
            .ilike('unidade', f"%{termo.upper()}%")
            .limit(20)
            .execute())
        seen = set()
        result = []
        for row in r.data:
            if row.get('cnes') not in seen:
                seen.add(row.get('cnes'))
                result.append(row)
        return result
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT DISTINCT cnes, cnpj, unidade, municipio
            FROM teto_mac WHERE unidade LIKE ? OR cnes LIKE ? OR cnpj LIKE ?
            ORDER BY unidade LIMIT 20
        """, (f"%{termo.upper()}%", f"%{termo}%", f"%{termo}%")).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def estatisticas_gerais():
    if USE_SUPABASE:
        r = get_sb().rpc('get_estatisticas_gerais', {}).execute()
        return r.data if isinstance(r.data, dict) else {}
    else:
        conn = get_db()
        stats = conn.execute("""
            SELECT COUNT(*) as total_registros,
                COUNT(DISTINCT cnes) as total_unidades,
                COUNT(DISTINCT municipio) as total_municipios,
                COUNT(DISTINCT CAST(drs AS INTEGER)) as total_drs,
                MIN(ano) as ano_min, MAX(ano) as ano_max,
                COUNT(DISTINCT ano * 100 + mes) as total_competencias
            FROM teto_mac
        """).fetchone()
        conn.close()
        return dict(stats) if stats else {}

# ── Usuários ───────────────────────────────────────────────────────────────────

def buscar_usuario_por_email(email):
    if USE_SUPABASE:
        r = get_sb().table('usuarios').select('*').eq('email', email.lower()).eq('ativo', True).limit(1).execute()
        return r.data[0] if r.data else None
    else:
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", (email.lower(),)).fetchone()
        conn.close()
        return dict(row) if row else None

def buscar_usuario_por_id(id):
    if USE_SUPABASE:
        r = get_sb().table('usuarios').select('*').eq('id', id).limit(1).execute()
        return r.data[0] if r.data else None
    else:
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
        conn.close()
        return dict(row) if row else None

def listar_usuarios():
    if USE_SUPABASE:
        r = get_sb().table('usuarios').select('*').order('nome').execute()
        return r.data if r.data else []
    else:
        conn = get_db()
        rows = conn.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()
        conn.close()
        return [dict(r) for r in rows]

def criar_usuario(nome, email, senha_hash, perfil='usuario'):
    dados = {'nome': nome, 'email': email.lower(), 'senha_hash': senha_hash, 'perfil': perfil, 'ativo': True}
    if USE_SUPABASE:
        r = get_sb().table('usuarios').insert(dados).execute()
        return r.data[0]['id'] if r.data else None
    else:
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo) VALUES (?,?,?,?,1)",
            (nome, email.lower(), senha_hash, perfil)
        )
        conn.commit()
        uid = cur.lastrowid
        conn.close()
        return uid

def editar_usuario_db(id, nome, email, perfil, ativo):
    if USE_SUPABASE:
        get_sb().table('usuarios').update({
            'nome': nome, 'email': email.lower(), 'perfil': perfil, 'ativo': bool(ativo)
        }).eq('id', id).execute()
    else:
        conn = get_db()
        conn.execute(
            "UPDATE usuarios SET nome=?, email=?, perfil=?, ativo=? WHERE id=?",
            (nome, email.lower(), perfil, int(ativo), id)
        )
        conn.commit()
        conn.close()

def deletar_usuario_db(id):
    if USE_SUPABASE:
        get_sb().table('usuarios').delete().eq('id', id).execute()
    else:
        conn = get_db()
        conn.execute("DELETE FROM usuarios WHERE id=?", (id,))
        conn.commit()
        conn.close()

def atualizar_senha(id, senha_hash):
    if USE_SUPABASE:
        get_sb().table('usuarios').update({'senha_hash': senha_hash}).eq('id', id).execute()
    else:
        conn = get_db()
        conn.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (senha_hash, id))
        conn.commit()
        conn.close()

def dashboard_kpis_geral():
    """KPIs consolidados de todos os períodos."""
    if USE_SUPABASE:
        ev = grafico_evolucao_mensal()
        stats = estatisticas_gerais()
        total_geral = sum(d.get('total', 0) or 0 for d in ev)
        return {
            'total_geral': total_geral,
            'total_unidades': stats.get('total_unidades', 0),
            'total_teto_mac': 0,
            'total_incentivos': 0,
            'total_aih': 0,
            'total_sia': 0,
        }
    else:
        conn = get_db()
        row = conn.execute("""
            SELECT COUNT(*) as total_unidades,
                COALESCE(SUM(total_mc_ac_incentivos),0) as total_geral,
                COALESCE(SUM(aih_mc + aih_ac),0) as total_aih,
                COALESCE(SUM(sia_mc + sia_ac),0) as total_sia,
                COALESCE(SUM(teto_mac + total_teto_mac),0) as total_teto_mac,
                COALESCE(SUM(integrasus+iac+sus_100+opo+rede_viver_sem_limite+rsme+
                    rce_rceg+rau_hosp_sos+rca_rcan+iapi+residencia_medica+
                    melhor_em_casa+cer+doencas_raras+oficina_ortopedica+ihac),0) as total_incentivos
            FROM teto_mac
        """).fetchone()
        conn.close()
        return dict(row) if row else {}

# ── Auditoria ─────────────────────────────────────────────────────────────────

def auditoria_validacao(ano, mes):
    """Relatório de qualidade de dados para um período."""
    if USE_SUPABASE:
        sb = get_sb()
        base = sb.table('teto_mac').select('id', count='exact')
        total = (base.eq('ano', ano).eq('mes', mes).execute()).count or 0
        sem_cnes = (sb.table('teto_mac').select('id', count='exact')
                    .eq('ano', ano).eq('mes', mes)
                    .or_('cnes.is.null,cnes.eq.').execute()).count or 0
        sem_valor = (sb.table('teto_mac').select('id', count='exact')
                     .eq('ano', ano).eq('mes', mes)
                     .lte('total_mc_ac_incentivos', 0).execute()).count or 0
        sem_drs = (sb.table('teto_mac').select('id', count='exact')
                   .eq('ano', ano).eq('mes', mes)
                   .or_('drs.is.null,drs.eq.0').execute()).count or 0
        return {'total': total, 'sem_cnes': sem_cnes, 'sem_valor': sem_valor,
                'sem_drs': sem_drs, 'duplicatas': 0, 'problemas': [], 'duplicatas_lista': []}
    else:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=?", (ano, mes)).fetchone()[0]
        sem_cnes  = conn.execute("SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND (cnes IS NULL OR TRIM(cnes)='')", (ano, mes)).fetchone()[0]
        sem_valor = conn.execute("SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND (total_mc_ac_incentivos IS NULL OR total_mc_ac_incentivos<=0)", (ano, mes)).fetchone()[0]
        sem_drs   = conn.execute("SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND (drs IS NULL OR drs=0)", (ano, mes)).fetchone()[0]
        dup_rows  = conn.execute("""
            SELECT cnes, COUNT(*) as c, GROUP_CONCAT(unidade, ' | ') as unidades
            FROM teto_mac WHERE ano=? AND mes=? AND cnes IS NOT NULL AND TRIM(cnes)!=''
            GROUP BY cnes HAVING c > 1 LIMIT 50
        """, (ano, mes)).fetchall()
        duplicatas = sum(r['c'] - 1 for r in dup_rows)
        prob_rows = conn.execute("""
            SELECT id, cnes, unidade, municipio, CAST(drs AS INTEGER) as drs,
                   total_mc_ac_incentivos,
                   CASE
                     WHEN cnes IS NULL OR TRIM(cnes)='' THEN 'Sem CNES'
                     WHEN total_mc_ac_incentivos IS NULL OR total_mc_ac_incentivos<=0 THEN 'Valor zero/nulo'
                     WHEN drs IS NULL OR drs=0 THEN 'Sem DRS'
                     ELSE 'Problema'
                   END as problema
            FROM teto_mac
            WHERE ano=? AND mes=? AND (
              cnes IS NULL OR TRIM(cnes)='' OR
              total_mc_ac_incentivos IS NULL OR total_mc_ac_incentivos<=0 OR
              drs IS NULL OR drs=0
            ) LIMIT 200
        """, (ano, mes)).fetchall()
        conn.close()
        return {
            'total': total, 'sem_cnes': sem_cnes, 'sem_valor': sem_valor,
            'sem_drs': sem_drs, 'duplicatas': duplicatas,
            'problemas': [dict(r) for r in prob_rows],
            'duplicatas_lista': [dict(r) for r in dup_rows]
        }

def auditoria_registros(ano, mes, drs=None, busca=None, page=1, per_page=50):
    """Registros paginados filtrados para auditoria."""
    if USE_SUPABASE:
        sb = get_sb()
        sel = 'id,cnes,unidade,municipio,drs,tipo,total_mc_ac_incentivos,teto_mac,total_teto_mac,aih_mc,aih_ac,sia_mc,sia_ac,arquivo_origem'
        q = sb.table('teto_mac').select(sel).eq('ano', ano).eq('mes', mes)
        qc = sb.table('teto_mac').select('id', count='exact').eq('ano', ano).eq('mes', mes)
        if drs:
            q  = q.eq('drs', drs)
            qc = qc.eq('drs', drs)
        if busca:
            q  = q.ilike('unidade', f'%{busca}%')
            qc = qc.ilike('unidade', f'%{busca}%')
        total = (qc.execute()).count or 0
        offset = (page - 1) * per_page
        r = q.order('total_mc_ac_incentivos', desc=True).range(offset, offset + per_page - 1).execute()
        return r.data or [], total
    else:
        conn = get_db()
        conds = ['ano=? AND mes=?']
        params = [ano, mes]
        if drs:
            conds.append('CAST(drs AS INTEGER)=?')
            params.append(int(drs))
        if busca:
            conds.append('(unidade LIKE ? OR cnes LIKE ? OR municipio LIKE ?)')
            b = f'%{busca}%'
            params.extend([b, b, b])
        where = ' AND '.join(conds)
        total = conn.execute(f'SELECT COUNT(*) FROM teto_mac WHERE {where}', params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(f"""
            SELECT id, cnes, unidade, municipio, CAST(drs AS INTEGER) as drs, tipo,
                   total_mc_ac_incentivos, teto_mac, total_teto_mac,
                   aih_mc, aih_ac, sia_mc, sia_ac, arquivo_origem
            FROM teto_mac WHERE {where}
            ORDER BY total_mc_ac_incentivos DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()
        conn.close()
        return [dict(r) for r in rows], total

def auditoria_deletar_ids(ids):
    """Deleta registros por lista de IDs."""
    if not ids:
        return 0
    if USE_SUPABASE:
        get_sb().table('teto_mac').delete().in_('id', ids).execute()
    else:
        conn = get_db()
        ph = ','.join(['?' for _ in ids])
        cur = conn.execute(f'DELETE FROM teto_mac WHERE id IN ({ph})', ids)
        conn.commit()
        conn.close()
        return cur.rowcount
    return len(ids)

def auditoria_deletar_periodo(ano, mes):
    """Deleta todos os registros de um período."""
    if USE_SUPABASE:
        get_sb().table('teto_mac').delete().eq('ano', ano).eq('mes', mes).execute()
    else:
        conn = get_db()
        cur = conn.execute('DELETE FROM teto_mac WHERE ano=? AND mes=?', (ano, mes))
        conn.commit()
        conn.close()
        return cur.rowcount

def auditoria_comparar(registros_xls, ano, mes):
    """Compara planilha com banco. Retorna diffs."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select(
            'id,cnes,unidade,total_mc_ac_incentivos,teto_mac,aih_mc,aih_ac,sia_mc,sia_ac'
        ).eq('ano', ano).eq('mes', mes).execute()
        db_rows = r.data or []
    else:
        conn = get_db()
        rows = conn.execute("""
            SELECT id, cnes, unidade, total_mc_ac_incentivos, teto_mac, aih_mc, aih_ac, sia_mc, sia_ac
            FROM teto_mac WHERE ano=? AND mes=?
        """, (ano, mes)).fetchall()
        conn.close()
        db_rows = [dict(r) for r in rows]

    db_idx  = {str(r['cnes']): r for r in db_rows if r.get('cnes')}
    xls_idx = {str(r.get('cnes','')): r for r in registros_xls if r.get('cnes')}

    apenas_db, apenas_xls, diferentes = [], [], []
    iguais = 0

    CAMPOS_CMP = [
        ('total_mc_ac_incentivos', 'Total MC+AC+Inc.'),
        ('teto_mac', 'Teto MAC'),
        ('aih_mc', 'AIH MC'),
        ('aih_ac', 'AIH AC'),
        ('sia_mc', 'SIA MC'),
        ('sia_ac', 'SIA AC'),
    ]

    for cnes, db_r in db_idx.items():
        if cnes not in xls_idx:
            apenas_db.append({'cnes': cnes, 'unidade': db_r.get('unidade',''), 'id': db_r.get('id')})
        else:
            xls_r = xls_idx[cnes]
            diffs = []
            for campo, label in CAMPOS_CMP:
                v_db  = round(float(db_r.get(campo) or 0), 2)
                v_xls = round(float(xls_r.get(campo) or 0), 2)
                if abs(v_db - v_xls) > 0.01:
                    diffs.append({'campo': label, 'db': v_db, 'xls': v_xls, 'diff': v_xls - v_db})
            if diffs:
                diferentes.append({
                    'cnes': cnes, 'unidade': db_r.get('unidade',''),
                    'id': db_r.get('id'), 'diffs': diffs
                })
            else:
                iguais += 1

    for cnes, xls_r in xls_idx.items():
        if cnes not in db_idx:
            apenas_xls.append({'cnes': cnes, 'unidade': xls_r.get('unidade','')})

    return {
        'apenas_db': apenas_db[:100],
        'apenas_xls': apenas_xls[:100],
        'diferentes': diferentes[:200],
        'iguais': iguais,
        'total_db': len(db_rows),
        'total_xls': len(registros_xls)
    }

# ── Detalhamento Completo ─────────────────────────────────────────────────────

_COLS_DET = [
    'id','drs','tipo','hu','municipio','cnes','cnpj','unidade',
    'aih_fisico','aih_faec','sia_faec','equip_hemodialise','limite_complementacao',
    'aih_mc','aih_ac','aih_total','sia_mc','sia_ac','sia_total',
    'teto_global','teto_mc','teto_ac','teto_mac','total_teto_mac',
    'portaria_ms_gm_8516','integrasus','iac','sus_100','opo',
    'rede_viver_sem_limite','rede_brasil_miseria','rsme','rce_rceg',
    'rau_hosp_sos','rca_rcan','iapi','residencia_medica','melhor_em_casa',
    'cer','doencas_raras','oficina_ortopedica','ihac','total_mc_ac_incentivos'
]

_SORT_ALLOW = {
    'drs','tipo','hu','municipio','cnes','unidade',
    'aih_fisico','aih_faec','sia_faec','equip_hemodialise','limite_complementacao',
    'aih_mc','aih_ac','aih_total','portaria_ms_gm_8516',
    'sia_mc','sia_ac','sia_total','teto_global','teto_mc','teto_ac','teto_mac','total_teto_mac',
    'integrasus','iac','sus_100','opo','rede_viver_sem_limite','rede_brasil_miseria',
    'rsme','rce_rceg','rau_hosp_sos','rca_rcan','iapi','residencia_medica','melhor_em_casa',
    'cer','doencas_raras','oficina_ortopedica','ihac','total_mc_ac_incentivos'
}

def detalhamento_registros(ano, mes, drs=None, tipo=None, busca=None, page=1, per_page=50,
                           sort_col='drs', sort_dir='asc', col_filters=None):
    where = ['ano = ?', 'mes = ?']
    params = [ano, mes]
    if drs:
        where.append('CAST(drs AS INTEGER) = ?')
        params.append(int(drs))
    if tipo:
        where.append('tipo = ?')
        params.append(tipo)
    if busca:
        where.append('(unidade LIKE ? OR cnes LIKE ? OR municipio LIKE ?)')
        params.extend([f'%{busca}%', f'%{busca}%', f'%{busca}%'])
    # Filtros de coluna adicionais (cf_*)
    if col_filters:
        for key, val in col_filters.items():
            if not val:
                continue
            if key.endswith('__gte'):
                col = key[:-5]
                if col in _SORT_ALLOW:
                    try:
                        where.append(f'CAST({col} AS REAL) >= ?')
                        params.append(float(val))
                    except ValueError:
                        pass
            elif key.endswith('__lte'):
                col = key[:-5]
                if col in _SORT_ALLOW:
                    try:
                        where.append(f'CAST({col} AS REAL) <= ?')
                        params.append(float(val))
                    except ValueError:
                        pass
            elif key in _SORT_ALLOW:
                if '|' in val:
                    vals = [v.strip() for v in val.split('|') if v.strip()]
                    placeholders = ','.join(['?' for _ in vals])
                    where.append(f'{key} IN ({placeholders})')
                    params.extend(vals)
                else:
                    where.append(f'LOWER({key}) LIKE ?')
                    params.append(f'%{val.lower()}%')
    ws = ' AND '.join(where)

    sc = sort_col if sort_col in _SORT_ALLOW else 'drs'
    sd = 'DESC' if str(sort_dir).lower() == 'desc' else 'ASC'

    if USE_SUPABASE:
        sb = get_sb()
        q  = sb.table('teto_mac').select('*').eq('ano', ano).eq('mes', mes)
        tc = sb.table('teto_mac').select('id', count='exact').eq('ano', ano).eq('mes', mes)
        if drs:
            q  = q.eq('drs', drs)
            tc = tc.eq('drs', drs)
        if tipo:
            q  = q.eq('tipo', tipo)
            tc = tc.eq('tipo', tipo)
        if busca:
            orq = f'unidade.ilike.%{busca}%,cnes.ilike.%{busca}%,municipio.ilike.%{busca}%'
            q  = q.or_(orq)
            tc = tc.or_(orq)
        if col_filters:
            for key, val in col_filters.items():
                if not val:
                    continue
                if key.endswith('__gte'):
                    col = key[:-5]
                    if col in _SORT_ALLOW:
                        try:
                            q  = q.gte(col, float(val))
                            tc = tc.gte(col, float(val))
                        except Exception:
                            pass
                elif key.endswith('__lte'):
                    col = key[:-5]
                    if col in _SORT_ALLOW:
                        try:
                            q  = q.lte(col, float(val))
                            tc = tc.lte(col, float(val))
                        except Exception:
                            pass
                elif key in _SORT_ALLOW:
                    if '|' in val:
                        vals_list = [v.strip() for v in val.split('|') if v.strip()]
                        q  = q.in_(key, vals_list)
                        tc = tc.in_(key, vals_list)
                    else:
                        q  = q.filter(key, 'ilike', f'%{val}%')
                        tc = tc.filter(key, 'ilike', f'%{val}%')
        total = (tc.execute()).count or 0
        offset = (page - 1) * per_page
        rows = q.order(sc, desc=(sd=='DESC')).range(offset, offset + per_page - 1).execute()
        return rows.data or [], total
    else:
        offset = (page - 1) * per_page
        conn = get_db()
        total = conn.execute(f'SELECT COUNT(*) FROM teto_mac WHERE {ws}', params).fetchone()[0]
        # Colunas numéricas ordenam como número
        order_expr = f'CAST({sc} AS REAL) {sd}' if sc not in {'tipo','hu','municipio','cnes','unidade'} else f'{sc} {sd}'
        rows = conn.execute(
            f"SELECT {','.join(_COLS_DET)} FROM teto_mac WHERE {ws} ORDER BY {order_expr} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows], total

def autocomplete_valores(campo, q, ano=None, mes=None, limit=15):
    """Retorna valores únicos de um campo para autocomplete (busca parcial)."""
    ALLOW = {'municipio', 'unidade', 'cnes'}
    if campo not in ALLOW or not q:
        return []
    if USE_SUPABASE:
        sb = get_sb()
        r = sb.table('teto_mac').select(campo)\
              .filter(campo, 'ilike', f'%{q}%')\
              .limit(limit * 5).execute()
        seen = set(); result = []
        for row in (r.data or []):
            # r.data pode ser list[dict] ou list[Row] dependendo da versão
            v = row.get(campo) if isinstance(row, dict) else getattr(row, campo, None)
            if v is None:
                continue
            vs = str(v).strip()
            if vs and vs not in seen:
                seen.add(vs); result.append(vs)
        return sorted(result)[:limit]
    conn = get_db()
    where = [f'{campo} LIKE ?', f'{campo} IS NOT NULL', f"TRIM({campo}) != ''"]
    params = [f'%{q}%']
    if ano:  where.append('ano = ?');  params.append(ano)
    if mes:  where.append('mes = ?');  params.append(mes)
    rows = conn.execute(
        f"SELECT DISTINCT {campo} FROM teto_mac WHERE {' AND '.join(where)} ORDER BY {campo} LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def detalhamento_valores_unicos(col, ano, mes):
    """Retorna lista de valores únicos de uma coluna para o filtro Excel."""
    if col not in _SORT_ALLOW:
        return []
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select(col).eq('ano', ano).eq('mes', mes).execute()
        vals = sorted(set(
            str(row[col]) for row in (r.data or [])
            if row.get(col) is not None and str(row.get(col, '')).strip() != ''
        ), key=lambda x: (float(x) if x.replace('.','',1).replace('-','',1).isdigit() else x.lower()))
        return vals
    conn = get_db()
    rows = conn.execute(
        f"SELECT DISTINCT CAST({col} AS TEXT) AS v FROM teto_mac "
        f"WHERE ano=? AND mes=? AND {col} IS NOT NULL AND TRIM(CAST({col} AS TEXT))!='' "
        f"ORDER BY {col}",
        (ano, mes)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0] is not None]

def detalhamento_tipos(ano, mes):
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('tipo').eq('ano', ano).eq('mes', mes).execute()
        return sorted(set(row['tipo'] for row in (r.data or []) if row.get('tipo')))
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT tipo FROM teto_mac WHERE ano=? AND mes=? AND tipo IS NOT NULL AND TRIM(tipo)!='' ORDER BY tipo",
        (ano, mes)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

def registrar_acesso(id):
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc).isoformat()
    if USE_SUPABASE:
        get_sb().table('usuarios').update({'ultimo_acesso': agora}).eq('id', id).execute()
    else:
        conn = get_db()
        conn.execute("UPDATE usuarios SET ultimo_acesso=? WHERE id=?", (agora, id))
        conn.commit()
        conn.close()

def verificar_duplicata(ano, mes, cnes):
    if USE_SUPABASE:
        r = (get_sb().table('teto_mac')
            .select('id', count='exact')
            .eq('ano', ano).eq('mes', mes).eq('cnes', str(cnes))
            .execute())
        return (r.count or 0) > 0
    else:
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND cnes=?",
            (ano, mes, str(cnes))
        ).fetchone()[0]
        conn.close()
        return count > 0

# ── SQLite init (fallback) ─────────────────────────────────────────────────────

def _init_sqlite():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teto_mac (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano INTEGER NOT NULL, mes INTEGER NOT NULL,
            drs REAL, tipo TEXT, hu TEXT, municipio TEXT,
            cnes TEXT, cnpj TEXT, unidade TEXT,
            aih_fisico REAL DEFAULT 0, aih_faec REAL DEFAULT 0,
            sia_faec REAL DEFAULT 0, equip_hemodialise REAL DEFAULT 0,
            limite_complementacao REAL DEFAULT 0,
            aih_mc REAL DEFAULT 0, aih_ac REAL DEFAULT 0, aih_total REAL DEFAULT 0,
            sia_mc REAL DEFAULT 0, sia_ac REAL DEFAULT 0, sia_total REAL DEFAULT 0,
            teto_global REAL DEFAULT 0, teto_mc REAL DEFAULT 0, teto_ac REAL DEFAULT 0,
            teto_mac REAL DEFAULT 0, total_teto_mac REAL DEFAULT 0,
            portaria_ms_gm_8516 REAL DEFAULT 0,
            integrasus REAL DEFAULT 0, iac REAL DEFAULT 0, sus_100 REAL DEFAULT 0,
            opo REAL DEFAULT 0, rede_viver_sem_limite REAL DEFAULT 0,
            rede_brasil_miseria REAL DEFAULT 0, rsme REAL DEFAULT 0,
            rce_rceg REAL DEFAULT 0, rau_hosp_sos REAL DEFAULT 0,
            rca_rcan REAL DEFAULT 0, iapi REAL DEFAULT 0,
            residencia_medica REAL DEFAULT 0, melhor_em_casa REAL DEFAULT 0,
            cer REAL DEFAULT 0, doencas_raras REAL DEFAULT 0,
            oficina_ortopedica REAL DEFAULT 0, ihac REAL DEFAULT 0,
            total_mc_ac_incentivos REAL DEFAULT 0,
            arquivo_origem TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo TEXT, ano INTEGER, mes INTEGER,
            total_registros INTEGER DEFAULT 0, registros_importados INTEGER DEFAULT 0,
            registros_erro INTEGER DEFAULT 0, status TEXT DEFAULT 'pendente',
            mensagem TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            perfil TEXT DEFAULT 'usuario',
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acesso TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ano_mes ON teto_mac(ano, mes);
        CREATE INDEX IF NOT EXISTS idx_cnes ON teto_mac(cnes);
        CREATE INDEX IF NOT EXISTS idx_municipio ON teto_mac(municipio);
        CREATE INDEX IF NOT EXISTS idx_drs ON teto_mac(drs);
    """)
    conn.commit()
    conn.close()
