-- Engagement reply agent schema.
-- Adds reply tracking table and marks discovered posts as evaluated.

ALTER TABLE discovered_posts
    ADD COLUMN IF NOT EXISTS reply_attempted boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS agent_replies (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    x_post_id       text,
    in_reply_to     text,
    text            text,
    reason          text        NOT NULL,
    skipped         boolean     NOT NULL DEFAULT false,
    posted_at       timestamptz NOT NULL DEFAULT now()
);
