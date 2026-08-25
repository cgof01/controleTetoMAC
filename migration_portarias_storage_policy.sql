-- ============================================================
-- Política de Storage para o bucket "portarias" (anexos em PDF)
-- ============================================================
-- Pré-requisito: crie o bucket antes, pelo Dashboard do Supabase
--   Storage → New bucket → nome "portarias" → Private
--   (bucket não pode ser criado por SQL, só pela chave service_role ou pelo Dashboard)
--
-- Mesmo com o bucket criado, o Storage bloqueia upload/download por padrão
-- (RLS) até existir uma política liberando acesso. O app usa a chave
-- "publishable" (role anon) — mesmo padrão de acesso interno já usado nas
-- outras tabelas do sistema (RLS desabilitado / liberado, controle de acesso
-- feito no login do Flask, não no Postgres).

CREATE POLICY "portarias_anon_all"
ON storage.objects
FOR ALL
TO anon
USING (bucket_id = 'portarias')
WITH CHECK (bucket_id = 'portarias');
