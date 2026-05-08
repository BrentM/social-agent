ALTER TABLE discovered_posts
    ADD COLUMN IF NOT EXISTS reply_settings TEXT DEFAULT 'everyone';
