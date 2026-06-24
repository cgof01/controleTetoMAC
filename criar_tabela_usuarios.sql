-- Execute este SQL no Supabase Dashboard → SQL Editor → New Query
-- Cria a tabela de usuários e o usuário admin

CREATE TABLE IF NOT EXISTS usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT DEFAULT 'usuario',
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    ultimo_acesso TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

ALTER TABLE usuarios DISABLE ROW LEVEL SECURITY;

-- Usuário admin inicial (senha: 123456)
INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
VALUES (
    'Adan Freire Pereira',
    'afpereira@saude.sp.gov.br',
    'scrypt:32768:8:1$LBwmdFHofSakmCW6$5ed4f3b42c515f03e7e364590034c7e2804f133531afadac98a75c3b0a7f027479a3a352da74f74b9c026feaa59a507cbe4bfe4a345126d4e39b918522ec25bd',
    'admin',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    senha_hash = EXCLUDED.senha_hash,
    perfil = EXCLUDED.perfil,
    ativo = EXCLUDED.ativo;

SELECT id, nome, email, perfil, ativo FROM usuarios;
