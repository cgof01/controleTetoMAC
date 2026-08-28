import xlrd
import openpyxl
import os
import re
import json
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
        elif 'REDE ALYNE' in hn:
            mapa['rede_alyne'] = i
        elif 'CUIDADOS PALIATIVOS' in hn or hn == 'PNCP' or 'PNCP' in hn:
            mapa['pncp'] = i
        # As variantes "Custeio UTI" / "Custeio" são colunas distintas do valor de
        # Incentivo já mapeado abaixo (mesma sigla RCE/RAU/RCA, mas outro conceito) —
        # por isso precisam ser checadas ANTES das condições genéricas de RCE/RAU/RCA.
        elif ('RCE' in hn or 'RCEG' in hn) and 'CUSTEIO' in hn:
            if 'rce_rceg_custeio' not in mapa:
                mapa['rce_rceg_custeio'] = i
        elif ('RAU' in hn or 'HOSP SOS' in hn) and 'CUSTEIO' in hn:
            if 'rau_hosp_sos_custeio' not in mapa:
                mapa['rau_hosp_sos_custeio'] = i
        elif ('RCA' in hn or 'RCAN' in hn) and 'CUSTEIO' in hn:
            if 'rca_rcan_custeio' not in mapa:
                mapa['rca_rcan_custeio'] = i
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
        elif 'MC' in hn and 'AC' in hn and 'INCENTIVO' in hn:
            # Cobre tanto "TOTAL MC + AC + INCENTIVOS" quanto a variante mais antiga
            # sem o prefixo "TOTAL" ("MC + AC + INCENTIVOS", vista em arquivos de 2020).
            mapa['total_mc_ac_incentivos'] = i

    return mapa

def val_num(v):
    if v is None or v == '':
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def val_int(v):
    return int(round(val_num(v)))

def val_str(v):
    if v is None:
        return ''
    s = str(v).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s

# Colunas reconhecidas por mapear_colunas que ainda não têm coluna dedicada em
# teto_mac — vão para campos_extras (JSON), o mesmo mecanismo usado pelos campos
# personalizados criados em Admin > Campos, sem precisar de migração de schema.
_CAMPOS_EXTRAS_IMPORT = (
    'rede_alyne', 'pncp', 'rce_rceg_custeio', 'rau_hosp_sos_custeio', 'rca_rcan_custeio',
)

def _montar_registro(row_vals, mapa, ano, mes, nome_arquivo):
    """Constrói o dict de uma linha da planilha, ou None se a linha estiver em branco."""
    drs_val = row_vals[mapa['drs']] if 'drs' in mapa and mapa['drs'] < len(row_vals) else ''
    unidade_val = row_vals[mapa['unidade']] if 'unidade' in mapa and mapa['unidade'] < len(row_vals) else ''
    if str(drs_val).strip() == '' and str(unidade_val).strip() == '':
        return None
    # Linha de rodapé de soma da planilha (ex.: "TOTAL", "TOTAL GERAL") — não é
    # um registro de unidade e não deve ser gravada nem somada ao total do sistema.
    if 'TOTAL' in str(drs_val).strip().upper() or 'TOTAL' in str(unidade_val).strip().upper():
        return None

    def get_col(campo):
        return row_vals[mapa[campo]] if campo in mapa and mapa[campo] < len(row_vals) else 0

    cnes_raw = val_str(get_col('cnes'))
    if cnes_raw and cnes_raw != 'RESREC':
        try:
            cnes_raw = str(int(float(cnes_raw)))
        except (ValueError, TypeError):
            pass

    registro = {
        'ano': ano, 'mes': mes,
        'drs': val_num(get_col('drs')),
        'tipo': val_str(get_col('tipo')),
        'hu': val_str(get_col('hu')),
        'municipio': val_str(get_col('municipio')).upper(),
        'cnes': cnes_raw,
        'cnpj': val_str(get_col('cnpj')),
        'unidade': val_str(get_col('unidade')).upper(),
        'aih_fisico': val_int(get_col('aih_fisico')),
        'aih_faec': val_num(get_col('aih_faec')),
        'sia_faec': val_num(get_col('sia_faec')),
        'equip_hemodialise': val_num(get_col('equip_hemodialise')),
        'limite_complementacao': val_num(get_col('limite_complementacao')),
        'aih_mc': val_num(get_col('aih_mc')),
        'aih_ac': val_num(get_col('aih_ac')),
        # aih_total/sia_total sempre calculados — a planilha fonte nunca traz uma
        # coluna "AIH TOTAL"/"SIA TOTAL" pronta (só MC/AC/FAEC separados), então
        # ler get_col('aih_total') sempre voltava 0. Mesma fórmula do campo
        # 'calculado' correspondente em campo_config (aih_faec+aih_mc+aih_ac).
        'aih_total': val_num(get_col('aih_faec')) + val_num(get_col('aih_mc')) + val_num(get_col('aih_ac')),
        'sia_mc': val_num(get_col('sia_mc')),
        'sia_ac': val_num(get_col('sia_ac')),
        'sia_total': val_num(get_col('sia_faec')) + val_num(get_col('sia_mc')) + val_num(get_col('sia_ac')),
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
        'arquivo_origem': nome_arquivo,
    }

    # Só grava campos_extras quando a planilha realmente tem alguma dessas colunas —
    # não sobrescrever com {} e apagar campos personalizados que já existam no
    # registro (ex.: adicionados manualmente em Admin > Campos) quando a mesma
    # competência for reimportada.
    extras = {campo: val_num(get_col(campo)) for campo in _CAMPOS_EXTRAS_IMPORT if campo in mapa}
    if extras:
        registro['campos_extras'] = extras
    return registro

def _gravar_registros(linhas, mapa, ano, mes, nome_arquivo, resultado):
    """Grava as linhas já mapeadas no banco, atualizando quem já existe (mesma
    competência + cnes + unidade) e inserindo apenas o que for novo — nunca duplica."""
    registros = {}
    for row_vals in linhas:
        registro = _montar_registro(row_vals, mapa, ano, mes, nome_arquivo)
        if registro is None:
            continue
        resultado['total'] += 1
        registros[(registro['cnes'], registro['unidade'])] = registro

    if not registros:
        return

    if USE_SUPABASE:
        try:
            r = get_sb().table('teto_mac').select('cnes,unidade').eq('ano', ano).eq('mes', mes).execute()
            existentes = {(row['cnes'], row['unidade']) for row in (r.data or [])}
        except Exception:
            existentes = set()

        chaves = list(registros.keys())
        for i in range(0, len(chaves), 500):
            bloco_chaves = chaves[i:i + 500]
            lote = [registros[k] for k in bloco_chaves]
            novos = sum(1 for k in bloco_chaves if k not in existentes)
            atualizados = len(bloco_chaves) - novos
            try:
                get_sb().table('teto_mac').upsert(lote, on_conflict='ano,mes,cnes,unidade').execute()
                resultado['importados'] += novos
                resultado['atualizados'] += atualizados
            except Exception as e:
                resultado['erros'] += len(lote)
                resultado['mensagens'].append(f'Erro lote Supabase: {e}')
    else:
        conn = get_db()
        try:
            for (cnes_v, unidade_v), registro in registros.items():
                existia = conn.execute(
                    "SELECT COUNT(*) FROM teto_mac WHERE ano=? AND mes=? AND cnes=? AND unidade=?",
                    (ano, mes, cnes_v, unidade_v)
                ).fetchone()[0] > 0
                conn.execute("DELETE FROM teto_mac WHERE ano=? AND mes=? AND cnes=? AND unidade=?",
                             (ano, mes, cnes_v, unidade_v))
                if isinstance(registro.get('campos_extras'), dict):
                    registro = dict(registro)
                    registro['campos_extras'] = json.dumps(registro['campos_extras'], ensure_ascii=False)
                campos = list(registro.keys())
                conn.execute(
                    f"INSERT INTO teto_mac ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})",
                    [registro[k] for k in campos]
                )
                if existia:
                    resultado['atualizados'] += 1
                else:
                    resultado['importados'] += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            resultado['mensagens'].append(f'Erro durante importação: {e}')
            resultado['erros'] += 1
        finally:
            conn.close()

def importar_arquivo_xls(filepath, ano=None, mes=None, nome_original=None):
    resultado = {
        'arquivo': nome_original or os.path.basename(filepath),
        'ano': ano, 'mes': mes,
        'total': 0, 'importados': 0, 'atualizados': 0, 'erros': 0,
        'mensagens': []
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

        header_row = None
        for r in range(min(5, ws.nrows)):
            row_strs = [str(ws.cell_value(r, c)).strip().upper() for c in range(ws.ncols)]
            if 'DRS' in row_strs:
                header_row = r
                break

        if header_row is None:
            resultado['mensagens'].append('Header não encontrado')
            resultado['erros'] = 1
            return resultado

        headers = [ws.cell_value(header_row, c) for c in range(ws.ncols)]
        mapa = mapear_colunas(headers)
        linhas = [[ws.cell_value(r, c) for c in range(ws.ncols)] for r in range(header_row + 1, ws.nrows)]
    except Exception:
        wb2 = None
        try:
            # read_only=True mantém o arquivo aberto (zip mapeado em memória) até
            # wb2.close() ser chamado — sem isso, no Windows o arquivo temporário
            # criado pelo Flask em /importar fica travado e o os.unlink() que
            # limpa o temp file depois da importação falha com "arquivo em uso".
            wb2 = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            ws2 = wb2.active
            rows_iter = list(ws2.iter_rows(values_only=True))

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

            mapa = mapear_colunas(list(rows_iter[header_row]))
            linhas = rows_iter[header_row + 1:]
        except Exception as e2:
            resultado['mensagens'].append(f'Erro ao abrir arquivo: {e2}')
            resultado['erros'] = 1
            return resultado
        finally:
            if wb2 is not None:
                wb2.close()

    if 'drs' not in mapa or 'unidade' not in mapa:
        resultado['mensagens'].append(f'Colunas essenciais não encontradas. Mapeadas: {list(mapa.keys())}')
        resultado['erros'] = 1
        return resultado

    _gravar_registros(linhas, mapa, ano, mes, nome_original or os.path.basename(filepath), resultado)
    _registrar_importacao(resultado)
    return resultado

def _registrar_importacao(resultado):
    dados = {
        'arquivo': resultado['arquivo'],
        'ano': resultado.get('ano'),
        'mes': resultado.get('mes'),
        'total_registros': resultado.get('total', 0),
        'registros_importados': resultado.get('importados', 0),
        'registros_atualizados': resultado.get('atualizados', 0),
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
                registros_atualizados, registros_erro, status, mensagem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, list(dados.values()))
        conn.commit()
        conn.close()

def importar_todos_finais(base_path, anos=None, callback=None):
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

            res = importar_arquivo_xls(filepath, ano_det, mes_det)
            resultados.append(res)
            if callback:
                callback(res)

    return resultados
