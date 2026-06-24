"""
Execute este script UMA VEZ para criar a tabela de usuários e o admin no Supabase.
  python setup_admin.py
"""
import httpx
import warnings
warnings.filterwarnings('ignore')

# Patch SSL antes de importar supabase
_orig = httpx.Client.__init__
def _no_ssl(self, *a, **kw):
    kw['verify'] = False
    _orig(self, *a, **kw)
httpx.Client.__init__ = _no_ssl

from werkzeug.security import generate_password_hash
from config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN = {
    'nome': 'Adan Freire Pereira',
    'email': 'afpereira@saude.sp.gov.br',
    'senha_hash': generate_password_hash('123456'),
    'perfil': 'admin',
    'ativo': True,
}

print("Verificando tabela usuarios no Supabase...")
try:
    r = sb.table('usuarios').select('id').limit(1).execute()
    print("  Tabela OK.")
except Exception as e:
    print(f"  ERRO: {e}")
    print("  Execute primeiro o SQL de schema_supabase.sql no Supabase Dashboard.")
    exit(1)

print(f"Inserindo admin: {ADMIN['email']} ...")
existing = sb.table('usuarios').select('id').eq('email', ADMIN['email']).execute()
if existing.data:
    print("  Admin já existe. Atualizando senha...")
    sb.table('usuarios').update({'senha_hash': ADMIN['senha_hash']}).eq('email', ADMIN['email']).execute()
else:
    sb.table('usuarios').insert(ADMIN).execute()
    print("  Admin criado com sucesso!")

print("\nPronto! Login:")
print(f"  Email: {ADMIN['email']}")
print(f"  Senha: 123456")
