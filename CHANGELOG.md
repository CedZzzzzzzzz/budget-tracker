# Changelog

All notable changes to Budget Tracker are documented in this file.

## [0.3.0] - 2026-07-23

### Added

- Added an account-support drawer with account metadata, authentication history,
  email-delivery history, session revocations, and administrative events.
- Added protected admin actions to resend verification emails, send password-reset
  emails, and force sign-out normal users.
- Added searchable, filterable, and paginated audit history for actor, target, action,
  outcome, source, and date range.
- Added a read-only system-health panel for email delivery, login activity, and session
  revocation.
- Added database-backed authentication events and email-delivery events without storing
  message contents or verification/reset tokens.

### Security

- Added server-validated session versions so forced sign-out, suspension, and password
  changes invalidate previously issued sessions.
- Admin support mutations require current-password confirmation, a reason, CSRF and
  Origin validation, conservative rate limits, audit records, and protected admin
  targets.
- Admin-triggered emails have per-user, per-email-type cooldowns and never return secret
  tokens to the administrator.

### Documentation

- Expanded the Admin Dashboard guide with account-support workflows, system-health
  meanings, API routes, migration details, security boundaries, and deployment checks.

## [0.2.0] - 2026-07-22

### Added

- Added a responsive admin dashboard with aggregate account metrics, verification and
  login activity, paginated user management, and recent audit activity.
- Added desktop account tables, mobile account cards, responsive filters, and accessible
  suspend/reactivate confirmation dialogs aligned with the existing purple glass design.
- Added role and account-status authorization, login timestamps, operator-only admin
  role commands, account suspension/reactivation, and append-only admin audit events.
- Added a secure terminal command for creating an already-verified administrator with a
  hidden password confirmation prompt.
- Added backend API, database transaction, authorization, and migration contract tests.

### Security

- Admin authorization is denied by default and revalidated from the database on every
  admin request.
- Account-status changes require the acting administrator's current password, reason,
  CSRF token, valid Origin, and rate limit while preventing self/admin suspension.
- Admin responses disable browser caching and exclude financial records, password data,
  session identifiers, and authentication tokens.

### Documentation

- Added the approved implementation plan and operator/user guide for the admin dashboard.

## [0.1.16] - 2026-07-22

### Fixed

- Made the Linux CI dependency install tolerate optional native and WASM peer packages
  while retaining the locked `npm ci` installation.

### Documentation

- Added a complete guide to automated testing and continuous integration.
- Documented local commands, GitHub Actions verification, failure meanings, security
  isolation, troubleshooting, and test requirements for future features.
- Clarified that CI detects covered regressions but does not replace feature-specific
  tests, manual review, or Git conflict resolution.

## [0.1.15] - 2026-07-22

### Added

- Added a tracked backend test suite for account security, exports, anomaly detection,
  migrations, API contracts, and transactional email templates.
- Added root commands for backend tests, frontend lint/build checks, and the complete
  local quality gate.
- Added parallel GitHub Actions jobs for pushes to `main` and pull requests.
- Added the automated testing and CI implementation plan and contributor instructions.
- Updated the PostgreSQL binary driver for Python 3.13 development compatibility and
  kept pytest in development dependencies only.

### Security

- CI uses read-only repository permissions and no production secrets, database, or live
  email provider.

### Performance

- Backend and frontend CI jobs run in parallel and cache dependency downloads.

## [0.1.14] - 2026-07-22

### Documentation

- Added production Brevo API configuration for verification email delivery.
- Documented that Brevo IP authorization applies to the backend server, not registering
  users, plus remediation for `525 Unauthorized IP address` failures.
- Added sender verification, deployment, resend, URL, logging, and credential-rotation
  guidance.

## [0.1.13] - 2026-07-22

### Added

- **Email verification** — new registrations receive a 24-hour verification link and
  remain signed out until the address is verified.
- **Verification pages** — public pending, resend, success, invalid-link, and expired-link
  states for desktop and mobile.
- **Verification API** — rate-limited verification and generic resend endpoints with
  origin validation and bounded inputs.
- **Email-change verification** — changing an account email clears active sessions and
  requires the new address to be verified.
- **Email verification tests** — token lifecycle, migration, registration, login privacy,
  resend, email changes, and session cleanup coverage.

### Security

- Verification tokens are generated securely, stored only as SHA-256 hashes, expire
  after 24 hours, and are replaced on resend.
- Unverified state is disclosed during login only after the password is correct.
- Existing accounts are safely backfilled as verified during migration.

### Performance

- Token creation and consumption use short user-scoped transactions and indexed token
  hashes without loading unrelated account data.

## [0.1.12] - 2026-07-22

### Added

- **Self-service account deletion** — Settings danger zone with account-data download,
  current-password verification, exact username confirmation, and an accessible
  permanent-deletion modal.
- **Account deletion API** — authenticated, CSRF-protected, rate-limited
  `DELETE /api/account` with bounded input and minimal responses.
- **Account deletion tests** — transaction, rollback, endpoint security, session cleanup,
  stale-session rejection, and migration coverage.

### Security

- Account deletion locks and verifies the user inside the same transaction before one
  user-row deletion triggers database cascades.
- Authenticated routes reject and clear sessions whose user record no longer exists.

### Performance

- Budget and expense ownership now uses indexed `ON DELETE CASCADE` relationships, so
  deletion requires no application-side account-data loading or row-by-row cleanup.

## [0.1.11] - 2026-07-22

### Added

- **Full-account export** — Settings download for a versioned ZIP containing profile,
  budgets, expenses, categories, limits, recurring expenses, goals, income sources, and
  categorization rules, plus a human-readable PDF account summary.
- **Private export endpoint** — authenticated, rate-limited `GET /api/account-export`
  with no-store caching and a consistent read-only database snapshot.
- **Account export tests** — archive contract, Unicode, CSV formula protection,
  sensitive-field exclusion, user scoping, authentication, and response coverage.
- **Spending anomaly detection** — deterministic median/MAD scoring against 90 days of
  category history, exposed through `GET /api/spending-anomalies`.
- **Dashboard anomaly alert** — header exclamation badge with an accessible, responsive
  modal and a direct review action that opens the matching expense in the edit flow.
- **Backend anomaly tests** — scoring edge cases, authentication, user scoping, and empty
  history response coverage.

### Performance

- Anomaly history is loaded with one user-scoped joined query, category baselines are
  calculated once, and responses are capped at three findings.

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
