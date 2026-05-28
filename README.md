# Intizom AI

**An AI-powered discipline operating system for Gen Z students.**

A Telegram bot + Mini App that turns goals into habits via XP,
streaks, daily quests, and an emotional AI coach.

---

## What's inside

### Bot (aiogram 3)
- Voice + text plan extraction (Whisper + GPT-4o-mini)
- Natural-language time parsing (uz/ru/en/tr → uz)
- Per-minute reminders, daily summary, evening reflection,
  morning nudge, streak warning, comeback ping
- Admin panel with user/admin management + broadcast

### Mini App (FastAPI + vanilla JS SPA)
- Discipline ring, XP / level bar, rank chip
- Daily Quest card with progress
- Real AI Coach page — mood, energy, intent, evening reflection
- Smart insights based on the user's last 30 days
- Calendar, weekly diary, monthly grid for goals
- Statistics: trend chart, heatmap, donut, achievements
- 6 themes + dark mode
- Achievement unlock modal with confetti
- 3-step first-run onboarding

### Gamification engine
- XP curve `50 × (n−1) × n` — fast early, earned later
- 30-day discipline score (0-100) — completion + streak +
  intensity + inactivity penalty
- Streak with grace day & freeze tokens
- Persistent achievement unlocks (15 badges, 4 rarities)
- Auto-rank: Boshlovchi → Legend → Mythic

### API surface (`/api/webapp/...`)
- `GET /plans?date_from=&date_to=` · CRUD for plans
- `GET /goals` · CRUD for goals
- `GET /stats` · full gamification snapshot
- `GET /coach` · contextual coach message
- `GET /quest` · daily mission with progress
- `GET|POST /checkin` · mood / energy / intent / reflection

---

## Layout

```
bot/
  handlers/      aiogram routers (start, plan, callback, report, status, admin)
  keyboards/     reusable inline + reply keyboards
  models/        SQLAlchemy: User, Plan, ScoreLog, Admin, Goal, Achievement, DailyCheckin
  services/      gamification, coach, score, plan, goal, scheduler, ai, user, admin
  utils/         formatters
  main.py        bot bootstrap
database/
  db.py          engine + idempotent migrations
webapp/
  app.py         FastAPI app + bot lifespan
  routes/        plans, goals, stats
  static/        index.html (single-file SPA)
start.py         single-process entry running both bot + server
```

---

## Run locally

```bash
pip install -r requirements.txt
# .env: BOT_TOKEN, OPENAI_API_KEY, DB_*, ADMIN_ID
# optional: WEBAPP_URL=https://<your-public-https>/
python start.py
```

## Deploy (Railway)

`railway.json` and `Procfile` boot `uvicorn webapp.app:app`. The
FastAPI lifespan starts the bot in the same process. Migrations
run automatically on startup via `_run_migrations()`.
