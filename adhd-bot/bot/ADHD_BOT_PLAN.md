# 🧠 ADHD Daily Bot — Project Plan

> A Twitter/X bot that posts upbeat, motivational ADHD facts and tips for adults, engages with replies, and grows its community by following relevant accounts.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Bot Persona](#bot-persona)
3. [Twitter/X API Setup](#twitterx-api-setup)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Architecture](#architecture)
7. [Feature Breakdown](#feature-breakdown)
8. [Content Strategy](#content-strategy)
9. [ADHD Tips & Facts Library](#adhd-tips--facts-library)
10. [Deployment Options](#deployment-options)
11. [Safety & Rate Limits](#safety--rate-limits)
12. [Roadmap](#roadmap)

---

## Project Overview

**Bot Handle (suggested):** `@ADHDBrainBoost` or `@FocusFuelBot`

**Mission:** Deliver daily, research-backed ADHD tips and facts to adults with ADHD. The bot maintains an upbeat, encouraging voice, responds to replies with helpful information, and actively builds a community by following relevant accounts.

**Posting Schedule:** 2–3 times per day (morning, afternoon, evening)

**Target Audience:** Adults with ADHD, caregivers, mental health advocates, productivity enthusiasts

---

## Bot Persona

### Name: **Boost** 🚀

**Full character brief:**

> Boost is your ADHD-positive hype buddy. They get it — the hyperfocus spirals, the forgotten keys, the 3am productivity bursts. Boost doesn't lecture; they celebrate the ADHD brain and arm you with real tools that actually work. Every post is punchy, warm, and leaves you feeling like your brain is a feature, not a bug.

### Voice & Tone

| Attribute | Description |
|---|---|
| **Energy** | High but not exhausting — like a good friend who's excited for you |
| **Empathy** | Acknowledges struggle without wallowing in it |
| **Language** | Plain, punchy, emoji-friendly. No jargon. |
| **Humor** | Light and relatable — "oh you too??" energy |
| **Authority** | References science casually, never lectures |

### Persona Rules

- Always affirm the ADHD brain as different, not broken
- Keep posts under 240 characters when possible (leaves room for engagement)
- Use "you" and "we" — community-first language
- Never shame or use negative framing
- Emoji use: yes, but purposefully (1–3 max per post)

### Sample Voice

> ✨ Reminder: "Executive dysfunction" isn't laziness — your brain's task-starting circuits work differently. Try the 2-minute rule: if it takes under 2 min, do it NOW. Works like magic for ADHD brains.

> 🧠 Fun fact: People with ADHD often have *more* creative connections between brain regions. That "random" idea you just had? Probably brilliant.

> You forgot something again? Same. Try leaving visual cues: put the thing you need to remember ON TOP of your bag. Out of sight = out of mind is real for ADHD brains. 👜

---

## Twitter/X API Setup

### Step 1: Create a Developer Account

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Sign in with the Twitter account you want the bot to use (or create a new one)
3. Apply for a **Free** or **Basic** developer tier
   - Free tier: Read-only + 1,500 tweets/month write access
   - Basic tier ($100/mo): Higher write limits — recommended for this bot
4. Fill out the use-case form — be honest: "automated educational content about ADHD for public benefit"

### Step 2: Create a Project & App

1. In the developer portal, create a new **Project**
2. Inside it, create an **App**
3. Under **App Settings → User authentication settings**:
   - Enable **OAuth 1.0a**
   - Set permissions to **Read and Write**
   - Set App type to **Automated Bot or App**
   - Add a callback URL (use `http://localhost` for now)

### Step 3: Get Your Keys

From the **Keys and Tokens** tab, copy:

```
API_KEY=
API_KEY_SECRET=
ACCESS_TOKEN=
ACCESS_TOKEN_SECRET=
BEARER_TOKEN=
```

Store these in a `.env` file — **never commit this file to git.**

### Step 4: Verify Access Level

Run the included `test_auth.py` script to confirm everything works before building further.

---

## Tech Stack

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Best Tweepy support, easy scheduling |
| Twitter Library | `tweepy` | Most mature Python Twitter library |
| Scheduling | `APScheduler` | Flexible in-process scheduling |
| Database | `SQLite` (via `sqlite3`) | Lightweight, no server needed, tracks posted content |
| Config | `python-dotenv` | Secure key management |
| Logging | `loguru` | Clean, simple logging |
| Testing | `pytest` | Standard Python testing |

### Dependencies

```
tweepy>=4.14.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
loguru>=0.7.0
pytest>=7.4.0
```

---

## Project Structure

```
adhd-bot/
│
├── .env                        # API keys (DO NOT COMMIT)
├── .env.example                # Template for .env
├── .gitignore
├── README.md
├── requirements.txt
│
├── bot/
│   ├── __init__.py
│   ├── main.py                 # Entry point — starts scheduler
│   ├── auth.py                 # Twitter API authentication
│   ├── poster.py               # Handles posting tweets
│   ├── listener.py             # Watches for replies/mentions
│   ├── responder.py            # Generates and sends replies
│   ├── follower.py             # Finds and follows relevant accounts
│   └── scheduler.py            # APScheduler setup and job definitions
│
├── content/
│   ├── facts.json              # ADHD facts library
│   ├── tips.json               # ADHD tips library
│   ├── replies.json            # Canned reply templates
│   └── follow_targets.json     # Search terms / accounts to follow
│
├── data/
│   └── bot.db                  # SQLite database (auto-created)
│
├── scripts/
│   ├── test_auth.py            # Verify API keys work
│   ├── seed_db.py              # Initialize database
│   └── generate_content.py     # Helper to add new content
│
└── logs/
    └── bot.log                 # Runtime logs
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                   main.py                    │
│            (Entry point + scheduler)         │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       │   scheduler.py  │
       │  APScheduler    │
       └───┬─────┬───┬──┘
           │     │   │
    ┌──────┘  ┌──┘  └──────────┐
    ▼         ▼                ▼
poster.py  listener.py    follower.py
    │         │                │
    │    responder.py          │
    │         │                │
    └────┬────┘                │
         ▼                     ▼
      auth.py ──────────── Twitter API
         │
      data/bot.db (SQLite)
         │
      content/*.json
```

### Data Flow

1. **Scheduler** triggers jobs on a timed basis
2. **Poster** pulls an unposted item from `facts.json` / `tips.json`, posts it, marks it as posted in SQLite
3. **Listener** polls for mentions/replies every 15 minutes
4. **Responder** receives a mention, classifies it (question / thanks / general), selects or generates a reply
5. **Follower** runs once daily, searches for accounts by keyword, follows those not yet followed

---

## Feature Breakdown

### 1. Daily Posting (`poster.py`)

- Reads from `content/facts.json` and `content/tips.json`
- Randomly selects an unposted item
- Posts at scheduled times (e.g. 8am, 1pm, 7pm)
- Marks item as posted in SQLite with timestamp
- Cycles back to allow repeats after all content is exhausted
- Rotates between facts and tips (alternates categories)

### 2. Reply Listener (`listener.py` + `responder.py`)

- Polls the Twitter API for mentions every 15 minutes
- Stores seen mention IDs to avoid double-responding
- Classifies replies into categories:
  - **Question** → responds with relevant tip or resource
  - **Thanks / Positive** → sends an encouraging reply
  - **General** → sends a warm, generic Boost reply
- Reply templates stored in `content/replies.json`
- AI-powered replies optional (Claude API integration stub included)

### 3. Account Follower (`follower.py`)

- Runs once per day
- Searches Twitter for accounts using keywords:
  - `#ADHD`, `#ADHDAdults`, `#NeurodiversityAwareness`
  - `ADHD coach`, `ADHD therapist`, `neurodiversity`
- Filters: English language, >100 followers, not already followed
- Follows up to 20 new accounts per day (rate limit safe)
- Logs all follows to SQLite

### 4. Database Tracking (`data/bot.db`)

Tables:
- `posted_content` — tracks what's been posted and when
- `mentions_seen` — prevents duplicate replies
- `followed_accounts` — log of all follows with timestamps

---

## Content Strategy

### Posting Schedule

| Time | Content Type |
|---|---|
| 8:00 AM | 🌅 Morning tip — actionable, start-your-day energy |
| 1:00 PM | 🧠 ADHD fact — science-y but fun |
| 7:00 PM | 💬 Evening reflection or reminder |

### Content Categories

- **Brain Science** — how the ADHD brain actually works
- **Daily Strategies** — practical tools and techniques
- **Emotional Support** — validation and reframing
- **Productivity Hacks** — ADHD-specific approaches
- **Myth Busting** — correcting common misconceptions
- **Wins & Celebration** — celebrating ADHD strengths

### Hashtag Strategy

Each post ends with 1–3 relevant hashtags:
`#ADHD` `#ADHDAdults` `#Neurodiversity` `#MentalHealth` `#BrainHealth` `#ADHDTips`

---

## ADHD Tips & Facts Library

*(Initial seed — 50 items, to be expanded)*

### Facts

1. ADHD affects approximately 4–5% of adults worldwide — you are far from alone.
2. The ADHD brain has lower baseline levels of dopamine, making novelty and rewards feel essential, not optional.
3. ADHD is highly heritable — if you have it, there's a ~75% chance a close family member does too.
4. Many adults with ADHD weren't diagnosed as children, especially women and girls.
5. Time blindness — difficulty sensing time passing — is one of the most common but least-discussed ADHD symptoms.
6. Hyperfocus is a real ADHD trait: when interest is high, ADHD brains can sustain intense, deep concentration.
7. ADHD brains often have a smaller prefrontal cortex — the area responsible for planning and impulse control.
8. Sleep problems affect up to 80% of people with ADHD, often due to a delayed circadian rhythm.
9. ADHD and anxiety frequently co-occur — roughly 50% of adults with ADHD also have an anxiety disorder.
10. Exercise increases dopamine and norepinephrine — two neurotransmitters that are key for ADHD regulation.

### Tips

1. Use body doubling — work alongside another person (even on video call) to improve focus and follow-through.
2. Try the Pomodoro technique: 25 minutes of work, 5-minute break. Timers give ADHD brains a deadline to work with.
3. Put visual cues where you need them — if it's out of sight, it's out of mind for ADHD brains.
4. Keep a "brain dump" notebook or app for capturing thoughts before they vanish.
5. Set alarms for transitions, not just appointments — ADHD makes switching tasks unexpectedly hard.
6. Break tasks into the smallest possible steps. "Clean kitchen" becomes "put one dish in the sink."
7. Use temptation bundling: only listen to your favorite podcast while doing a dreaded task.
8. Medication reminders work best when paired with an existing habit — take them with your morning coffee.
9. If you're procrastinating, set a 2-minute timer and just start — starting is the hardest part.
10. Keep duplicates of commonly lost items (keys, chargers, glasses) in your most-visited spots.

---

## Deployment Options

### Option A: Local Machine (Simple Start)
- Run with `python bot/main.py`
- Use a process manager like `pm2` or `supervisord` to keep it alive
- Best for: testing, low-cost start

### Option B: Railway (Recommended Cloud)
- Free tier available, easy Python deploys
- Add environment variables in the Railway dashboard
- Connect GitHub repo for auto-deploy
- URL: [railway.app](https://railway.app)

### Option C: Render
- Free tier with limitations (spins down after inactivity)
- Good for low-frequency bots
- URL: [render.com](https://render.com)

### Option D: VPS (DigitalOcean / Hetzner)
- Most control, ~$5/month
- Run with `systemd` service or Docker

---

## Safety & Rate Limits

### Twitter API Rate Limits (Free/Basic Tier)

| Action | Limit |
|---|---|
| Post tweets | 1,500/month (Free), 3,000/month (Basic) |
| Read mentions | 1 request per 15 min |
| Follow accounts | 400/day max (Twitter ToS) |
| Search users | Limited — space queries out |

### Bot Safety Rules (Built In)

- Never follow more than 20 accounts per day
- Never reply more than once to the same mention
- Store all actions in SQLite to prevent duplicates
- Respect a 5-second delay between API calls
- Log all errors — alert on repeated failures

### Twitter ToS Compliance

- Bot account must disclose it is automated (in bio)
- No spamming, no mass follows/unfollows cycles
- Content must not be misleading or harmful
- See: [Twitter Automation Rules](https://help.twitter.com/en/using-twitter/automated-account-rules)

---

## Roadmap

### Phase 1 — Foundation ✅ (Current)
- [ ] Project scaffold and documentation
- [ ] Twitter API setup guide
- [ ] Bot persona defined
- [ ] Initial content library (50 items)
- [ ] Core modules: poster, listener, responder, follower

### Phase 2 — Launch
- [ ] SQLite database seeded and tested
- [ ] All scheduler jobs running locally
- [ ] Auth tested with real API keys
- [ ] 10 test posts verified
- [ ] Deploy to Railway or chosen host

### Phase 3 — Growth
- [ ] Expand content library to 200+ items
- [ ] Add Claude API for dynamic reply generation
- [ ] Weekly analytics digest (follower growth, engagement)
- [ ] Monthly content themes (e.g., ADHD Awareness Month in October)

### Phase 4 — Community
- [ ] Retweet relevant community posts
- [ ] Weekly polls (e.g., "What's your biggest ADHD challenge?")
- [ ] Pin a weekly "tip of the week" thread

---

*Last updated: May 2026 | Status: In Development*
