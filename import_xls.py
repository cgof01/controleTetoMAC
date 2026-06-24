import xlrd
import openpyxl
import os
import re
from config import USE_SUPABASE
from database import MESES_PT

get_db = None
get_sb = None

if USE_SUPABASE:
    try:
        from database import get_sb
    except ImportError:
        pass
else:
    try:
        from database import get_db
    except ImportError:
        pass

MESES_NOME = {
    'JANEIRO': 1, 'FEVEREIRO': 2, 'MARCO': 3, 'MARÇO': 3, 'ABRIL': 4,
    'MAIO': 5, 'JUNHO': 6, 'JULHO': 7, 'AGOSTO': 8,
    'SETEMBRO': 9, 'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12
}

def extrair_ano_mes_do_nome(filename):
    nome = os.path.basename(filename).upper()
    ano = None
    mes = None

    for mes_nome, mes_num in MESES_NOME.items():
        if mes_nome in nome:
            mes = mes_num
            break

    match = re.search(r'(\d{4})', nome)
    if match:
        ano = int(match.group(1))

    return ano, mes

def normalizar_header(h):
    if not h:
        return ''
    h = str(h).upper().strip()
    h = re.sub(r'\s+', ' ', h)
    h = h.replace('\n', ' ')
    return h

def mapear_colunas(headers):
    mapa = {}
    for i, h in enumerate(headers):
        hn = normalizar_header(h)
        if 'DRS' == hn:
            mapa['drs'] = i
        elif hn == 'TIPO':
            mapa['tipo'] = i
        elif hn == 'HU':
            mapa['hu'] = i
        elif 'MUNIC' in hn and 'PIO' in hn:
            mapa['municipio'] = i
        elif hn == 'CNES':
            mapa['cnes'] = i
        elif hn == 'CNPJ':
            mapa['cnpj'] = i
        elif 'UNIDADE' in hn:
            mapa['unidade'] = i
        elif 'AIH F' in hn and 'SICO' in hn:
            mapa['aih_fisico'] = i
        elif 'AIH FAEC' in hn:
            mapa['aih_faec'] = i
        elif 'SIA FAEC' in hn:
            mapa['sia_faec'] = i
        elif 'HEMODI' in hn or 'DRC' in hn:
            mapa['equip_hemodialise'] = i
        elif 'LIMITE COMPLEMENTA' in hn:
            mapa['limite_complementacao'] = i
        elif 'AIH MC' == hn:
            mapa['aih_mc'] = i
        elif 'AIH AC' == hn:
            mapa['aih_ac'] = i
        elif 'AIH TOTAL' == hn:
            mapa['aih_total'] = i
        elif 'SIA MC' == hn:
            mapa['sia_mc'] = i
        elif 'SIA AC' in hn and 'SIA AC' == hn[:6]:
            mapa['sia_ac'] = i
        elif 'SIA TOTAL' == hn:
            mapa['sia_total'] = i
        elif 'TETO GLOBAL' == hn:
            mapa['teto_global'] = i
        elif 'TETO MC' == hn:
            mapa['teto_mc'] = i
        elif 'TETO AC' == hn:
            mapa['teto_ac'] = i
        elif 'TETO MAC' == hn:
            mapa['teto_mac'] = i
        elif 'TOTAL TETO MAC' == hn:
            mapa['total_teto_mac'] = i
        elif 'PORTARIA' in hn and '8.516' in hn:
            mapa['portaria_ms_gm_8516'] = i
        elif 'INTEGRASUS' in hn:
            mapa['integrasus'] = i
        elif hn == 'IAC':
            mapa['iac'] = i
        elif '100% SUS' in hn or '100%SUS' in hn:
            mapa['sus_100'] = i
        elif hn == 'OPO':
            mapa['opo'] = i
        elif 'VIVER SEM LIMITE' in hn:
            mapa['rede_viver_sem_limite'] = i
        elif 'BRASIL SEM MISERIA' in hn or 'BSOR' in hn:
            mapa['rede_brasil_miseria'] = i
        elif hn == 'RSME':
            mapa['rsme'] = i
        elif 'RCE' in hn or 'RCEG' in hn:
            if 'rce_rceg' not in mapa:
                mapa['rce_rceg'] = i
        elif 'RAU' in hn or 'HOSP SOS' in hn:
            if 'rau_hosp_sos' not in mapa:
                mapa['rau_hosp_sos'] = i
        elif 'RCA' in hn or 'RCAN' in hn:
            if 'rca_rcan' not in mapa:
                mapa['rca_rcan'] = i
        elif 'IAPI' in hn:
            mapa['iapi'] = i
        elif 'RESID' in hn and 'DICA' in hn:
            mapa['residencia_medica'] = i
        elif 'MELHOR EM CASA' in hn:
            mapa['melhor_em_casa'] = i
        elif hn == 'CER':
            mapa['cer'] = i
        elif 'DOEN' in hn and 'RARAS' in hn:
            mapa['doencas_raras'] = i
        elif 'OFICINA' in hn and 'ORTOP' in hn:
            mapa['oficina_ortopedica'] = i
        elif 'IHAC' in hn or 'AMIGO DA CRIAN' in hn:
            mapa['ihac'] = i
        elif 'TOTAL MC' in hn and 'INCENTIVO' in hn:
            mapa['total_mc_ac_incentivos'] = i

    return mapa

def val_num(v):
    if v is None or v == '':
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def val_str(v):
    if v is None:
        return ''
    s = str(v).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s

def importar_arquivo_xls(filepath, ano=None, mes=None, substituir=False, nome_original=None):
    resultado = {
        'arquivo': nome_original or os.path.basename(filepath),
        'ano': ano, 'mes': mes,
        'total': 0, 'importados': 0, 'erros': 0,
        'pulados': 0, 'mensagens': []
    }

    if ano is None or mes is None:
        nome_para_detect = nome_original or filepath
        ano_det, mes_det = extrair_ano_mes_do_nome(nome_para_detect)
        if ano is None:
            ano = ano_det
        if mes is None:
            mes = mes_det

    resultado['ano'] = ano
    resultado['mes'] = mes

    if not ano or not mes:
        resultado['mensagens'].append('Não foi possível determinar ano/mês do arquivo')
        resultado['erros'] = 1
        return resultado

    try:
        wb = xlrd.open_workbook(filepath)
        ws = wb.sheet_by_index(0)
    except Exception as e:
        try:
            wb2 = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            return _importar_openpyxl(wb2, filepath, ano, mes, substituir, resultado)
        except Exception as e2:
            resultado['mensagens'].append(f'Erro ao abrir arquivo: {e2}')
            resultado['erros'] = 1
            return resultado

    # Encontrar linha do header (procurar linha com 'DRS')
    header_row = None
    for r in range(min(5, ws.nrows)):
        row_vals = [str(ws.cell_value(r, c)).strip().upper() for c in range(ws.ncols)]
        if 'DRS' in row_vals:
            header_row = r
            break

    if header_row is None:
        resultado['mensagens'].append('Header não encontrado')
        resultado['erros'] = 1
        return resultado

    headers = [ws.cell_value(header_row, c) for c in range(ws.ncols)]
    mapa = mapear_colunas(headers)

    if 'drs' not in mapa or 'unidade' not in mapa:
        resultado['mensagens'].append(f'Colunas essenciais não encontradas. Mapeadas: {list(mapa.keys())}')
        resultado['erros'] = 1
        return resultado

    lote_supabase = []

    conn = get_db() if not USE_SUPABASE else None
    try:
        for r in range(header_row + 1, ws.nrows):
            row_vals = [ws.cell_value(r, c) for c in range(ws.ncols)]

            drs_val     = row_vals[mapa['drs']] if 'drs' in mapa else ''
            unidade_val = row_vals[mapa['unidade']] if 'unidade' in mapa else ''
            if str(drs_val).strip() == '' and str(unidade_val).strip() == '':
                continue

            cnes_raw = val_str(row_vals[mapa['cnes']]) if 'cnes' in mapa else ''
            if cnes_raw and cnes_raw != 'RESREC':
                try:
                    cnes_raw = str(int(float(cnes_raw)))
                except:
                    pass

            resultado['total'] += 1

            def get_col(campo, rv=row_vals):
                return rv[mapa[campo]] if campo in mapa and mapa[campo] < len(rv) else 0

            registro = {
                'ano': ano, 'mes': mes,
                'drs': val_num(get_col('drs')),
                'tipo': val_str(get_col('tipo')),
                'hu': val_str(get_col('hu')),
                'municipio': val_str(get_col('municipio')).upper(),
                'cnes': cnes_raw,
                'cnpj': val_str(row_vals[mapa['cnpj']]) if 'cnpj' in mapa else '',
                'unidade': val_str(get_col('unidade')).upper(),
                'aih_fisico': val_num(get_col('aih_fisico')),
                'aih_faec': val_num(get_col('aih_faec')),
                'sia_faec': val_num(get_col('sia_faec')),
                'equip_hemodialise': val_num(get_col('equip_hemodialise')),
                'limite_complementacao': val_num(get_col('limite_complementacao')),
                'aih_mc': val_num(get_col('aih_mc')),
                'aih_ac': val_num(get_col('aih_ac')),
                'aih_total': val_num(get_col('aih_total')),
                'sia_mc': val_num(get_col('sia_mc')),
                'sia_ac': val_num(get_col('sia_ac')),
                'sia_total': val_num(get_col('sia_total')),
                'teto_global': val_num(get_col('teto_global')),
                'teto_mc': val_num(get_col('teto_mc')),
                'teto_ac': val_num(get_col('teto_ac')),
                'teto_mac': val_num(get_col('teto_mac')),
                'total_teto_mac': val_num(get_col('total_teto_mac')),
                'portaria_ms_gm_8516': val_num(get_col('portaria_ms_gm_8516')),
                'integrasus': val_num(get_col('integrasus')),
                'iac': val_num(get_col('iac')),
                'sus_100': val_num(get_col('sus_100')),
                'opo': val_num(get_col('opo')),
                'rede_viver_sem_limite': val_num(get_col('rede_viver_sem_limite')),
                'rede_brasil_miseria': val_num(get_col('rede_brasil_miseria')),
                'rsme': val_num(get_col('rsme')),
                'rce_rceg': val_num(get_col('rce_rceg')),
                'rau_hosp_sos': val_num(get_col('rau_hosp_sos')),
                'rca_rcan': val_num(get_col('rca_rcan')),
                'iapi': val_num(get_col('iapi')),
                'residencia_medica': val_num(get_col('residencia_medica')),
                'melhor_em_casa': val_num(get_col('melhor_em_casa')),
                'cer': val_num(get_col('cer')),
                'doencas_raras': val_num(get_col('doencas_raras')),
                'oficina_ortopedica': val_num(get_col('oficina_ortopedica')),
                'ihac': val_num(get_col('ihac')),
                'total_mc_ac_incentivos': val_num(get_col('total_mc_ac_incentivos')),
                'arquivo_origem': os.path.basename(filepath),
            }

            if USE_SUPABASE:
                lote_supabase.append(registro)
                if len(lote_supabase) >= 200:
                    _flush_supabase(lote_supabase, substituir, resultado)
                    lote_supabase.clear()
            else:
                if not substituir:
                    count = conn.execute(
                        "SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND cnes=? AND unidade=?",
                        (ano, mes, cnes_raw, registro['unidade'])
                    ).fetchone()[0]
                    if count > 0:
                        resultado['pulados'] += 1
                        continue
                else:
                    conn.execute("DELETE FROM teto_mac WHERE ano=? AND mes=? AND cnes=? AND unidade=?",
                                 (ano, mes, cnes_raw, registro['unidade']))

                campos = list(registro.keys())
                conn.execute(
                    f"INSERT INTO teto_mac ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})",
                    [registro[k] for k in campos]
                )
                resultado['importados'] += 1

        if USE_SUPABASE and lote_supabase:
            _flush_supabase(lote_supabase, substituir, resultado)
        elif conn:
            conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        resultado['mensagens'].append(f'Erro durante importação: {e}')
        resultado['erros'] += 1
    finally:
        if conn:
            conn.close()

    # Registrar importação
    _registrar_importacao(resultado)
    return resultado

def _flush_supabase(lote, substituir, resultado):
    sb = get_sb()
    try:
        if substituir:
            sb.table('teto_mac').upsert(lote, on_conflict='ano,mes,cnes,unidade').execute()
        else:
            sb.table('teto_mac').insert(lote, upsert=False).execute()
        resultado['importados'] += len(lote)
    except Exception as e:
        resultado['erros'] += len(lote)
        resultado['mensagens'].append(f'Erro lote Supabase: {e}')

def _importar_openpyxl(wb, filepath, ano, mes, substituir, resultado):
    ws = wb.active
    rows_iter = list(ws.iter_rows(values_only=True))

    header_row = None
    for i, row in enumerate(rows_iter[:5]):
        row_strs = [str(v).strip().upper() if v else '' for v in row]
        if 'DRS' in row_strs:
            header_row = i
            break

    if header_row is None:
        resultado['mensagens'].append('Header não encontrado (xlsx)')
        resultado['erros'] = 1
        return resultado

    headers = list(rows_iter[header_row])
    mapa = mapear_colunas(headers)

    conn = get_db()
    try:
        for row in rows_iter[header_row + 1:]:
            if not row or all(v is None or str(v).strip() == '' for v in row[:7]):
                continue

            cnes_raw = val_str(row[mapa['cnes']]) if 'cnes' in mapa else ''

            resultado['total'] += 1

            registro = {
                'ano': ano, 'mes': mes,
                'drs': val_num(row[mapa['drs']]) if 'drs' in mapa else 0,
                'tipo': val_str(row[mapa['tipo']]) if 'tipo' in mapa else '',
                'hu': val_str(row[mapa['hu']]) if 'hu' in mapa else '',
                'municipio': val_str(row[mapa['municipio']]).upper() if 'municipio' in mapa else '',
                'cnes': cnes_raw,
                'cnpj': val_str(row[mapa['cnpj']]) if 'cnpj' in mapa else '',
                'unidade': val_str(row[mapa['unidade']]).upper() if 'unidade' in mapa else '',
                'total_mc_ac_incentivos': val_num(row[mapa['total_mc_ac_incentivos']]) if 'total_mc_ac_incentivos' in mapa else 0,
                'arquivo_origem': os.path.basename(filepath),
            }

            for campo in ['aih_fisico','aih_faec','sia_faec','aih_mc','aih_ac','sia_mc','sia_ac',
                          'teto_mac','total_teto_mac','integrasus','iac','sus_100','opo',
                          'residencia_medica','melhor_em_casa','cer','doencas_raras']:
                if campo in mapa and mapa[campo] < len(row):
                    registro[campo] = val_num(row[mapa[campo]])
                else:
                    registro[campo] = 0

            campos = list(registro.keys())
            placeholders = ', '.join(['?' for _ in campos])
            col_names = ', '.join(campos)
            valores = [registro[k] for k in campos]
            conn.execute(f"INSERT OR REPLACE INTO teto_mac ({col_names}) VALUES ({placeholders})", valores)
            resultado['importados'] += 1

        conn.commit()
    finally:
        conn.close()

    _registrar_importacao(resultado)
    return resultado

def _registrar_importacao(resultado):
    dados = {
        'arquivo': resultado['arquivo'],
        'ano': resultado.get('ano'),
        'mes': resultado.get('mes'),
        'total_registros': resultado.get('total', 0),
        'registros_importados': resultado.get('importados', 0),
        'registros_erro': resultado.get('erros', 0),
        'status': 'concluido' if resultado.get('erros', 0) == 0 else 'erro',
        'mensagem': '; '.join(resultado.get('mensagens', []))
    }
    if USE_SUPABASE:
        try:
            get_sb().table('importacoes').insert(dados).execute()
        except Exception:
            pass
    else:
        conn = get_db()
        conn.execute("""
            INSERT INTO importacoes (arquivo, ano, mes, total_registros, registros_importados,
                registros_erro, status, mensagem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, list(dados.values()))
        conn.commit()
        conn.close()

def importar_todos_finais(base_path, anos=None, substituir=False, callback=None):
    if anos is None:
        anos = list(range(2022, 2027))

    resultados = []
    for ano in anos:
        pasta = os.path.join(base_path, str(ano))
        if not os.path.exists(pasta):
            continue

        arquivos = sorted(os.listdir(pasta))
        finais = [f for f in arquivos if 'Final' in f and (f.endswith('.xls') or f.endswith('.xlsx'))]

        # Se não houver _Final, pegar o último arquivo do mês
        if not finais:
            finais = [f for f in arquivos if f.endswith('.xls') or f.endswith('.xlsx')]

        meses_vistos = set()
        for arq in finais:
            filepath = os.path.join(pasta, arq)
            ano_det, mes_det = extrair_ano_mes_do_nome(arq)
            if not ano_det:
                ano_det = ano
            if not mes_det:
                continue

            chave = (ano_det, mes_det)
            if chave in meses_vistos:
                continue
            meses_vistos.add(chave)

            res = importar_arquivo_xls(filepath, ano_det, mes_det, substituir)
            resultados.append(res)
            if callback:
                callback(res)

    return resultados
