-- ============================================================
-- Adiciona a coluna 'acessos' na tabela usuarios: permite ao admin
-- restringir quais seções do menu (Dashboard, Consultar/Editar, Nova
-- Competência, Gráficos, Central de Relatórios, Detalhamento) um usuário
-- de perfil 'usuario' pode acessar.
-- NULL = sem restrição (acesso a todas as seções, comportamento atual,
-- preservado para todo usuário já cadastrado). Quando preenchida, é uma
-- lista separada por vírgula com as chaves liberadas, ex.:
-- 'dashboard,pesquisa,graficos'. Perfil 'admin' ignora esta coluna —
-- administrador sempre tem acesso total.
-- Execute no Supabase: Dashboard -> SQL Editor -> New query. Idempotente.
-- ============================================================

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS acessos TEXT;

SELECT 'OK — coluna acessos criada em usuarios.' AS status;
