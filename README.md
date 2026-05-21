# Macro Tracker

A personal nutrition and fitness tracking app with a FastAPI backend, SQLite database, and a browser-based frontend.

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server**
   ```bash
   python app.py
   ```

3. **Open in browser**
   ```
   http://localhost:8001
   ```

The SQLite database (`macro.db`) is created automatically on first run.

---

## Features

- **Food log** — log meals by ingredient or recipe, organized by meal type (breakfast, lunch, dinner, snack)
- **Ingredient library** — build a searchable database of ingredients with full macro breakdowns
- **Recipes** — combine ingredients into reusable recipes with per-serving nutrition
- **Macro targets** — set daily calorie, protein, carb, fat, and fiber goals and track progress
- **Body measurements** — log custom body metrics (weight, body fat, etc.) with trend charts
- **Workouts** — log workouts and exercises with duration and calories burned
- **Analytics** — daily macro summaries and trend charts over time
- **AI food lookup** — look up nutrition info for any food using Claude
- **AI analysis** — get a plain-English coaching insight based on your recent data

---

## AI features (optional)

Set your Anthropic API key before starting the server:

```bash
# Mac / Linux
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Then use **AI food lookup** to auto-fill nutrition data for ingredients, or **AI analyze** in the analytics tab for a personalized summary.

---

## API

Auto-generated docs are at `http://localhost:8001/api/docs` when the server is running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/ingredients` | List or create ingredients |
| PUT/DELETE | `/api/ingredients/{id}` | Update or delete an ingredient |
| GET/POST | `/api/recipes` | List or create recipes |
| POST/PUT/DELETE | `/api/recipes/{id}/components` | Manage recipe ingredients |
| GET/POST/DELETE | `/api/log` | Food log entries |
| GET/POST | `/api/targets` | Macro targets |
| GET/POST | `/api/body/config` | Body measurement fields |
| GET/POST | `/api/body/measurements` | Body measurement entries |
| GET/POST | `/api/workouts` | Workout log |
| GET | `/api/analytics/daily` | Daily macro summary |
| GET | `/api/analytics/macro-trends` | Macro trends over time |
| GET | `/api/analytics/body-trends` | Body measurement trends |
| POST | `/api/ai/food-lookup` | AI nutrition lookup |
| POST | `/api/ai/analyze` | AI coaching insight |

---

## Project structure

```
macro-tracker/
├── app.py          ← FastAPI backend, all routes, DB setup
├── seed.py         ← Optional: seed the DB with sample data
├── macro.db        ← SQLite database (auto-created, git-ignored)
├── requirements.txt
├── README.md
└── static/
    └── index.html  ← Full frontend (HTML + JS, talks to API)
```
