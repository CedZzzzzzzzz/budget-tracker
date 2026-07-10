# Changelog

All notable changes to Budget Tracker are documented in this file.

## [0.1.10] - 2026-07-11

### Summary

Major UI refresh with a glassmorphism app shell, new budget setup and settings flows, spending insights charts, centralized category configuration, and a formal database migration system.

### Added

#### Frontend
- **App shell** (`frontend/src/components/AppLayout.jsx`) — glass sidebar, header, theme toggle, mobile drawer
- **Routes** — `/dashboard`, `/dashboard/monthly`, `/budget`, `/settings` via nested `AppLayout` routes
- **Budget Setup** (`frontend/src/pages/BudgetSetup.jsx`) — weekly category limits, recurring expenses, budget snapshot panel
- **Settings** (`frontend/src/pages/Settings.jsx`) — profile update and password change
- **Spending insights** (`frontend/src/components/BudgetCharts.jsx`)
  - Category donut chart with icon legend
  - Week-over-week allowance vs spent comparison
  - Daily spending line chart with purple glow styling
- **Category UI** — `CategoryIcon.jsx`, `CategoryBadge.jsx` with semantic SVG icons
- **Undo toast** (`frontend/src/components/UndoToast.jsx`) for reversible expense actions
- **Client utilities**
  - `frontend/src/utils/nav.js` — navigation config and page titles
  - `frontend/src/utils/budgetPatch.js` — optimistic dashboard/budget state patches
- **Styling** — glass component system, light/dark purple theme, budget snapshot and chart styles in `frontend/src/styles.css`

#### Backend
- **API modules**
  - `api/errors.py` — shared API error handler decorator
  - `api/pdf_report.py` — monthly PDF export (ReportLab)
- **New endpoints** (in `api/routes.py`)
  - `GET /api/budget-settings`, `PUT /api/category-limits`
  - `GET|POST /api/recurring-expenses`, `PUT|DELETE /api/recurring-expenses/<id>`
  - `GET /api/week-comparison`, `GET /api/week-detail`
  - `GET /api/export-csv`, `GET /api/export-monthly-pdf`
  - `GET|PUT /api/profile`, `POST /api/change-password`
- **Shared config** — `shared/categories.json` for categories, labels, icons, keywords, and priority (used by Python and Vite `@shared` alias)

#### Database
- **Migrations** (`migrations/`)
  - `001_initial.sql` — base schema
  - `003_indexes.sql` — performance indexes
  - `004_password_reset.sql` — password reset tokens
  - `005_features.sql` — category limits, recurring expenses, user category rules
  - `runner.py` — versioned migration runner with `schema_migrations` tracking
- **Money columns** — `NUMERIC(12,2)` for allowance, amounts, and category totals
- **Feature tables** — `category_budget_limits`, `recurring_expenses`, `recurring_expense_applications`, `user_category_rules`

### Changed

- **`frontend/src/pages/Dashboard.jsx`** — overview ring progress, editable allowance, spending insights, weekly summary, export actions
- **`frontend/src/App.jsx`** — route-based navigation under app shell
- **`frontend/src/api.js`** — CSRF-aware fetch helpers, PDF/CSV export support
- **`api/categorize.py`** + **`frontend/src/utils/categorize.js`** — read categories from shared JSON; user rule matching
- **`api/routes.py`** — refactored routes, dashboard payload, budget/recurring APIs, exports
- **`database.py`** — pooling options, money types, budget/recurring/category-rule queries
- **`api/email_service.py`** — Brevo SMTP/API transport selection and validation
- **`app.py`** — migration runner on startup, env validation
- **`frontend/vite.config.js`** — `@shared` alias and API proxy target via `VITE_API_PROXY_TARGET`
- **`static/js/script.js`** — legacy tracker script aligned with expanded categories

### Fixed

- **Per-day budget hint** — days remaining now includes today when calculating daily allowance
- **Hamburger menu** — hidden on laptop/desktop (`lg` breakpoint)
- **Daily chart alignment** — day labels aligned to data point x-positions
- **Email on Railway** — production can use Brevo API to avoid SMTP IP blocks (from prior patches, included in this release line)

### Files in this release

| Area | Path |
|------|------|
| Shared | `shared/categories.json` |
| Migrations | `migrations/*.sql`, `migrations/runner.py` |
| API | `api/routes.py`, `api/categorize.py`, `api/email_service.py`, `api/errors.py`, `api/pdf_report.py` |
| Core | `app.py`, `database.py` |
| Frontend pages | `Dashboard.jsx`, `BudgetSetup.jsx`, `Settings.jsx`, `App.jsx` |
| Frontend components | `AppLayout.jsx`, `BudgetCharts.jsx`, `CategoryIcon.jsx`, `CategoryBadge.jsx`, `UndoToast.jsx` |
| Frontend utils | `nav.js`, `budgetPatch.js`, `categorize.js`, `theme.js`, `api.js` |
| Styles / build | `styles.css`, `vite.config.js` |
| Legacy | `static/js/script.js` |

### Upgrade notes

1. Ensure `.env` is configured locally and in production; `.env` is gitignored.
2. Run the app once so `migrations/runner.py` applies pending migrations, or run migrations via your deploy entrypoint.
3. Rebuild the frontend: `cd frontend && npm run build`
4. New budget features require the `005_features` migration tables.

### Security

- No secrets are committed; credentials remain in `.env` only.
- CSRF protection on mutating API routes.
- Rate limits on password reset and change-password endpoints.
