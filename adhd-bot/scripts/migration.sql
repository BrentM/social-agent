-- ADHD Bot schema — run this once in the Supabase SQL editor before starting the bot.

CREATE TABLE IF NOT EXISTS posted_content (
    id          BIGSERIAL PRIMARY KEY,
    content_id  TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    tweet_id    TEXT,
    posted_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mentions_seen (
    id          BIGSERIAL PRIMARY KEY,
    mention_id  TEXT        NOT NULL UNIQUE,
    replied     BOOLEAN     DEFAULT FALSE,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS followed_accounts (
    id              BIGSERIAL PRIMARY KEY,
    twitter_user_id TEXT        NOT NULL UNIQUE,
    username        TEXT,
    followed_at     TIMESTAMPTZ DEFAULT NOW()
);
