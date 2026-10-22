# Soldier Management System (ប្រព័ន្ធគ្រប់គ្រងយោធិន)

Office of Appointment, Transfer and Rank Promotion. Backend: Python (FastAPI); frontend: Vue 3 (Element Plus); database: MySQL `soldier-management`.
See `plan.txt` for the full design.

## Run locally (development)

Requirements: Python 3.12+, Node 20+, MySQL 8+ with an empty database named `soldier-management`.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL and a random SECRET_KEY
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
Migrations and the seed must have been run first.

## Production (Docker)

```bash
# .env next to docker-compose.yml
MYSQL_ROOT_PASSWORD=...
SECRET_KEY=...
docker compose up -d --build
docker compose exec api python -m scripts.import_geo --source-dir /data/source
docker compose exec api python -m scripts.seed --source-dir /data/source --admin-password '<strong password>'
```

Back up the `db_data` volume (mysqldump) and the `storage` volume (photos and attachments) every day.

## Project layout

```
backend/
  app/core        config, database, JWT security, permission dependencies
  app/models      SQLAlchemy models (geo, org, soldier, document, decision, records, user)
  app/schemas     Pydantic input schemas
  app/api/crud.py generic list/get/create/update/delete router
  app/api/v1      system (auth/users/roles/settings/audit), master data, soldiers,
                  documents, decisions, records (training/discipline/awards/retirement/separation/strength), reports
  app/services    shared helpers, soldier computations (age, service length, history)
  alembic/        migrations
  scripts/        import_geo.py, seed.py, sql_dump.py (reads the .sql dumps without executing them)
  tests/          end-to-end API tests
frontend/src/
  layouts/MainLayout.vue   sidebar menu (menu.js) + header
  components/              CrudPage (config-driven list+form), UnitTreeSelect, SoldierSelect, VillageSelect, ...
  crud-configs.js          columns and fields for the simple modules
  views/                   dashboard, org, soldiers, decisions, training, reports, settings, print pages
```

## Important notes

- Soldier Excel import / comparison: download the template from **ការងារបញ្ចូលក្របខ័ណ្ឌយោធិនអាជីព**. The list export uses the same columns, so an exported file can be compared or imported again.
- `member_db.sql` contains real citizen personal data. Only its `countries` and `jobs` lists are imported. Keep it out of git (it is already in `.gitignore`).
- The **rank list is a draft**. Check names, order and "minimum years to next rank" under រចនាសម្ព័ន្ធក្របខណ្ឌ → ឋានន្តរស័ក្តិ.
- Retirement ages (default 60 for men, 55 for women) and the outgoing document number format can be changed under ការកំណត់ → ការកំណត់ប្រព័ន្ធ.
