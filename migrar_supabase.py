"""
migrar_supabase.py — Migra os 18.316 registros do SQLite para o Supabase.
Execute UMA VEZ após criar as tabelas no Supabase SQL Editor.
"""
import sqlite3
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

DB_PATH = os.path.join(os.path.dirname(__file__), 'teto_mac.db')
BATCH_SIZE = 200  # registros por requisição

def migrar():
    print("="*60)
    print("  MIGRAÇÃO SQLite → Supabase")
    print("="*60)

    # Verificar banco local
    if not os.path.exists(DB_PATH):
        print("ERRO: teto_mac.db não encontrado!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total_local = conn.execute("SELECT COUNT(*) FROM teto_mac").fetchone()[0]
    print(f"\n  Registros no SQLite: {total_local}")

    # Conectar Supabase
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Verificar se já tem dados no Supabase
    r = sb.table('teto_mac').select('id', count='exact').limit(1).execute()
    total_remoto = r.count or 0
    print(f"  Registros no Supabase: {total_remoto}")

    if total_remoto > 0:
        resp = input(f"\n  Já existem {total_remoto} registros no Supabase. Deseja apagar e reimportar? (s/N): ")
        if resp.lower() == 's':
            print("  Apagando registros existentes...")
            # Deletar em lotes
            while True:
                r2 = sb.table('teto_mac').select('id').limit(500).execute()
                if not r2.data:
                    break
                ids = [row['id'] for row in r2.data]
                sb.table('teto_mac').delete().in_('id', ids).execute()
                print(f"    Apagados {len(ids)} registros...")
            print("  Supabase limpo.")
        else:
            print("  Migração cancelada.")
            conn.close()
            return

    # Buscar todos os registros do SQLite
    campos_excluir = {'id', 'created_at', 'updated_at'}
    rows = conn.execute("SELECT * FROM teto_mac").fetchall()
    conn.close()

    total = len(rows)
    print(f"\n  Iniciando migração de {total} registros em lotes de {BATCH_SIZE}...")
    print()

    importados = 0
    erros = 0
    inicio = time.time()

    for i in range(0, total, BATCH_SIZE):
        lote = rows[i:i + BATCH_SIZE]
        dados = []
        for row in lote:
            d = dict(row)
            # Remover campos gerenciados pelo Supabase
            for c in campos_excluir:
                d.pop(c, None)
            # Converter None para 0 em campos numéricos
            campos_num = {
                'aih_fisico','aih_faec','sia_faec','equip_hemodialise',
                'limite_complementacao','aih_mc','aih_ac','aih_total',
                'sia_mc','sia_ac','sia_total','teto_global','teto_mc','teto_ac',
                'teto_mac','total_teto_mac','portaria_ms_gm_8516',
                'integrasus','iac','sus_100','opo','rede_viver_sem_limite',
                'rede_brasil_miseria','rsme','rce_rceg','rau_hosp_sos','rca_rcan',
                'iapi','residencia_medica','melhor_em_casa','cer','doencas_raras',
                'oficina_ortopedica','ihac','total_mc_ac_incentivos','drs'
            }
            for f in campos_num:
                if f in d and d[f] is None:
                    d[f] = 0.0
            dados.append(d)

        try:
            sb.table('teto_mac').insert(dados).execute()
            importados += len(lote)
        except Exception as e:
            print(f"  ERRO no lote {i//BATCH_SIZE + 1}: {e}")
            # Tentar um por um
            for reg in dados:
                try:
                    sb.table('teto_mac').insert(reg).execute()
                    importados += 1
                except Exception as e2:
                    erros += 1

        # Progresso
        pct = importados / total * 100
        elapsed = time.time() - inicio
        eta = (elapsed / max(importados, 1)) * (total - importados)
        bar = '█' * int(pct // 5) + '░' * (20 - int(pct // 5))
        print(f"\r  [{bar}] {importados}/{total} ({pct:.1f}%) — ETA: {eta:.0f}s", end='', flush=True)

    print()
    elapsed = time.time() - inicio
    print(f"\n{'='*60}")
    print(f"  MIGRAÇÃO CONCLUÍDA em {elapsed:.1f}s")
    print(f"  Importados: {importados}")
    print(f"  Erros:      {erros}")
    print(f"{'='*60}")

    # Verificar contagem final
    r_final = sb.table('teto_mac').select('id', count='exact').limit(1).execute()
    print(f"  Registros no Supabase agora: {r_final.count}")

    # Migrar importações
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    imp_rows = conn2.execute("SELECT * FROM importacoes").fetchall()
    conn2.close()

    if imp_rows:
        imp_dados = []
        for row in imp_rows:
            d = dict(row)
            d.pop('id', None)
            d.pop('created_at', None)
            imp_dados.append(d)
        try:
            sb.table('importacoes').insert(imp_dados).execute()
            print(f"  Histórico de importações migrado: {len(imp_dados)} registros")
        except Exception as e:
            print(f"  Aviso ao migrar importações: {e}")

if __name__ == '__main__':
    migrar()
