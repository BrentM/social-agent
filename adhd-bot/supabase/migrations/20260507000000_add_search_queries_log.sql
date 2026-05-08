-- Add search_queries log table so we can analyse what Claude searched,
-- how many results each query returned, and which agent strategy issued it.
-- The code change that populates discovered_posts.search_query ships alongside this.

CREATE TABLE IF NOT EXISTS search_queries (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    query        TEXT        NOT NULL,
    result_count INT         NOT NULL DEFAULT 0,
    strategy     TEXT        CHECK (strategy IN ('warmup', 'growth')),
    ran_at       TIMESTAMPTZ DEFAULT NOW()
);
