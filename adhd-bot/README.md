# 🚀 ADHD Bot — Boost

> An upbeat, motivational Twitter/X bot that posts daily ADHD tips and facts for adults, replies to mentions, and builds community.

---

## Quick Start

### 1. Clone & Install

```bash
git clone <your-repo>
cd adhd-bot
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env with your Twitter API keys
```

See `ADHD_BOT_PLAN.md` for full Twitter API setup instructions.

### 3. Initialize Database

```bash
python scripts/seed_db.py
```

### 4. Test Authentication

```bash
python scripts/test_auth.py
```

### 5. Run the Bot

```bash
python -m bot.main
```

---

## Project Structure

```
adhd-bot/
├── bot/            # Core modules
├── content/        # ADHD tips, facts, replies (JSON)
├── data/           # SQLite database (auto-created)
├── scripts/        # Utility scripts
└── logs/           # Runtime logs
```

---

## Features

- **📅 Scheduled posting** — 2-3 ADHD tips/facts per day
- **💬 Mention replies** — Polls every 15 min, replies in Boost's upbeat voice
- **👥 Community building** — Follows relevant ADHD accounts daily
- **📊 SQLite tracking** — Prevents duplicate posts and replies

---

## Bot Persona: Boost 🚀

Boost is your ADHD-positive hype buddy — upbeat, evidence-informed, and always in your corner. See `ADHD_BOT_PLAN.md` for the full persona brief.

---

## Documentation

See `ADHD_BOT_PLAN.md` for the full project plan, architecture, content strategy, and deployment options.
