# Soldier Management System (ប្រព័ន្ធគ្រប់គ្រងយោធិន)

Office of Appointment, Transfer and Rank Promotion. Backend: Python (FastAPI); frontend: Vue 3 (Element Plus); database: MySQL `soldier-management`
(PostgreSQL also works: `DATABASE_URL=postgresql+psycopg://user:password@host:5432/soldier-management`).
See `plan.txt` for the full design.

## Run locally (development)

Requirements: Python 3.12+, Node 20+, MySQL 8+ (or PostgreSQL 14+) with an empty database named `soldier-management`.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # runtime + test/lint tools
cp .env.example .env            # set DATABASE_URL and SECRET_KEY (see below)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste the output as SECRET_KEY in .env
.venv/bin/alembic upgrade head  # create tables
.venv/bin/python -m scripts.import_geo   # 25 provinces / 205 districts / 1683 communes / 14760 villages + countries
.venv/bin/python -m scripts.seed         # roles, permissions, admin user, ranks, positions, specialties, lookup lists
.venv/bin/python -m scripts.seed_demo    # optional: fictional demo data (units, ~175 soldiers, decisions, documents...)
.venv/bin/uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api to :8000)
```

The API refuses to start when `SECRET_KEY` is missing, a template placeholder or shorter than 16 characters:
anyone who knows the key can forge login tokens.

Default login: `admin` / `Admin@123`. Change it right away under **ប្ដូរពាក្យសម្ងាត់**.
With the demo data loaded there are also `officer`, `approver`, `viewer` and `guard.officer` (scoped to បញ្ជាការដ្ឋានកងការពារ), all with password `Demo@123`.
For the decision approval workflow there is one demo user per role: `assistant` (ជំនួយការ — enters and submits),
`deputy.office` (នាយរងការិយាល័យ), `chief.office` (នាយការិយាល័យ), `deputy.director` (នាយករង) and `director` (នាយក — final approval).
The demo seed only runs on a system with no units or soldiers; never load it into production.
API docs: http://localhost:8000/api/docs

## Tests

```bash
cd backend && .venv/bin/pytest
```

The tests run against the configured database inside one transaction that is rolled back, so they leave no data behind.
Migrations, `import_geo` and the seed must have been run first. `requirements-dev.txt` adds pytest, httpx and ruff;
the Docker image installs only `requirements.txt`.

## Production (Docker)

```bash
cp .env.example .env            # next to docker-compose.yml: set MYSQL_ROOT_PASSWORD, SECRET_KEY, CORS_ORIGINS, WEB_PORT
docker compose up -d --build
docker compose exec api python -m scripts.import_geo --source-dir /data/source
docker compose exec api python -m scripts.seed --source-dir /data/source --admin-password '<strong password>'
```

### Backups

The `backup` service copies the database (`backups/db/sm-YYYY-MM-DD_HHMM.sql.gz`, the last `BACKUP_KEEP_DAYS` days)
and the uploaded files (`backups/storage/`) every day at `BACKUP_TIME` (see `.env.example`), and once at start when
there is no copy of the day yet. Copy the `backups` folder to another disk or machine regularly.

```bash
docker compose run --rm backup now           # one backup now
docker compose logs backup                   # what the last backups did
# restore a database copy (replaces the current data):
gunzip < backups/db/sm-2026-11-09_0100.sql.gz | docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" soldier-management'
```

### Large data (hundreds of thousands of soldiers)

- Dashboard figures are counted in the background and kept for `dashboard_refresh_minutes` (system settings).
- Soldier and report Excel files are made in the background and downloaded when ready (kept 24 hours).
- The activity log is trimmed to `audit_retention_years` (system settings; 0 = keep everything) every hour.
- Give MySQL memory: add `--innodb-buffer-pool-size=6G` (about half the machine's RAM) to the `db` command.

## Project layout

```
backend/
  app/core        config, database, JWT security, permission dependencies
  app/models      SQLAlchemy models (geo, org, soldier, document, decision, records, user)
  app/schemas     Pydantic input schemas
  app/api/crud.py generic list/get/create/update/delete router
  app/api/v1      system (auth/users/roles/settings/audit), master data, soldiers,
                  documents, decisions, records (training/discipline/awards/retirement/separation/strength), reports
  app/services    shared helpers, soldier computations (age, service length, history), staffing, military ID cards
  alembic/        migrations
  scripts/        import_geo.py, seed.py, sql_dump.py (reads the .sql dumps without executing them)
  tests/          end-to-end API tests
frontend/src/
  layouts/MainLayout.vue   sidebar menu (menu.js) + header
  components/              CrudPage (config-driven list+form), UnitTreeSelect, SoldierSelect, VillageSelect, ...
  crud-configs.js          columns and fields for the simple modules
  about-content.js         user guide and change history shown on អំពីយើង
  views/                   dashboard, org, soldiers, decisions, training, id cards, retirement, policy, reports,
                           settings, print pages
```

## Important notes

- After pulling an update, run `alembic upgrade head` and then `python -m scripts.seed` again: the seed only adds what is
  missing, and gives permissions of new modules (e.g. ការងារអត្តសញ្ញាណប័ណ្ណយោធិន) to the roles that should have them.
- Every list can save its filter (Filter ដែលបានរក្សាទុក, own or shared) and export exactly what is filtered to Excel or
  print it / save it as PDF. Filtered lists keep their filter in the URL, so a link opens the same list.
- Soldier Excel import / comparison: download the template from **ការងារបញ្ចូលក្របខ័ណ្ឌយោធិនអាជីព**. The list export uses the same columns, so an exported file can be compared or imported again.
- `member_db.sql` contains real citizen personal data. Only its `countries` and `jobs` lists are imported. Keep it out of git (it is already in `.gitignore`).
- The **rank list is a draft**. Check names, order and "minimum years to next rank" under រចនាសម្ព័ន្ធក្របខណ្ឌ → ឋានន្តរស័ក្តិ.
- Retirement ages (default 60 for men, 55 for women) and the outgoing document number format can be changed under ការកំណត់ → ការកំណត់ប្រព័ន្ធ.
- The contact details and the link to a full user manual shown on **អំពីយើង** are set under ការកំណត់ → ការកំណត់ប្រព័ន្ធ.
  With every release, add an entry to `frontend/src/about-content.js` (ប្រវត្តិកែប្រែ) and bump the version in
  `frontend/package.json` and `backend/app/main.py`.
- Military ID cards: when a new card replaces an old one, set the old card to **ជំនួស**, otherwise it still counts as the
  soldier's current card (and may show up as ត្រូវធ្វើប័ណ្ណថ្មី).
