-- Project 006 v3 - research-corpus row-level security policies.
--
-- Enforces two rules at the database layer:
--   1. A principal can only read a memo if they are in principal_visibility
--      for it, OR they are the owner_principal.
--   2. MNPI memos (contains_mnpi = TRUE) are ALWAYS readable by the owner
--      and compliance role, never by anyone else - even with visibility
--      grants. This is the hard fence for MNPI leakage.
--
-- The app sets `SET LOCAL app.current_principal = '<principal_id>'` at
-- the start of every read txn. Without that setting, RLS returns zero rows.
-- That fail-closed default is intentional.

ALTER TABLE research_memo ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE principal_visibility ENABLE ROW LEVEL SECURITY;

-- Drop old policies if rerunning
DROP POLICY IF EXISTS memo_select_policy ON research_memo;
DROP POLICY IF EXISTS chunk_select_policy ON research_chunk;
DROP POLICY IF EXISTS visibility_select_policy ON principal_visibility;

-- --------------------------------------------------------------
-- SELECT: own || visibility-granted || (compliance-role AND flagged)
-- --------------------------------------------------------------
CREATE POLICY memo_select_policy ON research_memo
    FOR SELECT
    USING (
        (
            -- owner always sees their own memos
            owner_principal = current_setting('app.current_principal', true)
        )
        OR (
            -- visibility grant; but never bypasses MNPI fence
            contains_mnpi = FALSE
            AND EXISTS (
                SELECT 1 FROM principal_visibility pv
                WHERE pv.memo_id = research_memo.memo_id
                  AND pv.principal = current_setting('app.current_principal', true)
            )
        )
        OR (
            -- compliance role can read everything including MNPI
            current_setting('app.current_role', true) = 'compliance'
        )
    );

-- --------------------------------------------------------------
-- SELECT chunks: only if parent memo is visible to current principal
-- --------------------------------------------------------------
CREATE POLICY chunk_select_policy ON research_chunk
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM research_memo m
            WHERE m.memo_id = research_chunk.memo_id
            -- the memo select policy implicitly filters here via RLS reentry
        )
    );

-- --------------------------------------------------------------
-- SELECT visibility: only own rows
-- --------------------------------------------------------------
CREATE POLICY visibility_select_policy ON principal_visibility
    FOR SELECT
    USING (
        principal = current_setting('app.current_principal', true)
        OR current_setting('app.current_role', true) = 'admin'
    );

-- Writes are always allowed for the service role (no RLS on inserts from
-- the CDC Lambda which uses a FORCE ROW LEVEL SECURITY EXCEPTION role).
-- See CDK IAM grants.
