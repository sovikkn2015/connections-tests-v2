-- Project 006 v3 - research-corpus Aurora PostgreSQL schema.
-- Provisioned by aws/cdk/. pgvector extension required (15+).
--
-- Two primary tables:
--   research_memo   one row per Salesforce Research_Memo__c
--   research_chunk  one row per embedded chunk (N per memo)
--
-- Principals:
--   principal              OpenClaw user id (sub from Okta / JWT)
--   principal_visibility   many-to-many between principals and memos,
--                          mirroring Salesforce sharing rules exactly
--
-- All queries go through read-time filter in sharing_rules.py; row-level
-- security policies (002_rls_policies.sql) are the second fence. Both
-- are belt and braces: if the app forgets to set app.current_principal,
-- RLS returns zero rows instead of the whole table.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- Memos (document level)
-- ============================================================
CREATE TABLE IF NOT EXISTS research_memo (
    memo_id              TEXT PRIMARY KEY,                    -- SF Research_Memo__c.Id
    title                TEXT NOT NULL,
    author_sf_user_id    TEXT NOT NULL,
    owner_principal      TEXT NOT NULL,                       -- OpenClaw principal
    ticker               TEXT,
    sector               TEXT,
    classification       TEXT NOT NULL DEFAULT 'internal',    -- internal | client | public
    contains_mnpi        BOOLEAN NOT NULL DEFAULT FALSE,      -- HARD FENCE for MNPI (never to KB)
    created_at           TIMESTAMPTZ NOT NULL,
    updated_at           TIMESTAMPTZ NOT NULL,
    sf_last_modified_at  TIMESTAMPTZ NOT NULL,
    version              INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_memo_ticker    ON research_memo(ticker);
CREATE INDEX IF NOT EXISTS idx_memo_sector    ON research_memo(sector);
CREATE INDEX IF NOT EXISTS idx_memo_class     ON research_memo(classification);
CREATE INDEX IF NOT EXISTS idx_memo_owner     ON research_memo(owner_principal);
CREATE INDEX IF NOT EXISTS idx_memo_title_trgm
    ON research_memo USING gin (title gin_trgm_ops);

-- ============================================================
-- Chunks (embedding level)
-- ============================================================
CREATE TABLE IF NOT EXISTS research_chunk (
    chunk_id        BIGSERIAL PRIMARY KEY,
    memo_id         TEXT NOT NULL REFERENCES research_memo(memo_id) ON DELETE CASCADE,
    chunk_order     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    section         TEXT,
    token_count     INTEGER,
    embedding       vector(1024) NOT NULL,              -- Titan v2 normalized
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunk_memo ON research_chunk(memo_id);

-- HNSW for cosine similarity (Titan v2 is normalized -> cosine == inner product,
-- but we index with cosine for clarity). Build params tuned for ~100k chunks.
CREATE INDEX IF NOT EXISTS idx_chunk_embedding_hnsw
    ON research_chunk USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- BM25-ish full-text index for hybrid retrieval.
CREATE INDEX IF NOT EXISTS idx_chunk_text_gin
    ON research_chunk USING gin (to_tsvector('english', text));

-- ============================================================
-- Principal visibility (SF sharing rule mirror)
-- ============================================================
CREATE TABLE IF NOT EXISTS principal_visibility (
    principal       TEXT NOT NULL,
    memo_id         TEXT NOT NULL REFERENCES research_memo(memo_id) ON DELETE CASCADE,
    access_level    TEXT NOT NULL DEFAULT 'read',              -- read | edit | owner
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (principal, memo_id)
);

CREATE INDEX IF NOT EXISTS idx_pv_principal ON principal_visibility(principal);

-- ============================================================
-- Housekeeping: upsert helper for CDC handler
-- ============================================================
CREATE OR REPLACE FUNCTION upsert_memo(
    p_memo_id TEXT,
    p_title TEXT,
    p_author_sf_user_id TEXT,
    p_owner_principal TEXT,
    p_ticker TEXT,
    p_sector TEXT,
    p_classification TEXT,
    p_contains_mnpi BOOLEAN,
    p_sf_last_modified_at TIMESTAMPTZ
) RETURNS VOID AS $$
BEGIN
    INSERT INTO research_memo (
        memo_id, title, author_sf_user_id, owner_principal,
        ticker, sector, classification, contains_mnpi,
        created_at, updated_at, sf_last_modified_at
    ) VALUES (
        p_memo_id, p_title, p_author_sf_user_id, p_owner_principal,
        p_ticker, p_sector, p_classification, p_contains_mnpi,
        now(), now(), p_sf_last_modified_at
    )
    ON CONFLICT (memo_id) DO UPDATE SET
        title = EXCLUDED.title,
        author_sf_user_id = EXCLUDED.author_sf_user_id,
        owner_principal = EXCLUDED.owner_principal,
        ticker = EXCLUDED.ticker,
        sector = EXCLUDED.sector,
        classification = EXCLUDED.classification,
        contains_mnpi = EXCLUDED.contains_mnpi,
        sf_last_modified_at = EXCLUDED.sf_last_modified_at,
        updated_at = now(),
        version = research_memo.version + 1;
END;
$$ LANGUAGE plpgsql;
