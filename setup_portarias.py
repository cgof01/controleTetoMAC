"""
setup_portarias.py
Cria o bucket 'portarias' no Supabase Storage (privado).
Execute uma única vez após rodar schema_portarias_supabase.sql.

    python setup_portarias.py
"""
import httpx, ssl

# Desabilitar verificação SSL (igual ao app)
_orig = httpx.Client.__init__
def _no_ssl(self, *a, **kw):
    kw['verify'] = False
    _orig(self, *a, **kw)
httpx.Client.__init__ = _no_ssl

from config import SUPABASE_URL, SUPABASE_KEY, USE_SUPABASE

if not USE_SUPABASE:
    print("USE_SUPABASE=False — nada a fazer (modo SQLite local).")
    raise SystemExit(0)

from supabase import create_client
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = 'portarias'

try:
    buckets     = sb.storage.list_buckets()
    nomes       = [b.name for b in buckets] if buckets else []

    if BUCKET in nomes:
        print(f"Bucket '{BUCKET}' já existe. Nenhuma ação necessária.")
    else:
        sb.storage.create_bucket(BUCKET, options={'public': False})
        print(f"Bucket '{BUCKET}' criado com sucesso (privado).")

    print("\nVerificando tabela portarias...")
    r = sb.table('portarias').select('id').limit(1).execute()
    print("Tabela 'portarias' acessível.")

    print("\n✔  Setup concluído. O sistema está pronto para usar portarias.")

except Exception as e:
    print(f"\n✘  Erro: {e}")
    print("\nCertifique-se de que:")
    print("  1. schema_portarias_supabase.sql foi executado no Supabase SQL Editor")
    print("  2. SUPABASE_URL e SUPABASE_KEY estão corretos em config.py")
