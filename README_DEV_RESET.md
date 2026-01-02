# SEOSuite (Local Dev) - Phase 2 Modular + Fresh SQLite

This ZIP is prepared for local development with a clean database reset.

## What changed
- Models moved out of `core` into real module apps:
  - `geo`: Country, Language
  - `projects`: Client, Project, Keyword, ProjectCompetitor
  - `serp`: SerpRun, SerpResult, SerpFeature, SerpKeywordSnapshot
  - `planner`: KeywordIdeaRun, KeywordIdea
- Views/services/templates split by module apps:
  - `projects` (keywords)
  - `serp` (runs, rankings, actions)
  - `planner` (keyword planner)
- `integrations` includes `DataForSEOClient` (moved from core) at `integrations/dataforseo/client.py`
- Database file removed (`db.sqlite3`) and all old migrations removed so you can generate clean migrations.

## First run (SQLite)
From the project root:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Notes
- Environment variables:
  - Copy `.env.example` to `.env` and fill API keys as needed.
- If you want a seed command, tell me and I will add `jobs/management/commands/seed_dev.py`.
