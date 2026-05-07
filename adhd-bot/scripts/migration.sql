-- ADHD Bot — full schema migration
-- Safe to run multiple times (all statements use IF NOT EXISTS / ON CONFLICT DO NOTHING).

-- ── Existing tables ──────────────────────────────────────────────────────────

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

-- ── Content items (replaces facts.json + tips.json) ──────────────────────────
-- source: 'seed' = original library, 'generated' = Claude-written

CREATE TABLE IF NOT EXISTS content_items (
    id          BIGSERIAL   PRIMARY KEY,
    content_id  TEXT        NOT NULL UNIQUE,
    type        TEXT        NOT NULL CHECK (type IN ('fact', 'tip')),
    text        TEXT        NOT NULL,
    emoji       TEXT,
    topic       TEXT,
    source      TEXT        NOT NULL DEFAULT 'seed' CHECK (source IN ('seed', 'generated')),
    active      BOOLEAN     DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Reply templates (replaces replies.json) ──────────────────────────────────

CREATE TABLE IF NOT EXISTS reply_templates (
    id          BIGSERIAL   PRIMARY KEY,
    intent      TEXT        NOT NULL CHECK (intent IN ('question', 'positive', 'general')),
    text        TEXT        NOT NULL,
    active      BOOLEAN     DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Configured queries (replaces follow_targets + research_targets keywords/hashtags)
-- purpose: 'follow' = used by follower.py to find accounts to follow
--          'research_keyword' = used by researcher.py keyword search
--          'research_hashtag' = used by researcher.py hashtag search

CREATE TABLE IF NOT EXISTS configured_queries (
    id          BIGSERIAL   PRIMARY KEY,
    query       TEXT        NOT NULL,
    purpose     TEXT        NOT NULL CHECK (purpose IN ('follow', 'research_keyword', 'research_hashtag')),
    active      BOOLEAN     DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (query, purpose)
);

-- ── Configured accounts (replaces follow_targets seed_accounts + research key_people)
-- is_follow_seed: bot should follow this account
-- is_research:    pull this account's timeline for content signals
-- An account can serve both purposes simultaneously.

CREATE TABLE IF NOT EXISTS configured_accounts (
    id              BIGSERIAL   PRIMARY KEY,
    username        TEXT        NOT NULL UNIQUE,
    twitter_user_id TEXT,
    is_follow_seed  BOOLEAN     DEFAULT FALSE,
    is_research     BOOLEAN     DEFAULT FALSE,
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Research posts (discovered from X — reference only, never posted) ────────

CREATE TABLE IF NOT EXISTS research_posts (
    id              BIGSERIAL   PRIMARY KEY,
    tweet_id        TEXT        NOT NULL UNIQUE,
    author_username TEXT,
    text            TEXT        NOT NULL,
    like_count      INT         DEFAULT 0,
    retweet_count   INT         DEFAULT 0,
    reply_count     INT         DEFAULT 0,
    source          TEXT        CHECK (source IN ('keyword', 'key_person', 'hashtag')),
    source_query    TEXT,
    discovered_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── x_agent growth system tables ─────────────────────────────────────────────
-- Additive to the bot/ system. Prefix agent_* to avoid ambiguity.

CREATE TABLE IF NOT EXISTS discovered_users (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    x_user_id        TEXT        NOT NULL UNIQUE,
    username         TEXT,
    bio              TEXT,
    followers_count  INT         DEFAULT 0,
    followed_by_agent BOOLEAN    DEFAULT FALSE,
    followed_at      TIMESTAMPTZ,
    discovered_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discovered_posts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    x_post_id     TEXT        NOT NULL UNIQUE,
    author_x_id   TEXT        REFERENCES discovered_users(x_user_id),
    text          TEXT,
    like_count    INT         DEFAULT 0,
    search_query  TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_tweets (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    x_post_id  TEXT,
    text       TEXT,
    posted_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at              TIMESTAMPTZ DEFAULT NOW(),
    strategy_selected   TEXT,
    reason              TEXT,
    post_count_at_time  INT
);

-- ── Seed data ────────────────────────────────────────────────────────────────

-- Facts (from facts.json)
INSERT INTO content_items (content_id, type, text, emoji, topic) VALUES
('fact_001', 'fact', 'ADHD affects ~4–5% of adults worldwide. You are very much not alone in this.',                                                                                    '🌍', 'prevalence'),
('fact_002', 'fact', 'The ADHD brain has lower baseline dopamine levels. That craving for novelty and excitement? It''s biology, not a character flaw.',                               '🧠', 'brain_science'),
('fact_003', 'fact', 'ADHD is ~75% heritable. If you have it, there''s a good chance a parent or sibling does too — often undiagnosed.',                                              '🧬', 'genetics'),
('fact_004', 'fact', 'Time blindness is real. ADHD brains have difficulty sensing time passing, which is why ''just 5 minutes'' becomes 2 hours.',                                    '⏰', 'symptoms'),
('fact_005', 'fact', 'Hyperfocus is a genuine ADHD superpower. When something sparks interest, the ADHD brain can sustain deep, intense focus for hours.',                           '🔥', 'strengths'),
('fact_006', 'fact', 'Women and girls with ADHD are significantly underdiagnosed. Symptoms often present differently and get mistaken for anxiety or being ''ditzy''.',               '💙', 'diagnosis'),
('fact_007', 'fact', 'Exercise is one of the most evidence-backed non-medication treatments for ADHD — it boosts dopamine AND norepinephrine.',                                      '🏃', 'treatment'),
('fact_008', 'fact', 'Up to 80% of people with ADHD have sleep problems, often due to a delayed circadian rhythm. Night owl tendencies aren''t laziness.',                          '🌙', 'sleep'),
('fact_009', 'fact', 'ADHD and anxiety co-occur in about 50% of adults with ADHD. Often the anxiety IS the ADHD — fear of forgetting, failing, or falling behind.',                 '💭', 'comorbidities'),
('fact_010', 'fact', 'The ADHD prefrontal cortex (responsible for planning and impulse control) develops on average 3 years behind neurotypical peers.',                             '🧪', 'brain_science'),
('fact_011', 'fact', 'Many adults weren''t diagnosed until adulthood — sometimes their 30s, 40s, or later. Late diagnosis is valid, and it changes everything.',                    '💡', 'diagnosis'),
('fact_012', 'fact', 'ADHD brains show more creative cross-connections between brain regions. That ''random'' idea you had mid-conversation? Classic ADHD brain working.',           '✨', 'strengths'),
('fact_013', 'fact', 'Rejection sensitive dysphoria (RSD) isn''t in the DSM, but it''s one of the most painful aspects of ADHD for many adults. Your feelings are valid.',         '❤️', 'emotional'),
('fact_014', 'fact', 'ADHD is not a problem of knowing what to do — it''s a problem of doing what you know. Executive function is the bottleneck, not intelligence.',               '🎯', 'brain_science'),
('fact_015', 'fact', 'Studies show people with ADHD are more likely to be entrepreneurs. The impulsivity, risk tolerance, and creative thinking? Business advantages.',              '🚀', 'strengths'),
('fact_016', 'fact', 'The ADHD nervous system is interest-based, not importance-based. That''s why you can play video games for 8 hours but can''t write a 1-page report.',         '🎮', 'brain_science'),
('fact_017', 'fact', 'ADHD medication doesn''t ''fix'' the brain — it raises dopamine levels to a range that makes self-regulation feel more accessible.',                          '💊', 'treatment'),
('fact_018', 'fact', 'Many people with ADHD experience ''task paralysis'' — the inability to start a task despite wanting to. It''s not procrastination; it''s a neurological barrier.', '🧱', 'symptoms'),
('fact_019', 'fact', 'ADHD brains are often described as having a ''Ferrari engine with bicycle brakes.'' Tons of power — regulation is the challenge.',                             '🏎️', 'brain_science'),
('fact_020', 'fact', 'Emotional dysregulation — big feelings that hit fast and hard — is one of the most impairing but least-discussed aspects of ADHD.',                           '🌊', 'emotional'),
('fact_021', 'fact', 'ADHD does NOT mean you can''t focus. It means your brain regulates attention differently — too much in some areas, too little in others.',                    '🔭', 'myths'),
('fact_022', 'fact', 'Working memory — holding information ''in mind'' while using it — is often impaired in ADHD. That''s why you walked into a room and forgot why.',             '📦', 'symptoms'),
('fact_023', 'fact', 'Physical movement helps ADHD brains regulate. Fidgeting, pacing, doodling — these often improve focus, not reduce it.',                                       '🤸', 'lifestyle'),
('fact_024', 'fact', 'ADHD is associated with higher rates of creativity and outside-the-box thinking across multiple studies. Your brain really does work differently.',            '🎨', 'strengths'),
('fact_025', 'fact', 'Sugar and diet don''t cause ADHD, but they can affect symptoms. Stable blood sugar helps with focus and emotional regulation.',                                '🥗', 'lifestyle')
ON CONFLICT (content_id) DO NOTHING;

-- Tips (from tips.json)
INSERT INTO content_items (content_id, type, text, emoji, topic) VALUES
('tip_001', 'tip', 'Try body doubling — work alongside someone (even silently on video call). The social presence activates accountability circuits in the ADHD brain.',             '👥', 'focus'),
('tip_002', 'tip', 'Use the 2-minute rule: if a task takes under 2 minutes, do it NOW. Don''t add it to a list. ADHD brains lose tasks in lists.',                                  '⚡', 'productivity'),
('tip_003', 'tip', 'Leave visual cues for yourself. Put the thing you need to remember ON TOP of your bag or in front of the door. Out of sight = out of mind is real.',            '👀', 'memory'),
('tip_004', 'tip', 'Keep a ''brain dump'' notebook. When a thought pops up mid-task, write it down fast and return to what you were doing. Don''t chase the thought.',              '📓', 'focus'),
('tip_005', 'tip', 'Set transition alarms, not just appointment alarms. ADHD makes switching tasks unexpectedly hard. Give yourself a 10-min warning before you need to change.',   '🔔', 'time_management'),
('tip_006', 'tip', 'Break tasks into the smallest possible step. ''Clean kitchen'' → ''put one dish in the sink.'' Starting is the hardest part for ADHD brains.',                 '🪜', 'productivity'),
('tip_007', 'tip', 'Try temptation bundling: only listen to your favorite podcast or playlist when doing a dreaded task. Pair boredom with something you love.',                    '🎧', 'motivation'),
('tip_008', 'tip', 'Pair medication with an existing habit (like morning coffee) so you never forget it. Habit stacking works really well for ADHD brains.',                        '☕', 'medication'),
('tip_009', 'tip', 'If you''re stuck in task paralysis, set a timer for 5 minutes and just START. You don''t have to finish — just start. The momentum usually kicks in.',          '⏱️', 'focus'),
('tip_010', 'tip', 'Keep duplicates of commonly lost items (keys, chargers, glasses, pens) in your most-visited spots. Remove the friction of losing things.',                      '🔑', 'organization'),
('tip_011', 'tip', 'Try the Pomodoro method: 25 min work, 5 min break. Timers give ADHD brains a deadline to race against — and deadlines are dopamine.',                          '🍅', 'productivity'),
('tip_012', 'tip', 'Use a whiteboard in a visible spot for your 1-3 must-do tasks today. Physical, visible, erasable. Much better than a long digital to-do list.',                '📋', 'organization'),
('tip_013', 'tip', 'Move your body before a hard task. Even 10 minutes of walking boosts dopamine and makes focus significantly easier for ADHD brains.',                           '🚶', 'lifestyle'),
('tip_014', 'tip', 'If you always forget something before leaving the house, create a ''launch pad'' — one spot by the door for everything you need tomorrow.',                     '🚪', 'organization'),
('tip_015', 'tip', 'Tell someone your goal out loud. Social accountability is one of the most effective ADHD focus hacks. Even a text to a friend counts.',                         '💬', 'accountability'),
('tip_016', 'tip', 'Try ''time blocking'' on your calendar. Schedule specific tasks in time slots — not just meetings. ADHD brains do better with structure that''s visible.',      '📅', 'time_management'),
('tip_017', 'tip', 'Wear noise-cancelling headphones even with nothing playing. They signal to your brain (and others): ''I am in focus mode now.''',                               '🎶', 'focus'),
('tip_018', 'tip', 'Batch similar tasks together. Reply to all emails at once. Make all phone calls in one block. Task-switching is expensive for ADHD brains.',                    '📦', 'productivity'),
('tip_019', 'tip', 'Add ''buffer time'' everywhere. ADHD brains consistently underestimate how long things take. If you think it takes 20 min, plan for 40.',                       '🕐', 'time_management'),
('tip_020', 'tip', 'Don''t rely on memory — externalize everything. Sticky notes, phone reminders, voice memos. Your brain was not designed to be your to-do list.',               '📱', 'memory'),
('tip_021', 'tip', 'When you catch yourself doomscrolling, don''t shame yourself — ask ''what am I avoiding?'' Then do just 2 minutes of that task.',                              '📲', 'self_compassion'),
('tip_022', 'tip', 'Create routines that require zero decisions. Same breakfast, same morning order, same route. Decision fatigue hits ADHD brains extra hard.',                    '🔄', 'organization'),
('tip_023', 'tip', 'Use a visual timer (like a Time Timer) instead of a digital clock. Seeing time disappear is more compelling to ADHD brains than reading numbers.',             '🟠', 'time_management'),
('tip_024', 'tip', 'Celebrate small wins out loud. Completing a task feels good, but verbalizing it — ''I did the thing!'' — reinforces the dopamine hit and builds momentum.',    '🎉', 'motivation'),
('tip_025', 'tip', 'Be honest with people about your ADHD when it matters. Asking for deadlines, check-ins, or written instructions isn''t weakness — it''s smart self-management.', '🤝', 'self_advocacy')
ON CONFLICT (content_id) DO NOTHING;

-- Reply templates (from replies.json)
INSERT INTO reply_templates (intent, text) VALUES
('question', 'Great question! 🧠 Every ADHD brain is different, but one thing that helps a lot of people: start with the SMALLEST possible step. Like, embarrassingly small. That gets the engine going. What specifically are you struggling with?'),
('question', 'Oh yes, we feel this. ✨ Body doubling is underrated — try working alongside someone (even on a silent video call). The social presence activates focus for a lot of ADHD brains!'),
('question', 'This is such a common ADHD challenge! Try externalizing it — get it OUT of your head and onto paper, a whiteboard, or a voice memo. Your brain isn''t a storage system. 💡'),
('question', 'The struggle is real and SO valid. 💙 One thing: pair the dreaded task with something you love. Only listen to your fave playlist while doing it. Temptation bundling = ADHD magic.'),
('question', 'YES. Time blindness hits hard. Try a visual timer (like Time Timer app) — seeing time shrink is more real to ADHD brains than watching a clock. ⏳'),
('question', 'For focus, try the Pomodoro method: 25 min on, 5 min off. The deadline feeling creates dopamine. 🍅 What kind of task are you working on?'),
('question', '💙 First: you''re not broken, your brain just needs different scaffolding. Have you tried breaking the task into the TINIEST possible first step? Not ''do the report'' — ''open the doc.'' That''s it.'),
('positive',  'This made our day! 🚀 Keep going — your ADHD brain is doing amazing things.'),
('positive',  'Love hearing this! ✨ You''re proof that ADHD brains are capable of incredible things when they have the right tools.'),
('positive',  'Thank YOU for being here! 💙 The ADHD community is full of brilliant, creative, resilient people — and you''re one of them.'),
('positive',  'YES! 🎉 This is exactly the kind of win we love to hear. Celebrate it — seriously, out loud. The dopamine hit from celebrating builds momentum!'),
('positive',  'That genuinely means so much! 🧠 Sharing what works is how we all get better at this. Keep thriving!'),
('general',   'Hey! 👋 Thanks for reaching out. The ADHD community here is full of people who get it. What''s on your mind?'),
('general',   '🧠 We see you! ADHD life is wild but you''re not alone in it. Anything we can help with?'),
('general',   'Hi! ✨ Always glad to connect with the ADHD community. What''s going on?'),
('general',   'Hey there! 💙 ADHD is a lot — but so are you. Drop us a question anytime, we''re here for it.'),
('general',   'Thanks for the reply! 🚀 We''re all figuring out our ADHD brains together. What''s on your mind?')
ON CONFLICT DO NOTHING;

-- Follow search queries (from follow_targets.json["search_queries"])
INSERT INTO configured_queries (query, purpose) VALUES
('#ADHD adults',          'follow'),
('#ADHDTips',             'follow'),
('#ADHDAdults',           'follow'),
('#Neurodiversity ADHD',  'follow'),
('ADHD coach tips',       'follow'),
('ADHD executive function','follow'),
('ADHD productivity',     'follow'),
('adult ADHD diagnosis',  'follow'),
('#ADHDAwareness',        'follow'),
('ADHD brain science',    'follow')
ON CONFLICT (query, purpose) DO NOTHING;

-- Research keyword queries (from research_agent plan)
INSERT INTO configured_queries (query, purpose) VALUES
('ADHD time blindness',   'research_keyword'),
('ADHD body doubling',    'research_keyword'),
('ADHD dopamine',         'research_keyword'),
('ADHD rejection sensitive dysphoria', 'research_keyword'),
('ADHD task paralysis',   'research_keyword')
ON CONFLICT (query, purpose) DO NOTHING;

-- Research hashtags (from research_agent plan)
INSERT INTO configured_queries (query, purpose) VALUES
('#ADHD',             'research_hashtag'),
('#ADHDAdults',       'research_hashtag'),
('#ADHDTips',         'research_hashtag'),
('#Neurodiversity',   'research_hashtag'),
('#ADHDAwareness',    'research_hashtag')
ON CONFLICT (query, purpose) DO NOTHING;

-- Seed accounts — follow targets and research key people (all four serve both purposes)
INSERT INTO configured_accounts (username, is_follow_seed, is_research) VALUES
('ADHDreWired', TRUE, TRUE),
('HowToADHD',   TRUE, TRUE),
('drhallowell', TRUE, TRUE),
('ADHDCoaches', TRUE, TRUE)
ON CONFLICT (username) DO NOTHING;
