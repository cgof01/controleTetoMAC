"""
database.py — Camada de dados usando Supabase (HTTPS/REST)
Fallback automático para SQLite em desenvolvimento.
"""
import os
import json
import concurrent.futures
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

    from supabase import create_client as _create_client
    import threading
    _sb_thread_local = threading.local()

    def get_sb():
        """Cliente Supabase próprio da thread atual (não um único cliente global
        compartilhado). O servidor de produção roda com múltiplas threads por
        worker (gunicorn --worker-class gthread), e as buscas paginadas em
        paralelo (_fetch_paginas_paralelo) também usam várias threads ao mesmo
        tempo — um cliente HTTP/2 compartilhado entre threads derruba a conexão
        (ConnectionTerminated) sob concorrência."""
        if not hasattr(_sb_thread_local, 'sb'):
            _sb_thread_local.sb = _create_client(SUPABASE_URL, SUPABASE_KEY)
        return _sb_thread_local.sb

    get_sb_paralelo = get_sb  # mesmo cliente por thread, usado nas buscas em paralelo

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
    """Normaliza None para 0 em campos numéricos e desserializa campos_extras."""
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
    # Desserializa campos_extras (SQLite armazena como TEXT)
    ce = result.get('campos_extras')
    if isinstance(ce, str):
        try:
            result['campos_extras'] = json.loads(ce)
        except Exception:
            result['campos_extras'] = {}
    elif ce is None:
        result['campos_extras'] = {}
    # Achata campos_extras no registro principal para acesso uniforme no template
    if result.get('campos_extras'):
        for k, v in result['campos_extras'].items():
            if k not in result:
                result[k] = v
    # Desserializa snapshot_replicacao (foto dos valores no momento da cópia de competência)
    sr = result.get('snapshot_replicacao')
    if isinstance(sr, str):
        try:
            result['snapshot_replicacao'] = json.loads(sr) if sr else None
        except Exception:
            result['snapshot_replicacao'] = None
    return result

# ── CRUD ───────────────────────────────────────────────────────────────────────

def _prep_campos_extras(dados_clean, use_supabase):
    """Serializa campos_extras/snapshot_replicacao para TEXT no SQLite; deixa como dict no Supabase."""
    for campo in ('campos_extras', 'snapshot_replicacao'):
        v = dados_clean.get(campo)
        if v is not None and not use_supabase and isinstance(v, dict):
            dados_clean[campo] = json.dumps(v, ensure_ascii=False)
    return dados_clean

def inserir_registro(dados):
    dados_clean = {k: v for k, v in dados.items() if k not in ('id','created_at','updated_at')}
    dados_clean = _prep_campos_extras(dados_clean, USE_SUPABASE)
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
    dados_clean = _prep_campos_extras(dados_clean, USE_SUPABASE)
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


# Colunas que a tela de Pesquisa deixa ordenar clicando no cabeçalho — cada uma
# vira 1+ colunas físicas de ORDER BY (competência ordena por ano+mes juntos).
_ORDENAR_COLS = {
    'competencia': ['ano', 'mes'],
    'drs': ['drs'], 'tipo': ['tipo'], 'municipio': ['municipio'],
    'cnes': ['cnes'], 'unidade': ['unidade'],
    'aih_fisico': ['aih_fisico'], 'aih_faec': ['aih_faec'],
    'aih_mc': ['aih_mc'], 'aih_ac': ['aih_ac'],
    'sia_faec': ['sia_faec'], 'sia_mc': ['sia_mc'], 'sia_ac': ['sia_ac'],
    'equip_hemodialise': ['equip_hemodialise'], 'limite_complementacao': ['limite_complementacao'],
    'teto_mac': ['teto_mac'],
    'total_mc_ac_incentivos': ['total_mc_ac_incentivos'],
}

def pesquisar(filtros=None, page=1, per_page=50, ordenar_por=None, ordenar_dir='desc'):
    if USE_SUPABASE:
        return _pesquisar_supabase(filtros, page, per_page, ordenar_por, ordenar_dir)
    else:
        return _pesquisar_sqlite(filtros, page, per_page, ordenar_por, ordenar_dir)

def _aplicar_filtros_supabase(q, filtros):
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
    return q

def _where_sqlite(filtros):
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
    return where, params

def _pesquisar_supabase(filtros, page, per_page, ordenar_por=None, ordenar_dir='desc'):
    sb = get_sb()
    q = _aplicar_filtros_supabase(sb.table('teto_mac').select('*', count='exact'), filtros)

    offset = (page - 1) * per_page
    desc = (ordenar_dir or 'desc').lower() != 'asc'
    cols = _ORDENAR_COLS.get(ordenar_por)
    if cols:
        for c in cols:
            q = q.order(c, desc=desc)
    else:
        q = q.order('ano', desc=True).order('mes', desc=True).order('unidade')
    q = q.range(offset, offset + per_page - 1)

    r = q.execute()
    total = r.count if r.count is not None else len(r.data)
    return [_clean(row) for row in r.data], total

def _pesquisar_sqlite(filtros, page, per_page, ordenar_por=None, ordenar_dir='desc'):
    conn = get_db()
    where, params = _where_sqlite(filtros)
    total = conn.execute(f"SELECT COUNT(*) FROM teto_mac {where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    dir_sql = 'ASC' if (ordenar_dir or 'desc').lower() == 'asc' else 'DESC'
    cols = _ORDENAR_COLS.get(ordenar_por)
    order_by = (', '.join(f'{c} {dir_sql}' for c in cols) if cols
                else 'ano DESC, mes DESC, unidade')
    rows = conn.execute(
        f"SELECT * FROM teto_mac {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    conn.close()
    return [_clean(dict(r)) for r in rows], total

def _fetch_paginas_paralelo(fetch_pagina, total, page_size=1000, max_workers=10):
    """Busca em PARALELO (várias requisições HTTP ao mesmo tempo) todas as páginas
    de 0 até `total`, já que o PostgREST/Supabase limita cada requisição a no máximo
    1000 linhas. Buscar essas páginas em sequência (uma de cada vez) é o que deixava
    telas como Pesquisa extremamente lentas com dezenas de milhares de registros —
    em paralelo o tempo total fica perto do tempo de UMA requisição, não da soma
    de todas. `fetch_pagina(offset)` deve devolver a lista de linhas daquele offset."""
    offsets = list(range(0, total, page_size))
    if not offsets:
        return []
    todos = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(offsets))) as ex:
        for rows in ex.map(fetch_pagina, offsets):
            todos.extend(rows)
    return todos

def pesquisar_todos(filtros=None):
    """Busca TODOS os registros que casam com os filtros — evita truncar
    silenciosamente exportações grandes por causa do limite de linhas por requisição
    do Supabase/PostgREST (o mesmo problema que existia em relatorio_periodo)."""
    if USE_SUPABASE:
        sb = get_sb()
        total = (_aplicar_filtros_supabase(sb.table('teto_mac').select('id', count='exact'), filtros)
                  .limit(1).execute()).count or 0

        def _fetch_pagina(offset):
            q = _aplicar_filtros_supabase(get_sb_paralelo().table('teto_mac').select('*'), filtros)
            # order('id') é o desempate final — sem uma ordem estável e única, cada
            # requisição de página pode devolver os empates (ano/mes/unidade iguais)
            # numa ordem física diferente, e a combinação das páginas perde ou
            # duplica linhas (foi exatamente esse bug que apareceu nos testes).
            q = q.order('ano', desc=True).order('mes', desc=True).order('unidade').order('id')
            r = q.range(offset, offset + 999).execute()
            return [_clean(row) for row in (r.data or [])]

        return _fetch_paginas_paralelo(_fetch_pagina, total)
    else:
        conn = get_db()
        where, params = _where_sqlite(filtros)
        rows = conn.execute(
            f"SELECT * FROM teto_mac {where} ORDER BY ano DESC, mes DESC, unidade", params
        ).fetchall()
        conn.close()
        return [_clean(dict(r)) for r in rows]

_CAMPOS_SOMA_PESQUISA = [
    'aih_fisico', 'aih_faec', 'sia_faec', 'aih_mc', 'aih_ac', 'aih_total',
    'sia_mc', 'sia_ac', 'sia_total', 'teto_mac', 'total_teto_mac',
    'total_mc_ac_incentivos',
]

def pesquisar_totais(filtros=None):
    """Soma os campos numéricos principais de TODOS os registros que casam com os
    filtros (não só a página atual) — usado para mostrar o consolidado da Pesquisa."""
    totais = {c: 0.0 for c in _CAMPOS_SOMA_PESQUISA}
    totais['registros'] = 0
    if USE_SUPABASE:
        sb = get_sb()
        cols = ','.join(_CAMPOS_SOMA_PESQUISA)
        total = (_aplicar_filtros_supabase(sb.table('teto_mac').select('id', count='exact'), filtros)
                  .limit(1).execute()).count or 0
        totais['registros'] = total

        def _fetch_pagina(offset):
            q = _aplicar_filtros_supabase(get_sb_paralelo().table('teto_mac').select(cols), filtros)
            # order('id') obrigatório: .range() sem ordem estável faz páginas
            # buscadas em paralelo se sobreporem/deixarem buracos (linhas somem).
            r = q.order('id').range(offset, offset + 999).execute()
            return r.data or []

        for row in _fetch_paginas_paralelo(_fetch_pagina, total):
            for c in _CAMPOS_SOMA_PESQUISA:
                totais[c] += row.get(c) or 0
    else:
        conn = get_db()
        where, params = _where_sqlite(filtros)
        sel = ', '.join(f'SUM(COALESCE({c},0)) as {c}' for c in _CAMPOS_SOMA_PESQUISA)
        row = conn.execute(f"SELECT COUNT(*) as registros, {sel} FROM teto_mac {where}", params).fetchone()
        conn.close()
        if row:
            r = dict(row)
            totais['registros'] = r.get('registros') or 0
            for c in _CAMPOS_SOMA_PESQUISA:
                totais[c] = r.get(c) or 0
    return totais

# ── Replicação de competência (copiar mês inteiro) ─────────────────────────────

_COLS_FIXAS_REPLICAR = {
    'ano', 'mes', 'drs', 'tipo', 'hu', 'municipio', 'cnes', 'cnpj', 'unidade',
    'campos_extras', 'arquivo_origem',
}

# Chaves que nunca entram na "foto" usada para detectar o que foi alterado
# depois de uma replicação de competência (metadados, não campos de negócio).
_META_EXCLUIR_SNAPSHOT = {
    'id', 'created_at', 'updated_at', 'ano', 'mes', 'campos_extras',
    'snapshot_replicacao', 'origem_replicacao_ano', 'origem_replicacao_mes',
    'arquivo_origem',
}

def _fetch_todos_competencia(ano, mes):
    """Busca TODOS os registros de uma competência, paginando para não depender
    de limites de linhas por requisição (ex: max_rows do PostgREST no Supabase)."""
    todos = []
    page = 1
    per_page = 500
    while True:
        regs, total = pesquisar({'ano': ano, 'mes': mes}, page=page, per_page=per_page)
        if not regs:
            break
        todos.extend(regs)
        if len(regs) < per_page or len(todos) >= total:
            break
        page += 1
    return todos

def replicar_competencia(ano_origem, mes_origem, ano_destino, mes_destino):
    """Copia todos os registros de (ano_origem, mes_origem) para (ano_destino, mes_destino).
    Unidades que já tenham registro na competência de destino (mesma chave
    ano+mes+cnes+unidade usada em toda a importação/deduplicação do sistema) são
    puladas e preservadas como estão."""
    origem = _fetch_todos_competencia(ano_origem, mes_origem)
    if not origem:
        return {'copiados': 0, 'ja_existentes': 0, 'total_origem': 0}

    destino = _fetch_todos_competencia(ano_destino, mes_destino)
    existentes = {
        (str(r.get('cnes') or ''), (r.get('unidade') or '').strip().upper())
        for r in destino
    }

    campos_cfg = listar_campos_config(incluir_inativos=True)
    colunas_validas = _COLS_FIXAS_REPLICAR | {c['coluna_db'] for c in campos_cfg if c.get('coluna_db')}

    novos = []
    ja_existentes = 0
    for reg in origem:
        chave = (str(reg.get('cnes') or ''), (reg.get('unidade') or '').strip().upper())
        if chave in existentes:
            ja_existentes += 1
            continue
        novo = {k: v for k, v in reg.items() if k in colunas_validas}
        novo['ano'] = ano_destino
        novo['mes'] = mes_destino
        # Guarda uma foto dos valores de origem para poder destacar em vermelho,
        # na tela do registro, o que for alterado depois da cópia (ver campos_alterados).
        novo['snapshot_replicacao'] = {
            k: v for k, v in reg.items() if k not in _META_EXCLUIR_SNAPSHOT
        }
        novo['origem_replicacao_ano'] = ano_origem
        novo['origem_replicacao_mes'] = mes_origem
        novos.append(novo)

    if not novos:
        return {'copiados': 0, 'ja_existentes': ja_existentes, 'total_origem': len(origem)}

    if USE_SUPABASE:
        sb = get_sb()
        for i in range(0, len(novos), 200):
            lote = [_prep_campos_extras(dict(n), True) for n in novos[i:i + 200]]
            sb.table('teto_mac').insert(lote).execute()
    else:
        conn = get_db()
        for n in novos:
            n = _prep_campos_extras(dict(n), False)
            campos = list(n.keys())
            conn.execute(
                f"INSERT INTO teto_mac ({','.join(campos)}) VALUES ({','.join(['?' for _ in campos])})",
                [n[k] for k in campos]
            )
        conn.commit()
        conn.close()

    return {'copiados': len(novos), 'ja_existentes': ja_existentes, 'total_origem': len(origem)}

def _valor_normalizado(v):
    """Normaliza um valor para comparação tolerante (número vs texto, None vs 0/''.)"""
    if v is None or v == '':
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return str(v).strip().upper()

def campos_alterados(registro):
    """Retorna o conjunto de campos cujo valor atual difere da foto salva no momento
    em que o registro foi copiado por replicar_competencia. Vazio se o registro não
    veio de uma replicação de competência ou se nada foi alterado desde a cópia."""
    snap = (registro or {}).get('snapshot_replicacao')
    if not snap:
        return set()
    return {
        campo for campo, valor_original in snap.items()
        if _valor_normalizado(registro.get(campo)) != _valor_normalizado(valor_original)
    }

# ── Ajustes de campo (trava de valor + adição/subtração com justificativa) ─────
# Ao editar um registro já existente (inclusive um recém-criado por
# replicar_competencia), os campos de valor não são mais sobrescritos direto:
# o usuário lança um ajuste (adição ou subtração de uma quantia, ex.: referente
# a uma Portaria/SIB) com justificativa obrigatória, e o campo pode acumular
# vários ajustes ao longo do tempo. A coluna em teto_mac continua sendo o
# "valor atual" (valor travado original + soma de todos os ajustes já
# lançados) — por isso nenhum relatório/RPC existente precisa mudar para
# enxergar o efeito de um ajuste; eles já leem a coluna normalmente.

CAMPOS_AJUSTAVEIS_SECOES = {'aih', 'sia', 'teto_mac', 'incentivos'}

def campo_ajustavel(campo_cfg):
    """Um campo entra no fluxo de trava+ajuste quando é um valor numérico de
    negócio (moeda/número) numa das seções de valor — não uma identificação
    (Unidade, CNES, Município...) nem um campo 'calculado' automaticamente."""
    return (
        campo_cfg.get('ativo', True)
        and campo_cfg.get('tipo') in ('moeda', 'numero')
        and campo_cfg.get('secao_key') in CAMPOS_AJUSTAVEIS_SECOES
    )

def listar_ajustes(registro_id):
    """Todos os ajustes já lançados num registro, mais recentes primeiro."""
    if USE_SUPABASE:
        r = (get_sb().table('ajustes_campo').select('*')
             .eq('registro_id', int(registro_id))
             .order('created_at', desc=True).execute())
        return r.data or []
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ajustes_campo WHERE registro_id=? ORDER BY created_at DESC",
        (int(registro_id),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def campos_com_ajustes(registro_ids):
    """Para uma lista de ids de registro, devolve {registro_id: {campo_key, ...}}
    com os campos que já receberam pelo menos um ajuste — usado para destacar em
    vermelho, na lista de Pesquisa, os valores que foram alterados via ajuste."""
    ids = [int(i) for i in registro_ids if i is not None]
    if not ids:
        return {}
    if USE_SUPABASE:
        r = (get_sb().table('ajustes_campo').select('registro_id,campo_key')
             .in_('registro_id', ids).execute())
        rows = r.data or []
    else:
        conn = get_db()
        placeholders = ','.join('?' for _ in ids)
        rows = [dict(row) for row in conn.execute(
            f"SELECT registro_id, campo_key FROM ajustes_campo WHERE registro_id IN ({placeholders})",
            ids
        ).fetchall()]
        conn.close()
    resultado = {}
    for row in rows:
        resultado.setdefault(row['registro_id'], set()).add(row['campo_key'])
    return resultado

def _recalcular_calculados(valores, campos_cfg):
    """Reaplica a soma dos campos 'calculado' (mesma lógica de recalcularTodos()
    em form.html, só que em Python) a partir de `valores` — dict com os valores
    atuais de negócio já refletindo o ajuste que acabou de ser aplicado.
    Devolve {coluna_db: novo_total} só dos campos calculado."""
    recalculados = {}
    for c in campos_cfg:
        if c.get('tipo') != 'calculado' or not c.get('formula'):
            continue
        formula_keys = [k.strip() for k in c['formula'].split(',') if k.strip()]
        total = sum(float(valores.get(k) or 0) for k in formula_keys)
        destino = c.get('coluna_db') or c['campo_key']
        recalculados[destino] = total
    return recalculados

def registrar_ajuste(registro_id, campo_key, tipo, valor, justificativa, usuario_nome):
    """Lança um ajuste (adição/subtração) sobre um campo travado: soma/subtrai
    `valor` do valor atual, recalcula os campos 'calculado', persiste tudo num
    único UPDATE em teto_mac e grava a linha no ledger ajustes_campo.
    Levanta ValueError se o campo não for ajustável ou os dados forem inválidos."""
    campos_cfg = listar_campos_config(incluir_inativos=True)
    meta = next((c for c in campos_cfg if c['campo_key'] == campo_key), None)
    if not meta or not campo_ajustavel(meta):
        raise ValueError(f'Campo "{campo_key}" não pode receber ajustes.')
    if tipo not in ('adicao', 'subtracao'):
        raise ValueError('Tipo de ajuste inválido.')
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError('Valor do ajuste inválido.')
    if valor <= 0:
        raise ValueError('Valor do ajuste deve ser maior que zero.')
    justificativa = (justificativa or '').strip()
    if not justificativa:
        raise ValueError('Justificativa é obrigatória.')

    registro = buscar_registro(registro_id)
    if not registro:
        raise ValueError('Registro não encontrado.')

    coluna_db = meta.get('coluna_db')
    delta = valor if tipo == 'adicao' else -valor
    atual = float(registro.get(campo_key) or 0)
    novo_valor = atual + delta

    dados_update = {}
    valores_para_formula = dict(registro)
    valores_para_formula[campo_key] = novo_valor
    if coluna_db:
        dados_update[coluna_db] = novo_valor
        valores_para_formula[coluna_db] = novo_valor
    else:
        extras = dict(registro.get('campos_extras') or {})
        extras[campo_key] = novo_valor
        dados_update['campos_extras'] = extras

    dados_update.update(_recalcular_calculados(valores_para_formula, campos_cfg))
    atualizar_registro(registro_id, dados_update)

    ajuste = {
        'registro_id': int(registro_id), 'campo_key': campo_key, 'tipo': tipo,
        'valor': valor, 'justificativa': justificativa,
        'usuario_nome': usuario_nome or 'Sistema',
    }
    if USE_SUPABASE:
        r = get_sb().table('ajustes_campo').insert(ajuste).execute()
        ajuste = r.data[0] if r.data else ajuste
    else:
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO ajustes_campo (registro_id, campo_key, tipo, valor, justificativa, usuario_nome) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ajuste['registro_id'], ajuste['campo_key'], ajuste['tipo'], ajuste['valor'],
             ajuste['justificativa'], ajuste['usuario_nome'])
        )
        conn.commit()
        ajuste['id'] = cur.lastrowid
        conn.close()

    return {'novo_valor': novo_valor, 'ajuste': ajuste}

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

_EXCLUIR_UNIDADES = ('TOTAL', 'SUBTOTAL', 'TOTAL GERAL', 'GERAL')

def _filtrar_totais(dados):
    return [
        d for d in dados
        if not any(
            ex == (d.get('unidade') or '').upper().strip()
            for ex in _EXCLUIR_UNIDADES
        )
    ]

# As funções analíticas abaixo aceitam `ano_fim`/`mes_fim` opcionais para relatórios
# por período/ano (não só um único mês). Quando omitidos, o período é o próprio
# mês (`ano`,`mes`) — comportamento idêntico ao de antes. Todas usam _fetch_periodo,
# que já pagina para não truncar períodos grandes.

def grafico_por_drs(ano, mes, ano_fim=None, mes_fim=None):
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
                           campos=['drs', 'total_mc_ac_incentivos'])
    seen = {}
    for row in rows:
        drs = int(row.get('drs') or 0)
        if drs not in seen:
            seen[drs] = {'drs': drs, 'total': 0.0, 'unidades': 0}
        seen[drs]['total']    += row.get('total_mc_ac_incentivos') or 0
        seen[drs]['unidades'] += 1
    return sorted(seen.values(), key=lambda x: x['total'], reverse=True)

def grafico_top_unidades(ano, mes, limite=15, ano_fim=None, mes_fim=None):
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
                           campos=['unidade', 'municipio', 'total_mc_ac_incentivos'])
    acc = {}
    for row in rows:
        un = row.get('unidade') or ''
        if un not in acc:
            acc[un] = {'unidade': un, 'municipio': row.get('municipio'), 'total': 0.0}
        acc[un]['total'] += row.get('total_mc_ac_incentivos') or 0
    dados = _filtrar_totais(list(acc.values()))
    dados = [d for d in dados if d['total'] > 0]
    dados.sort(key=lambda x: x['total'], reverse=True)
    return dados[:limite]

def grafico_por_tipo(ano, mes, ano_fim=None, mes_fim=None):
    def _agrupar(t):
        t = (t or '').strip().upper()
        if 'PRÓPRIO' in t or 'PROPRIO' in t: return 'Rede Própria'
        if 'PRIVADO' in t: return 'Privados'
        return t.title() if t else 'Outros'

    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
                           campos=['tipo', 'total_mc_ac_incentivos'])
    acc = {}
    for row in rows:
        tipo = _agrupar(row.get('tipo'))
        if tipo not in acc:
            acc[tipo] = {'tipo': tipo, 'total': 0.0, 'unidades': 0}
        acc[tipo]['total']    += row.get('total_mc_ac_incentivos') or 0
        acc[tipo]['unidades'] += 1
    return sorted(acc.values(), key=lambda x: x['total'], reverse=True)

def relatorio_por_unidade(ano, mes, ano_fim=None, mes_fim=None):
    """Ranking de unidades por total no período."""
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes, campos=[
        'unidade', 'cnes', 'municipio', 'drs', 'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac',
        'total_mc_ac_incentivos',
    ])
    seen = {}
    for row in rows:
        un = (row.get('unidade') or '').strip().upper()
        if un in _EXCLUIR_UNIDADES:
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

def relatorio_por_municipio(ano, mes, ano_fim=None, mes_fim=None):
    """Totais agrupados por município."""
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
        campos=['municipio', 'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac', 'total_mc_ac_incentivos'])
    seen = {}
    for row in rows:
        mun = (row.get('municipio') or 'Não Informado').strip()
        if mun not in seen:
            seen[mun] = {'municipio': mun, 'unidades': 0,
                         'total_aih': 0.0, 'total_sia': 0.0, 'total_geral': 0.0}
        seen[mun]['unidades'] += 1
        seen[mun]['total_aih'] += (row.get('aih_mc') or 0) + (row.get('aih_ac') or 0)
        seen[mun]['total_sia'] += (row.get('sia_mc') or 0) + (row.get('sia_ac') or 0)
        seen[mun]['total_geral'] += row.get('total_mc_ac_incentivos') or 0
    return sorted(seen.values(), key=lambda x: x['total_geral'], reverse=True)

# Lista canônica de todos os incentivos — reaproveitada por todo relatório/KPI que
# soma ou lista incentivos individualmente. Antes cada lugar (relatorio_resumo_drs,
# kpis_central, relatorio_incentivos, RPCs do Supabase) tinha sua própria lista
# copiada à mão, e cada cópia esquecia campos diferentes (nenhuma somava os 5
# INCENTIVOS_EXTRAS, que ficam dentro de campos_extras — ver import_xls.py
# _CAMPOS_EXTRAS_IMPORT — em vez de coluna própria em teto_mac).
INCENTIVOS_NATIVOS = [
    ('integrasus', 'IntegraSUS'), ('iac', 'IAC'), ('sus_100', '100% SUS'),
    ('opo', 'OPO'), ('rede_viver_sem_limite', 'Rede Viver Sem Limite'),
    ('rede_brasil_miseria', 'Rede Brasil Sem Miséria'), ('rsme', 'RSME'),
    ('rce_rceg', 'RCE/RCEG'), ('rau_hosp_sos', 'RAU/Hosp. SOS'),
    ('rca_rcan', 'RCA/RCAN'), ('iapi', 'IAPI'), ('residencia_medica', 'Residência Médica'),
    ('melhor_em_casa', 'Melhor em Casa'), ('cer', 'CER'),
    ('doencas_raras', 'Doenças Raras'), ('oficina_ortopedica', 'Oficina Ortopédica'),
    ('ihac', 'IHAC'),
]
INCENTIVOS_EXTRAS = [
    ('rede_alyne', 'Rede Alyne'), ('pncp', 'Política Nacional de Cuidados Paliativos - PNCP'),
    ('rce_rceg_custeio', 'RCE/RCEG - Custeio UTI'),
    ('rau_hosp_sos_custeio', 'RAU/Hosp. SOS - Custeio UTI'),
    ('rca_rcan_custeio', 'RCA/RCAN - Custeio'),
]
INCENTIVOS_TODOS = INCENTIVOS_NATIVOS + INCENTIVOS_EXTRAS

# Os 17 incentivos nativos (colunas reais) também entram na allowlist de
# ordenação da Pesquisa (_ORDENAR_COLS, definida mais acima) — os 5 que vivem
# em campos_extras (rede_alyne, pncp, custeio...) não têm coluna própria pra
# usar num ORDER BY, então ficam de fora e a coluna aparece sem link de
# ordenação na tela (mesmo padrão de "sortable só quando é coluna real").
_ORDENAR_COLS.update({k: [k] for k, _ in INCENTIVOS_NATIVOS})

def _extras_dict(row):
    """Desserializa campos_extras de uma linha crua (TEXT no SQLite, dict/JSONB no Supabase)."""
    extras = row.get('campos_extras')
    if isinstance(extras, str):
        try:
            return json.loads(extras) if extras else {}
        except Exception:
            return {}
    return extras or {}

def relatorio_fundo(ano, mes, ano_fim=None, mes_fim=None):
    """Componentes FAEC + MAC agrupados por DRS."""
    campos_soma = ['aih_fisico', 'aih_faec', 'sia_faec', 'equip_hemodialise',
                   'limite_complementacao', 'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac']
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
                           campos=['drs'] + campos_soma + ['total_mc_ac_incentivos'])
    seen = {}
    for row in rows:
        drs = int(row.get('drs') or 0)
        if drs not in seen:
            seen[drs] = {k: 0.0 for k in campos_soma + ['total']}
            seen[drs]['drs'] = drs
        for k in campos_soma:
            seen[drs][k] += row.get(k) or 0
        seen[drs]['total'] += row.get('total_mc_ac_incentivos') or 0
    return sorted(seen.values(), key=lambda x: x['drs'])

def relatorio_incentivos(ano, mes, ano_fim=None, mes_fim=None):
    """Totais de cada incentivo individual (nativos + os guardados em campos_extras)."""
    rows = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes,
                           campos=[k for k, _ in INCENTIVOS_NATIVOS] + ['campos_extras'])
    totais = {k: 0.0 for k, _ in INCENTIVOS_TODOS}
    for row in rows:
        extras = _extras_dict(row)
        for k, _ in INCENTIVOS_NATIVOS:
            totais[k] += row.get(k) or 0
        for k, _ in INCENTIVOS_EXTRAS:
            totais[k] += extras.get(k) or 0
    return [{'campo': k, 'label': lbl, 'total': totais[k]} for k, lbl in INCENTIVOS_TODOS]


# ── Central de Relatórios Analíticos ─────────────────────────────────────────

_DIMS_ALLOW = {'drs', 'tipo', 'hu', 'municipio', 'cnes', 'cnpj', 'unidade', 'ano', 'mes'}
# Campos que ainda não têm coluna dedicada em teto_mac (ficam dentro de
# campos_extras — ver import_xls.py _CAMPOS_EXTRAS_IMPORT). A consulta precisa
# buscar a coluna campos_extras inteira e resolver o valor por dentro do JSON.
_METS_EXTRAS = {'rede_alyne', 'pncp', 'rce_rceg_custeio', 'rau_hosp_sos_custeio', 'rca_rcan_custeio'}
_METS_NATIVAS = {
    'aih_fisico', 'aih_faec', 'sia_faec', 'equip_hemodialise', 'limite_complementacao',
    'aih_mc', 'aih_ac', 'aih_total', 'sia_mc', 'sia_ac', 'sia_total',
    'teto_global', 'teto_mc', 'teto_ac', 'teto_mac', 'total_teto_mac',
    'portaria_ms_gm_8516', 'integrasus', 'iac', 'sus_100', 'opo',
    'rede_viver_sem_limite', 'rede_brasil_miseria', 'rsme', 'rce_rceg',
    'rau_hosp_sos', 'rca_rcan', 'iapi', 'residencia_medica', 'melhor_em_casa',
    'cer', 'doencas_raras', 'oficina_ortopedica', 'ihac', 'total_mc_ac_incentivos'
}
_METS_ALLOW = _METS_NATIVAS | _METS_EXTRAS

def _valor_metrica(row, m):
    """Lê o valor de uma métrica de uma linha, indo buscar dentro de
    campos_extras quando a métrica não é uma coluna nativa."""
    if m in _METS_EXTRAS:
        return (row.get('campos_extras') or {}).get(m) or 0
    return row.get(m) or 0
_INC = ('integrasus+iac+sus_100+opo+rede_viver_sem_limite+rede_brasil_miseria+rsme+rce_rceg+'
        'rau_hosp_sos+rca_rcan+iapi+residencia_medica+melhor_em_casa+cer+doencas_raras+'
        'oficina_ortopedica+ihac')
_FAEC = 'aih_faec+sia_faec+equip_hemodialise+limite_complementacao'


def kpis_central(ano, mes, ano_fim=None, mes_fim=None):
    """KPIs completos para a Central de Relatórios. Usa _fetch_periodo (paginado e,
    no Supabase, em paralelo) em vez de um .limit() fixo — que na prática o
    PostgREST capa em 1000 linhas por requisição e truncava silenciosamente
    qualquer competência/período com mais unidades que isso."""
    campos = [
        'drs', 'municipio', 'cnes', 'aih_fisico', 'aih_faec', 'sia_faec', 'equip_hemodialise',
        'limite_complementacao', 'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac', 'teto_mac', 'total_teto_mac',
        'total_mc_ac_incentivos', 'campos_extras',
    ] + [k for k, _ in INCENTIVOS_NATIVOS]
    data = _fetch_periodo(ano, mes, ano_fim or ano, mes_fim or mes, campos=campos)
    drs_s, mun_s, cnes_s = set(), set(), set()
    faec = aih = sia = inc = teto = geral = 0.0
    for row in data:
        if row.get('drs'):       drs_s.add(str(row['drs']))
        if row.get('municipio'): mun_s.add(str(row['municipio']).strip())
        if row.get('cnes'):      cnes_s.add(str(row['cnes']))
        extras = _extras_dict(row)
        faec  += sum(row.get(k) or 0 for k in ['aih_faec', 'sia_faec', 'equip_hemodialise', 'limite_complementacao'])
        aih   += (row.get('aih_mc') or 0) + (row.get('aih_ac') or 0)
        sia   += (row.get('sia_mc') or 0) + (row.get('sia_ac') or 0)
        inc   += sum(row.get(k) or 0 for k, _ in INCENTIVOS_NATIVOS)
        inc   += sum(extras.get(k) or 0 for k, _ in INCENTIVOS_EXTRAS)
        teto  += (row.get('teto_mac') or 0) + (row.get('total_teto_mac') or 0)
        geral += row.get('total_mc_ac_incentivos') or 0
    return {'total_teto_mac': teto, 'total_faec': faec, 'total_aih': aih,
            'total_sia': sia, 'total_incentivos': inc, 'total_geral': geral,
            'count_drs': len(drs_s), 'count_municipios': len(mun_s),
            'count_unidades': len(data), 'count_cnes': len(cnes_s)}


def _aplicar_filtros_analitico(q, filtros):
    for k, v in (filtros or {}).items():
        if k not in _DIMS_ALLOW or not v:
            continue
        if isinstance(v, list) and v:
            q = q.in_(k, v)
        elif isinstance(v, str) and v:
            try:
                fv = float(v); num_v = int(fv) if fv == int(fv) else fv
                q = q.eq(k, num_v)
            except (ValueError, TypeError):
                q = q.filter(k, 'ilike', f'%{v}%')
    return q

def consulta_analitica(ano, mes, dimensoes=None, metricas=None, filtros=None, ordenar_por=None,
                        limite=500, ano_fim=None, mes_fim=None):
    """Consulta genérica para o construtor de relatórios (Central de Relatórios
    Analíticos), com suporte a período (ano_fim/mes_fim opcionais — default é o
    próprio mês, igual antes). Busca paginada (e no Supabase em paralelo) em vez
    de um .limit() fixo, que o PostgREST capa em 1000 linhas e truncava
    silenciosamente qualquer consulta com mais registros que isso."""
    dimensoes = [d for d in (dimensoes or []) if d in _DIMS_ALLOW]
    metricas  = [m for m in (metricas  or ['total_mc_ac_incentivos']) if m in _METS_ALLOW]
    if not metricas:
        metricas = ['total_mc_ac_incentivos']
    filtros = filtros or {}
    ano_fim = ano_fim or ano
    mes_fim = mes_fim or mes
    ini = ano * 100 + mes
    fim = ano_fim * 100 + mes_fim

    tem_extras = any(m in _METS_EXTRAS for m in metricas)

    if USE_SUPABASE:
        sb = get_sb()
        col_set = list(dict.fromkeys(
            ['ano', 'mes'] + dimensoes + [m for m in metricas if m not in _METS_EXTRAS]
            + (['campos_extras'] if tem_extras else [])
        ))
        cols = ','.join(col_set)

        total = (_aplicar_filtros_analitico(
            sb.table('teto_mac').select('id', count='exact').gte('ano', ano).lte('ano', ano_fim), filtros
        ).limit(1).execute()).count or 0

        def _fetch_pagina(offset):
            q = _aplicar_filtros_analitico(
                get_sb_paralelo().table('teto_mac').select(cols).gte('ano', ano).lte('ano', ano_fim), filtros
            )
            # order('id') obrigatório: .range() sem ordem estável faz páginas
            # buscadas em paralelo se sobreporem/deixarem buracos (linhas somem).
            r = q.order('id').range(offset, offset + 999).execute()
            return r.data or []

        brutos = _fetch_paginas_paralelo(_fetch_pagina, total)
        data = [row for row in brutos if ini <= (row['ano'] * 100 + row['mes']) <= fim]
        seen = {}
        for row in data:
            key = tuple(str(row.get(d) or '') for d in dimensoes) if dimensoes else ('_total_',)
            if key not in seen:
                seen[key] = {d: row.get(d) for d in dimensoes}
                for m in metricas:
                    seen[key][m] = 0.0
                seen[key]['_count'] = 0
            for m in metricas:
                seen[key][m] += _valor_metrica(row, m)
            seen[key]['_count'] += 1
        result = list(seen.values())
    elif tem_extras:
        # campos_extras é TEXT (JSON) no SQLite — soma em Python igual ao Supabase.
        conn = get_db()
        where  = ['(ano * 100 + mes) BETWEEN ? AND ?']
        params = [ini, fim]
        for k, v in filtros.items():
            if k not in _DIMS_ALLOW or not v:
                continue
            if isinstance(v, list) and v:
                placeholders = ','.join('?' for _ in v)
                where.append(f'{k} IN ({placeholders})')
                params.extend(v)
            elif isinstance(v, str) and v:
                try:
                    fv = float(v); num_v = int(fv) if fv == int(fv) else fv
                    where.append(f'CAST({k} AS REAL) = ?')
                    params.append(num_v)
                except (ValueError, TypeError):
                    where.append(f'LOWER({k}) LIKE ?')
                    params.append(f'%{v.lower()}%')
        col_set = list(dict.fromkeys(dimensoes + [m for m in metricas if m not in _METS_EXTRAS] + ['campos_extras']))
        sql = f"SELECT {', '.join(col_set)} FROM teto_mac WHERE {' AND '.join(where)}"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        seen = {}
        for r in rows:
            row = dict(r)
            ce = row.get('campos_extras')
            row['campos_extras'] = json.loads(ce) if isinstance(ce, str) and ce else {}
            key = tuple(str(row.get(d) or '') for d in dimensoes) if dimensoes else ('_total_',)
            if key not in seen:
                seen[key] = {d: row.get(d) for d in dimensoes}
                for m in metricas:
                    seen[key][m] = 0.0
                seen[key]['_count'] = 0
            for m in metricas:
                seen[key][m] += _valor_metrica(row, m)
            seen[key]['_count'] += 1
        result = list(seen.values())
    else:
        conn = get_db()
        where  = ['(ano * 100 + mes) BETWEEN ? AND ?']
        params = [ini, fim]
        for k, v in filtros.items():
            if k not in _DIMS_ALLOW or not v:
                continue
            if isinstance(v, list) and v:
                placeholders = ','.join('?' for _ in v)
                where.append(f'{k} IN ({placeholders})')
                params.extend(v)
            elif isinstance(v, str) and v:
                try:
                    fv = float(v); num_v = int(fv) if fv == int(fv) else fv
                    where.append(f'CAST({k} AS REAL) = ?')
                    params.append(num_v)
                except (ValueError, TypeError):
                    where.append(f'LOWER({k}) LIKE ?')
                    params.append(f'%{v.lower()}%')
        sel_mets = ', '.join(f'SUM(COALESCE({m},0)) as {m}' for m in metricas) + ', COUNT(*) as _count'
        if dimensoes:
            g = ', '.join(dimensoes)
            sql = f"SELECT {g}, {sel_mets} FROM teto_mac WHERE {' AND '.join(where)} GROUP BY {g}"
        else:
            sql = f"SELECT {sel_mets} FROM teto_mac WHERE {' AND '.join(where)}"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        result = [dict(r) for r in rows]

    sort_key = ordenar_por if ordenar_por in metricas else (metricas[0] if metricas else None)
    if sort_key:
        result.sort(key=lambda x: x.get(sort_key) or 0, reverse=True)
    return result[:limite]


def relatorio_resumo_drs(ano, mes):
    """Resumo por DRS, com cada incentivo (nativo + campos_extras) em chave própria,
    além de total_incentivos/total_geral. Agregação em Python (não SQL GROUP BY) no
    SQLite para poder somar os campos guardados em campos_extras (JSON), mesmo padrão
    já usado em kpis_central/relatorio_incentivos."""
    if USE_SUPABASE:
        r = get_sb().rpc('get_resumo_drs', {'p_ano': ano, 'p_mes': mes}).execute()
        return r.data if isinstance(r.data, list) else []
    else:
        campos = (['drs', 'aih_fisico', 'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac',
                    'teto_mac', 'total_teto_mac', 'total_mc_ac_incentivos', 'campos_extras']
                   + [k for k, _ in INCENTIVOS_NATIVOS])
        conn = get_db()
        cols = ','.join(campos)
        rows = conn.execute(
            f"SELECT {cols} FROM teto_mac WHERE ano = ? AND mes = ? AND drs IS NOT NULL",
            (ano, mes)
        ).fetchall()
        conn.close()
        seen = {}
        for raw in rows:
            row = dict(raw)
            drs = int(row.get('drs') or 0)
            if drs not in seen:
                g = {k: 0.0 for k, _ in INCENTIVOS_TODOS}
                g.update({'drs': drs, 'total_unidades': 0, 'aih_fisico': 0.0,
                          'total_aih': 0.0, 'total_sia': 0.0, 'teto_mac': 0.0,
                          'total_incentivos': 0.0, 'total_geral': 0.0})
                seen[drs] = g
            g = seen[drs]
            extras = _extras_dict(row)
            g['total_unidades'] += 1
            g['aih_fisico'] += row.get('aih_fisico') or 0
            g['total_aih'] += (row.get('aih_mc') or 0) + (row.get('aih_ac') or 0)
            g['total_sia'] += (row.get('sia_mc') or 0) + (row.get('sia_ac') or 0)
            g['teto_mac'] += (row.get('teto_mac') or 0) + (row.get('total_teto_mac') or 0)
            g['total_geral'] += row.get('total_mc_ac_incentivos') or 0
            for k, _ in INCENTIVOS_NATIVOS:
                v = row.get(k) or 0
                g[k] += v
                g['total_incentivos'] += v
            for k, _ in INCENTIVOS_EXTRAS:
                v = extras.get(k) or 0
                g[k] += v
                g['total_incentivos'] += v
        return sorted(seen.values(), key=lambda x: x['drs'])

_CAMPOS_PERIODO_PADRAO = [
    'ano', 'mes', 'drs', 'tipo', 'municipio', 'cnes', 'cnpj', 'unidade',
    'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac', 'teto_mac', 'total_teto_mac', 'total_mc_ac_incentivos',
    'campos_extras',
] + [k for k, _ in INCENTIVOS_NATIVOS]

def _fetch_periodo(ano_ini, mes_ini, ano_fim, mes_fim, campos=None):
    """Busca registros de teto_mac num intervalo de competências (ano,mes), inclusive,
    paginando para não depender do limite de linhas por requisição do Supabase/PostgREST
    (o `.limit()` fixo usado antes aqui truncava silenciosamente períodos longos)."""
    campos = campos or _CAMPOS_PERIODO_PADRAO
    ini = ano_ini * 100 + mes_ini
    fim = ano_fim * 100 + mes_fim
    # 'ano'/'mes' são obrigatórios para o filtro de mes_ini/mes_fim abaixo (Supabase)
    # e para ordenação/uso pelos chamadores — garante que estejam sempre selecionados,
    # mesmo quando o chamador passa uma lista de campos mais enxuta.
    campos = list(dict.fromkeys(['ano', 'mes'] + list(campos)))
    if USE_SUPABASE:
        sb = get_sb()
        cols = ','.join(campos)
        total = (sb.table('teto_mac').select('id', count='exact')
                 .gte('ano', ano_ini).lte('ano', ano_fim).limit(1).execute()).count or 0

        def _fetch_pagina(offset):
            # order('id') obrigatório: .range() sem ordem estável faz páginas
            # buscadas em paralelo se sobreporem/deixarem buracos (linhas somem —
            # foi assim que um mês inteiro sumiu num teste desta função).
            r = (get_sb_paralelo().table('teto_mac').select(cols)
                .gte('ano', ano_ini).lte('ano', ano_fim)
                .order('id')
                .range(offset, offset + 999)
                .execute())
            return r.data or []

        todos = _fetch_paginas_paralelo(_fetch_pagina, total)
        return [row for row in todos if ini <= (row['ano'] * 100 + row['mes']) <= fim]
    else:
        conn = get_db()
        cols = ','.join(campos)
        rows = conn.execute(f"""
            SELECT {cols} FROM teto_mac
            WHERE (ano * 100 + mes) BETWEEN ? AND ?
            ORDER BY ano, mes, unidade
        """, (ini, fim)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

def relatorio_periodo(ano_ini, mes_ini, ano_fim, mes_fim, granularidade='detalhado'):
    """Registros de teto_mac num período. granularidade:
    'detalhado' (uma linha por unidade/competência, comportamento original),
    'mensal' (soma dos valores por competência) ou 'anual' (soma dos valores por ano)."""
    dados = _fetch_periodo(ano_ini, mes_ini, ano_fim, mes_fim)
    # Achata campos_extras (rede_alyne, pncp, custeio...) direto na linha, para o
    # template acessar r.pncp igual aos campos nativos, em vez de r.campos_extras.pncp.
    for row in dados:
        extras = _extras_dict(row)
        for k, _ in INCENTIVOS_EXTRAS:
            row[k] = extras.get(k) or 0
    if granularidade == 'detalhado':
        return sorted(dados, key=lambda r: (r['ano'], r['mes'], r.get('unidade') or ''))

    campos_soma = (['aih_mc', 'aih_ac', 'sia_mc', 'sia_ac', 'teto_mac', 'total_teto_mac',
                    'total_mc_ac_incentivos'] + [k for k, _ in INCENTIVOS_TODOS])
    grupos = {}
    for row in dados:
        chave = (row['ano'], row['mes']) if granularidade == 'mensal' else (row['ano'],)
        if chave not in grupos:
            grupos[chave] = {c: 0.0 for c in campos_soma}
            grupos[chave]['unidades'] = 0
            grupos[chave]['ano'] = row['ano']
            if granularidade == 'mensal':
                grupos[chave]['mes'] = row['mes']
        grupos[chave]['unidades'] += 1
        for c in campos_soma:
            grupos[chave][c] += row.get(c) or 0
    chave_ordenacao = (lambda x: (x['ano'], x['mes'])) if granularidade == 'mensal' else (lambda x: x['ano'])
    return sorted(grupos.values(), key=chave_ordenacao)

def periodo_completo(ano_ini, mes_ini, ano_fim, mes_fim, campos=None):
    """Wrapper público de _fetch_periodo, para uso fora deste módulo (ex.: exportação
    de Excel por período, que precisa de todas as colunas — não só as usadas pelos
    relatórios analíticos)."""
    return _fetch_periodo(ano_ini, mes_ini, ano_fim, mes_fim, campos=campos)

def comparativo_unidade(cnes, ano_ini=2022, ano_fim=2026):
    """Histórico de uma unidade por CNES, com cada incentivo (nativo + campos_extras)
    em chave própria — antes só trazia integrasus/iac/sus_100."""
    if USE_SUPABASE:
        r = (get_sb().rpc('get_historico_unidade', {'p_cnes': str(cnes)}).execute())
        return r.data if isinstance(r.data, list) else []
    else:
        campos = (['ano', 'mes', 'unidade', 'municipio', 'drs', 'total_mc_ac_incentivos',
                    'aih_mc', 'aih_ac', 'sia_mc', 'sia_ac', 'teto_mac', 'total_teto_mac',
                    'campos_extras']
                   + [k for k, _ in INCENTIVOS_NATIVOS])
        conn = get_db()
        cols = ','.join(campos)
        rows = conn.execute(f"""
            SELECT {cols} FROM teto_mac WHERE cnes = ? AND ano BETWEEN ? AND ?
            ORDER BY ano, mes
        """, (str(cnes), ano_ini, ano_fim)).fetchall()
        conn.close()
        resultado = []
        for raw in rows:
            row = dict(raw)
            extras = _extras_dict(row)
            row['total'] = row.pop('total_mc_ac_incentivos') or 0
            row['teto'] = (row.pop('teto_mac') or 0) + (row.pop('total_teto_mac') or 0)
            for k, _ in INCENTIVOS_EXTRAS:
                row[k] = extras.get(k) or 0
            row.pop('campos_extras', None)
            resultado.append(row)
        return resultado

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

def _analisar_qualidade(registros):
    """Recebe os registros (id,cnes,unidade,municipio,drs,total_mc_ac_incentivos) de
    uma competência e calcula os contadores + as listas detalhadas de problemas,
    usadas tanto pelos cards quanto pelas tabelas da tela de Auditoria."""
    total = len(registros)
    sem_cnes = sem_valor = sem_drs = 0
    problemas = []
    por_cnes = {}
    for r in registros:
        cnes = (r.get('cnes') or '').strip()
        motivos = []
        if not cnes:
            motivos.append('Sem CNES')
            sem_cnes += 1
        if not r.get('total_mc_ac_incentivos') or r['total_mc_ac_incentivos'] <= 0:
            motivos.append('Valor zero/nulo')
            sem_valor += 1
        if not r.get('drs'):
            motivos.append('Sem DRS')
            sem_drs += 1
        if motivos:
            problemas.append({**r, 'problema': ' + '.join(motivos)})
        if cnes:
            por_cnes.setdefault(cnes, []).append(r.get('unidade') or '')

    dup_lista = [
        {'cnes': cnes, 'c': len(unidades), 'unidades': ' | '.join(unidades)}
        for cnes, unidades in por_cnes.items() if len(unidades) > 1
    ]
    dup_lista.sort(key=lambda d: d['c'], reverse=True)
    duplicatas = sum(d['c'] - 1 for d in dup_lista)

    return {
        'total': total, 'sem_cnes': sem_cnes, 'sem_valor': sem_valor,
        'sem_drs': sem_drs, 'duplicatas': duplicatas,
        'problemas': problemas[:200],
        'duplicatas_lista': dup_lista[:50],
    }

def auditoria_validacao(ano, mes):
    """Relatório de qualidade de dados para um período: contadores + a lista
    detalhada de qual registro tem qual problema, para o usuário poder corrigir."""
    sel = ['id', 'cnes', 'unidade', 'municipio', 'drs', 'total_mc_ac_incentivos']
    if USE_SUPABASE:
        sb = get_sb()
        cols = ','.join(sel)
        registros = []
        offset = 0
        page_size = 1000
        while True:
            r = (sb.table('teto_mac').select(cols)
                .eq('ano', ano).eq('mes', mes)
                .order('id')
                .range(offset, offset + page_size - 1).execute())
            rows = r.data or []
            if not rows:
                break
            registros.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
    else:
        conn = get_db()
        rows = conn.execute(f"""
            SELECT id, cnes, unidade, municipio, CAST(drs AS INTEGER) as drs, total_mc_ac_incentivos
            FROM teto_mac WHERE ano=? AND mes=?
        """, (ano, mes)).fetchall()
        conn.close()
        registros = [dict(r) for r in rows]
    return _analisar_qualidade(registros)

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
        # No Postgres, ajustes_campo tem ON DELETE CASCADE de verdade — não
        # precisa limpar à mão.
        get_sb().table('teto_mac').delete().in_('id', ids).execute()
        return len(ids)
    else:
        conn = get_db()
        ph = ','.join(['?' for _ in ids])
        # SQLite só respeita ON DELETE CASCADE com PRAGMA foreign_keys=ON, que
        # esta conexão não liga — apaga os ajustes órfãos manualmente antes.
        conn.execute(f'DELETE FROM ajustes_campo WHERE registro_id IN ({ph})', ids)
        cur = conn.execute(f'DELETE FROM teto_mac WHERE id IN ({ph})', ids)
        conn.commit()
        conn.close()
        return cur.rowcount

def auditoria_deletar_periodo(ano, mes):
    """Deleta todos os registros de uma competência (ano+mês)."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('id', count='exact').eq('ano', ano).eq('mes', mes).limit(1).execute()
        n = r.count or 0
        get_sb().table('teto_mac').delete().eq('ano', ano).eq('mes', mes).execute()
        return n
    else:
        conn = get_db()
        conn.execute(
            'DELETE FROM ajustes_campo WHERE registro_id IN '
            '(SELECT id FROM teto_mac WHERE ano=? AND mes=?)', (ano, mes)
        )
        cur = conn.execute('DELETE FROM teto_mac WHERE ano=? AND mes=?', (ano, mes))
        conn.commit()
        conn.close()
        return cur.rowcount

def auditoria_deletar_ano(ano):
    """Deleta todos os registros de um ano inteiro (todas as competências)."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('id', count='exact').eq('ano', ano).limit(1).execute()
        n = r.count or 0
        get_sb().table('teto_mac').delete().eq('ano', ano).execute()
        return n
    else:
        conn = get_db()
        conn.execute(
            'DELETE FROM ajustes_campo WHERE registro_id IN '
            '(SELECT id FROM teto_mac WHERE ano=?)', (ano,)
        )
        cur = conn.execute('DELETE FROM teto_mac WHERE ano=?', (ano,))
        conn.commit()
        conn.close()
        return cur.rowcount

def auditoria_deletar_tudo():
    """Deleta TODOS os registros de teto_mac (e os ajustes de campo
    correspondentes) — não mexe em usuarios/config/portarias/logs_sistema."""
    if USE_SUPABASE:
        r = get_sb().table('teto_mac').select('id', count='exact').limit(1).execute()
        n = r.count or 0
        get_sb().table('teto_mac').delete().gte('id', 0).execute()
        return n
    else:
        conn = get_db()
        n = conn.execute('SELECT COUNT(*) FROM teto_mac').fetchone()[0]
        conn.execute('DELETE FROM ajustes_campo')
        conn.execute('DELETE FROM teto_mac')
        conn.commit()
        conn.close()
        return n

def registrar_log(usuario_nome, acao, detalhes, registros_afetados=0):
    """Grava uma entrada no log de auditoria do sistema (ações administrativas
    sensíveis, como exclusões em massa)."""
    dados = {'usuario_nome': usuario_nome, 'acao': acao, 'detalhes': detalhes,
             'registros_afetados': registros_afetados}
    if USE_SUPABASE:
        try:
            get_sb().table('logs_sistema').insert(dados).execute()
        except Exception:
            pass
    else:
        conn = get_db()
        conn.execute(
            "INSERT INTO logs_sistema (usuario_nome, acao, detalhes, registros_afetados) VALUES (?,?,?,?)",
            (usuario_nome, acao, detalhes, registros_afetados)
        )
        conn.commit()
        conn.close()

def listar_logs(limit=50):
    if USE_SUPABASE:
        try:
            r = get_sb().table('logs_sistema').select('*').order('created_at', desc=True).limit(limit).execute()
            return r.data or []
        except Exception:
            return []
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM logs_sistema ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
            campos_extras TEXT DEFAULT '{}',
            snapshot_replicacao TEXT,
            origem_replicacao_ano INTEGER,
            origem_replicacao_mes INTEGER,
            arquivo_origem TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ano, mes, cnes, unidade)
        );
        CREATE TABLE IF NOT EXISTS importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo TEXT, ano INTEGER, mes INTEGER,
            total_registros INTEGER DEFAULT 0, registros_importados INTEGER DEFAULT 0,
            registros_atualizados INTEGER DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS secao_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secao_key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            cor TEXT NOT NULL DEFAULT 'primary',
            icone TEXT NOT NULL DEFAULT 'list',
            ordem INT NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS campo_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            secao_key TEXT NOT NULL,
            campo_key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'moeda',
            ordem INT NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            obrigatorio INTEGER NOT NULL DEFAULT 0,
            formula TEXT DEFAULT NULL,
            coluna_db TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sistema_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            valor TEXT,
            descricao TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ajustes_campo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registro_id INTEGER NOT NULL REFERENCES teto_mac(id) ON DELETE CASCADE,
            campo_key TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('adicao','subtracao')),
            valor REAL NOT NULL,
            justificativa TEXT NOT NULL,
            usuario_nome TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_nome TEXT,
            acao TEXT NOT NULL,
            detalhes TEXT,
            registros_afetados INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ano_mes ON teto_mac(ano, mes);
        CREATE INDEX IF NOT EXISTS idx_cnes ON teto_mac(cnes);
        CREATE INDEX IF NOT EXISTS idx_municipio ON teto_mac(municipio);
        CREATE INDEX IF NOT EXISTS idx_drs ON teto_mac(drs);
        CREATE INDEX IF NOT EXISTS idx_campo_secao ON campo_config(secao_key, ordem);
        CREATE INDEX IF NOT EXISTS idx_ajustes_registro_campo ON ajustes_campo(registro_id, campo_key);
    """)
    conn.commit()
    # Adiciona colunas em tabelas existentes (migration segura, uma tentativa por coluna)
    for alter_sql in (
        "ALTER TABLE teto_mac ADD COLUMN campos_extras TEXT DEFAULT '{}'",
        "ALTER TABLE teto_mac ADD COLUMN snapshot_replicacao TEXT",
        "ALTER TABLE teto_mac ADD COLUMN origem_replicacao_ano INTEGER",
        "ALTER TABLE teto_mac ADD COLUMN origem_replicacao_mes INTEGER",
    ):
        try:
            conn.execute(alter_sql)
            conn.commit()
        except Exception:
            pass
    conn.close()
    _seed_campos_config_sqlite()
    _seed_sistema_config_sqlite()

# ── Portarias ─────────────────────────────────────────────────────────────────
# Metadados: Supabase (tabela portarias) ou SQLite local (portarias.db)
# Arquivos:  Supabase Storage (bucket 'portarias') ou disco local (uploads/portarias/)

_PORTARIAS_DB     = os.path.join(os.path.dirname(__file__), 'portarias.db')
_PORTARIAS_LOCAL  = os.path.join(os.path.dirname(__file__), 'uploads', 'portarias')
_PORTARIAS_BUCKET = 'portarias'
_portarias_ok     = False

# ── SQLite local (fallback quando USE_SUPABASE=False) ─────────────────────────

def _portarias_conn():
    global _portarias_ok
    import sqlite3 as _sl
    if not _portarias_ok:
        _init_portarias_db(_sl)
    conn = _sl.connect(_PORTARIAS_DB)
    conn.row_factory = _sl.Row
    return conn

def _init_portarias_db(sl):
    global _portarias_ok
    os.makedirs(_PORTARIAS_LOCAL, exist_ok=True)
    conn = sl.connect(_PORTARIAS_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS portarias (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            cnes                TEXT NOT NULL,
            nome_original       TEXT NOT NULL,
            storage_path        TEXT NOT NULL,
            descricao           TEXT DEFAULT '',
            tamanho_kb          INTEGER DEFAULT 0,
            tamanho_original_kb INTEGER DEFAULT 0,
            validado            INTEGER DEFAULT 0,
            validado_em         TEXT,
            validado_por        TEXT,
            created_at          TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_port_cnes ON portarias(cnes);
    """)
    conn.commit()
    conn.close()
    _portarias_ok = True

# ── Storage helpers (Supabase ou local) ───────────────────────────────────────

def upload_portaria_storage(storage_path, file_bytes):
    if USE_SUPABASE:
        get_sb().storage.from_(_PORTARIAS_BUCKET).upload(
            storage_path, file_bytes,
            {'content-type': 'application/pdf', 'upsert': 'true'}
        )
    else:
        caminho = os.path.join(_PORTARIAS_LOCAL, storage_path)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, 'wb') as f:
            f.write(file_bytes)

def download_portaria_storage(storage_path):
    if USE_SUPABASE:
        return bytes(get_sb().storage.from_(_PORTARIAS_BUCKET).download(storage_path))
    caminho = os.path.join(_PORTARIAS_LOCAL, storage_path)
    with open(caminho, 'rb') as f:
        return f.read()

def _deletar_storage(storage_path):
    if USE_SUPABASE:
        try:
            get_sb().storage.from_(_PORTARIAS_BUCKET).remove([storage_path])
        except Exception:
            pass
    else:
        caminho = os.path.join(_PORTARIAS_LOCAL, storage_path)
        if os.path.exists(caminho):
            try:
                os.unlink(caminho)
            except Exception:
                pass

# ── CRUD de metadados ─────────────────────────────────────────────────────────

def listar_portarias(cnes):
    if USE_SUPABASE:
        try:
            r = (get_sb().table('portarias').select('*')
                 .eq('cnes', str(cnes))
                 .order('created_at', desc=True)
                 .execute())
            return r.data or []
        except Exception:
            return []
    try:
        conn = _portarias_conn()
        rows = conn.execute(
            "SELECT * FROM portarias WHERE cnes=? ORDER BY created_at DESC", (str(cnes),)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def salvar_portaria(cnes, nome_original, storage_path, tamanho_kb, tamanho_original_kb, descricao=''):
    dados = {
        'cnes': str(cnes), 'nome_original': nome_original,
        'storage_path': storage_path, 'descricao': descricao or '',
        'tamanho_kb': tamanho_kb, 'tamanho_original_kb': tamanho_original_kb,
    }
    if USE_SUPABASE:
        r = get_sb().table('portarias').insert(dados).execute()
        return r.data[0]['id'] if r.data else None
    conn = _portarias_conn()
    cur = conn.execute("""
        INSERT INTO portarias
            (cnes, nome_original, storage_path, tamanho_kb, tamanho_original_kb, descricao)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (dados['cnes'], dados['nome_original'], dados['storage_path'],
          dados['tamanho_kb'], dados['tamanho_original_kb'], dados['descricao']))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

def buscar_portaria(pid):
    if USE_SUPABASE:
        try:
            r = get_sb().table('portarias').select('*').eq('id', int(pid)).execute()
            return r.data[0] if r.data else None
        except Exception:
            return None
    try:
        conn = _portarias_conn()
        row  = conn.execute("SELECT * FROM portarias WHERE id=?", (int(pid),)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None

def validar_portaria(pid, usuario_nome):
    from datetime import datetime
    agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    if USE_SUPABASE:
        get_sb().table('portarias').update({
            'validado': True, 'validado_em': agora, 'validado_por': usuario_nome
        }).eq('id', int(pid)).execute()
        return
    conn = _portarias_conn()
    conn.execute(
        "UPDATE portarias SET validado=1, validado_em=?, validado_por=? WHERE id=?",
        (agora, usuario_nome, int(pid))
    )
    conn.commit()
    conn.close()

def desvalidar_portaria(pid):
    if USE_SUPABASE:
        get_sb().table('portarias').update({
            'validado': False, 'validado_em': None, 'validado_por': None
        }).eq('id', int(pid)).execute()
        return
    conn = _portarias_conn()
    conn.execute(
        "UPDATE portarias SET validado=0, validado_em=NULL, validado_por=NULL WHERE id=?",
        (int(pid),)
    )
    conn.commit()
    conn.close()

def deletar_portaria_db(pid):
    p = buscar_portaria(pid)
    if p:
        _deletar_storage(p['storage_path'])
        if USE_SUPABASE:
            get_sb().table('portarias').delete().eq('id', int(pid)).execute()
        else:
            conn = _portarias_conn()
            conn.execute("DELETE FROM portarias WHERE id=?", (int(pid),))
            conn.commit()
            conn.close()
    return p


# ── Configuração de Campos (campo_config) ──────────────────────────────────────

_SEED_SECOES = [
    ('aih',        'AIH — Autorização de Internação Hospitalar', 'success',   'cash-stack',     1),
    ('sia',        'SIA — Sistema de Informações Ambulatoriais', 'info',      'clipboard-data', 2),
    ('teto_mac',   'Teto MAC',                                   'secondary', 'bank',           3),
    ('incentivos', 'Incentivos',                                  'warning',   'award',          4),
]

_SEED_CAMPOS = [
    # (secao_key, campo_key, label, tipo, ordem, coluna_db, formula)
    ('aih', 'aih_fisico', 'AIH Físico',                 'numero',    10, 'aih_fisico', None),
    ('aih', 'aih_faec',   'AIH FAEC',                   'moeda',     20, 'aih_faec',   None),
    ('aih', 'aih_mc',     'AIH MC (Média Complexidade)', 'moeda',     30, 'aih_mc',     None),
    ('aih', 'aih_ac',     'AIH AC (Alta Complexidade)',  'moeda',     40, 'aih_ac',     None),
    ('aih', 'aih_total',  'AIH Total',                  'calculado', 50, 'aih_total',  'aih_faec,aih_mc,aih_ac'),

    ('sia', 'sia_faec',              'SIA FAEC',                         'moeda', 10, 'sia_faec',              None),
    ('sia', 'sia_mc',                'SIA MC (Média Complexidade)',       'moeda', 20, 'sia_mc',                None),
    ('sia', 'sia_ac',                'SIA AC (Alta Complexidade)',        'moeda', 30, 'sia_ac',                None),
    ('sia', 'sia_total',             'SIA Total',                        'calculado', 40, 'sia_total',        'sia_faec,sia_mc,sia_ac'),
    ('sia', 'equip_hemodialise',     'Equip. Hemodiálise (DRC)',          'moeda', 50, 'equip_hemodialise',     None),
    ('sia', 'limite_complementacao', 'Limite Complementação Tabela SUS',  'moeda', 60, 'limite_complementacao', None),

    ('teto_mac', 'teto_global',         'Teto Global',         'moeda', 10, 'teto_global',         None),
    ('teto_mac', 'teto_mc',             'Teto MC',             'moeda', 20, 'teto_mc',             None),
    ('teto_mac', 'teto_ac',             'Teto AC',             'moeda', 30, 'teto_ac',             None),
    ('teto_mac', 'teto_mac_campo',      'Teto MAC',            'moeda', 40, 'teto_mac',            None),
    ('teto_mac', 'total_teto_mac',      'Total Teto MAC',      'moeda', 50, 'total_teto_mac',      None),
    ('teto_mac', 'portaria_ms_gm_8516', 'Portaria MS/GM 8.516','moeda', 60, 'portaria_ms_gm_8516', None),

    ('incentivos', 'integrasus',           'IntegraSUS',             'moeda', 10,  'integrasus',           None),
    ('incentivos', 'iac',                  'IAC',                    'moeda', 20,  'iac',                  None),
    ('incentivos', 'sus_100',              '100% SUS',               'moeda', 30,  'sus_100',              None),
    ('incentivos', 'opo',                  'OPO',                    'moeda', 40,  'opo',                  None),
    ('incentivos', 'rede_viver_sem_limite','Rede Viver Sem Limite',  'moeda', 50,  'rede_viver_sem_limite', None),
    ('incentivos', 'rede_brasil_miseria',  'Rede Brasil Sem Miséria','moeda', 60,  'rede_brasil_miseria',  None),
    ('incentivos', 'rsme',                 'RSME',                   'moeda', 70,  'rsme',                 None),
    ('incentivos', 'rce_rceg',             'RCE/RCEG',               'moeda', 80,  'rce_rceg',             None),
    ('incentivos', 'rau_hosp_sos',         'RAU/HOSP SOS',           'moeda', 90,  'rau_hosp_sos',         None),
    ('incentivos', 'rca_rcan',             'RCA/RCAN',               'moeda', 100, 'rca_rcan',             None),
    ('incentivos', 'iapi',                 'IAPI',                   'moeda', 110, 'iapi',                 None),
    ('incentivos', 'residencia_medica',    'Residência Médica',      'moeda', 120, 'residencia_medica',    None),
    ('incentivos', 'melhor_em_casa',       'Melhor em Casa',         'moeda', 130, 'melhor_em_casa',       None),
    ('incentivos', 'cer',                  'CER',                    'moeda', 140, 'cer',                  None),
    ('incentivos', 'doencas_raras',        'Doenças Raras',          'moeda', 150, 'doencas_raras',        None),
    ('incentivos', 'oficina_ortopedica',   'Oficina Ortopédica',     'moeda', 160, 'oficina_ortopedica',   None),
    ('incentivos', 'ihac',                 'IHAC',                   'moeda', 170, 'ihac',                 None),
    # Sem coluna dedicada em teto_mac — ficam em campos_extras (JSON), mesmo
    # mecanismo dos campos personalizados. Já eram reconhecidos na importação
    # (import_xls._CAMPOS_EXTRAS_IMPORT) mas não apareciam no formulário/Admin
    # por não terem sido registrados aqui.
    ('incentivos', 'rede_alyne',           'Rede Alyne',                                 'moeda', 180, None, None),
    ('incentivos', 'pncp',                 'Política Nacional de Cuidados Paliativos - PNCP', 'moeda', 190, None, None),
    ('incentivos', 'rce_rceg_custeio',     'RCE/RCEG - Custeio UTI',                    'moeda', 200, None, None),
    ('incentivos', 'rau_hosp_sos_custeio', 'RAU/Hosp. SOS - Custeio UTI',                'moeda', 210, None, None),
    ('incentivos', 'rca_rcan_custeio',     'RCA/RCAN - Custeio',                        'moeda', 220, None, None),
    ('incentivos', 'total_mc_ac_incentivos','TOTAL MC + AC + INCENTIVOS','calculado', 999, 'total_mc_ac_incentivos',
     'aih_mc,aih_ac,sia_mc,sia_ac,integrasus,iac,sus_100,opo,rede_viver_sem_limite,rede_brasil_miseria,'
     'rsme,rce_rceg,rau_hosp_sos,rca_rcan,iapi,residencia_medica,melhor_em_casa,cer,doencas_raras,oficina_ortopedica,ihac'),
]


def _seed_campos_config_sqlite():
    """Seed inicial das tabelas secao_config e campo_config no SQLite."""
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM secao_config").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO secao_config (secao_key, label, cor, icone, ordem) VALUES (?,?,?,?,?)",
                _SEED_SECOES
            )
        count2 = conn.execute("SELECT COUNT(*) FROM campo_config").fetchone()[0]
        if count2 == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO campo_config "
                "(secao_key, campo_key, label, tipo, ordem, coluna_db, formula) VALUES (?,?,?,?,?,?,?)",
                _SEED_CAMPOS
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _seed_campos_config_supabase():
    """Seed inicial no Supabase (chamado apenas se as tabelas estiverem vazias)."""
    try:
        sb = get_sb()
        if not sb.table('secao_config').select('id').limit(1).execute().data:
            for s in _SEED_SECOES:
                sb.table('secao_config').upsert({
                    'secao_key': s[0], 'label': s[1], 'cor': s[2], 'icone': s[3], 'ordem': s[4]
                }, on_conflict='secao_key').execute()
        if not sb.table('campo_config').select('id').limit(1).execute().data:
            for c in _SEED_CAMPOS:
                sb.table('campo_config').upsert({
                    'secao_key': c[0], 'campo_key': c[1], 'label': c[2],
                    'tipo': c[3], 'ordem': c[4], 'coluna_db': c[5], 'formula': c[6]
                }, on_conflict='campo_key').execute()
    except Exception:
        pass


def listar_secoes_config():
    """Retorna todas as seções ativas, ordenadas."""
    if USE_SUPABASE:
        try:
            r = get_sb().table('secao_config').select('*').eq('ativo', True).order('ordem').execute()
            if not r.data:
                _seed_campos_config_supabase()
                r = get_sb().table('secao_config').select('*').eq('ativo', True).order('ordem').execute()
            return r.data or []
        except Exception:
            return [{'secao_key': s[0], 'label': s[1], 'cor': s[2], 'icone': s[3], 'ordem': s[4], 'ativo': True}
                    for s in _SEED_SECOES]
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM secao_config WHERE ativo=1 ORDER BY ordem"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_campos_config(secao_key=None, incluir_inativos=False):
    """Retorna campos configurados, opcionalmente filtrados por seção."""
    if USE_SUPABASE:
        try:
            q = get_sb().table('campo_config').select('*')
            if secao_key:
                q = q.eq('secao_key', secao_key)
            if not incluir_inativos:
                q = q.eq('ativo', True)
            q = q.order('secao_key').order('ordem')
            r = q.execute()
            if not r.data and not secao_key:
                _seed_campos_config_supabase()
                r = q.execute()
            return r.data or []
        except Exception:
            dados = _SEED_CAMPOS
            if secao_key:
                dados = [c for c in dados if c[0] == secao_key]
            return [{'secao_key': c[0], 'campo_key': c[1], 'label': c[2],
                     'tipo': c[3], 'ordem': c[4], 'coluna_db': c[5], 'formula': c[6],
                     'ativo': True, 'obrigatorio': False, 'id': 0}
                    for c in dados]
    conn = get_db()
    where_parts = []
    params = []
    if secao_key:
        where_parts.append("secao_key = ?")
        params.append(secao_key)
    if not incluir_inativos:
        where_parts.append("ativo = 1")
    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    rows = conn.execute(
        f"SELECT * FROM campo_config {where} ORDER BY secao_key, ordem", params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def salvar_campo_config(dados):
    """Cria ou atualiza um campo. Retorna o id."""
    dados_clean = {k: v for k, v in dados.items() if k not in ('id', 'created_at', 'updated_at')}
    id_ = dados.get('id')
    if USE_SUPABASE:
        if id_:
            get_sb().table('campo_config').update(dados_clean).eq('id', int(id_)).execute()
            return int(id_)
        r = get_sb().table('campo_config').insert(dados_clean).execute()
        return r.data[0]['id'] if r.data else None
    conn = get_db()
    if id_:
        campos = list(dados_clean.keys())
        set_clause = ', '.join([f'{k} = ?' for k in campos])
        conn.execute(
            f"UPDATE campo_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [dados_clean[k] for k in campos] + [int(id_)]
        )
        conn.commit()
        conn.close()
        return int(id_)
    campos = list(dados_clean.keys())
    cur = conn.execute(
        f"INSERT INTO campo_config ({','.join(campos)}) VALUES ({','.join(['?' for _ in campos])})",
        [dados_clean[k] for k in campos]
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def deletar_campo_config(id_):
    """Remove permanentemente um campo personalizado (coluna_db IS NULL).
    Campos nativos são apenas desativados."""
    if USE_SUPABASE:
        campo = get_sb().table('campo_config').select('coluna_db').eq('id', int(id_)).execute()
        if campo.data and campo.data[0].get('coluna_db') is None:
            get_sb().table('campo_config').delete().eq('id', int(id_)).execute()
        else:
            get_sb().table('campo_config').update({'ativo': False}).eq('id', int(id_)).execute()
        return
    conn = get_db()
    row = conn.execute("SELECT coluna_db FROM campo_config WHERE id = ?", (int(id_),)).fetchone()
    if row and row[0] is None:
        conn.execute("DELETE FROM campo_config WHERE id = ?", (int(id_),))
    else:
        conn.execute("UPDATE campo_config SET ativo = 0 WHERE id = ?", (int(id_),))
    conn.commit()
    conn.close()


def reordenar_campos(items):
    """items = list of {id, ordem}"""
    if USE_SUPABASE:
        sb = get_sb()
        for item in items:
            sb.table('campo_config').update({'ordem': item['ordem']}).eq('id', item['id']).execute()
        return
    conn = get_db()
    for item in items:
        conn.execute("UPDATE campo_config SET ordem = ? WHERE id = ?", (item['ordem'], item['id']))
    conn.commit()
    conn.close()


def salvar_secao_config(dados):
    """Cria ou atualiza uma seção."""
    dados_clean = {k: v for k, v in dados.items() if k not in ('id', 'created_at', 'updated_at')}
    id_ = dados.get('id')
    if USE_SUPABASE:
        if id_:
            get_sb().table('secao_config').update(dados_clean).eq('id', int(id_)).execute()
            return int(id_)
        r = get_sb().table('secao_config').insert(dados_clean).execute()
        return r.data[0]['id'] if r.data else None
    conn = get_db()
    if id_:
        campos = list(dados_clean.keys())
        set_clause = ', '.join([f'{k} = ?' for k in campos])
        conn.execute(
            f"UPDATE secao_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [dados_clean[k] for k in campos] + [int(id_)]
        )
        conn.commit()
        conn.close()
        return int(id_)
    campos = list(dados_clean.keys())
    cur = conn.execute(
        f"INSERT INTO secao_config ({','.join(campos)}) VALUES ({','.join(['?' for _ in campos])})",
        [dados_clean[k] for k in campos]
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


# ── Configurações do Sistema (sistema_config) ───────────────────────────────────

_SEED_SISTEMA_CONFIG = [
    # (chave, valor, descricao)
    ('competencia_offset_meses', '-1',
     'Deslocamento em meses (relativo à competência mais recente já lançada '
     'no sistema, não à data real do calendário) usado para pré-selecionar a '
     'competência (ano/mês) ao inserir um novo registro. '
     '-1 = mês anterior, 0 = mês atual, 1 = mês seguinte.'),
]


def _seed_sistema_config_sqlite():
    """Seed inicial da tabela sistema_config no SQLite."""
    conn = get_db()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO sistema_config (chave, valor, descricao) VALUES (?,?,?)",
            _SEED_SISTEMA_CONFIG
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def obter_config(chave, default=None):
    """Retorna o valor (string) de uma configuração do sistema, ou `default` se não existir."""
    if USE_SUPABASE:
        try:
            r = get_sb().table('sistema_config').select('valor').eq('chave', chave).execute()
            if r.data:
                return r.data[0]['valor']
        except Exception:
            pass
        return default
    try:
        conn = get_db()
        row = conn.execute("SELECT valor FROM sistema_config WHERE chave=?", (chave,)).fetchone()
        conn.close()
        return row['valor'] if row else default
    except Exception:
        return default


def salvar_config(chave, valor):
    """Cria ou atualiza uma configuração do sistema (chave/valor)."""
    if USE_SUPABASE:
        get_sb().table('sistema_config').upsert(
            {'chave': chave, 'valor': str(valor)}, on_conflict='chave'
        ).execute()
        return
    conn = get_db()
    conn.execute("""
        INSERT INTO sistema_config (chave, valor) VALUES (?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, updated_at = CURRENT_TIMESTAMP
    """, (chave, str(valor)))
    conn.commit()
    conn.close()
