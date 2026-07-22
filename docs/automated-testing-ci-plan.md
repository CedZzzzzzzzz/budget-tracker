# Automated Testing and CI Plan

## Objective

Create a reliable automated quality gate for Budget Tracker. Every pushed change and
pull request must prove that backend behavior, security-sensitive account flows, frontend
code quality, and the production frontend build remain healthy.

## Why this is next

The application now handles email verification, password resets, account deletion,
account exports, anomaly detection, and user financial data. These flows cross API,
database, email, and frontend boundaries. The existing backend tests are useful but are
ignored by Git, and there is no continuous integration workflow to run them before code
is merged or deployed.

## Scope

- Track the existing backend tests in the repository.
- Add tests for the shared password-reset and verification email template.
- Keep production credentials, live databases, and real email delivery out of tests.
- Add consistent local commands for backend and frontend verification.
- Add a GitHub Actions workflow for pushes and pull requests.
- Run backend and frontend jobs independently so failures are easy to identify.
- Cache package downloads where supported without caching application secrets.
- Document the verification commands and CI contract.

## Out of scope

- Browser end-to-end tests that require a deployed backend or live Neon database.
- Sending live Brevo messages from CI.
- Load, penetration, and visual-regression testing.
- Automatic production deployment.
- Replacing the current database layer or frontend build system.

## Current state

- Backend tests use `pytest`, Flask test clients, and mocked database boundaries.
- Tests cover account deletion, account export, spending anomalies, email verification,
  endpoint behavior, and migration contracts.
- `requirements-dev.txt` installs production dependencies and pins `pytest`.
- Frontend scripts provide `lint` and `build` commands.
- Playwright exists as a development dependency, but the current animation script
  requires a separately running local server and is unsuitable for the first CI gate.
- The `/tests/` path is ignored and no `.github/workflows` pipeline exists.

## Test architecture

### Backend unit tests

Pure calculation, serialization, token, email-template, and database-boundary behavior
must be tested without a network connection. External systems are replaced with mocks.

### Backend API tests

Flask test clients exercise authentication, CSRF, status codes, response contracts, and
session cleanup. Database and mail delivery functions are patched at the route boundary.

### Migration contract tests

Migration tests read SQL files and assert required constraints, indexes, backfills, and
cascade behavior. CI does not require a live database for this layer.

### Frontend quality gates

Oxlint checks React and JavaScript correctness. Vite performs a production build to catch
module, JSX, import, and bundling failures. Existing warnings remain visible but do not
fail the first rollout unless the tool reports a nonzero exit code.

## Email-template coverage

The shared transactional template must be checked for:

- branded responsive table structure and inline styles;
- the correct action label and expiry copy for each email;
- a plain-text alternative for each message;
- escaped action URLs in HTML attributes and fallback links;
- no network calls while rendering template content.

## Local command contract

The root project exposes commands that mirror CI:

```text
npm run test:backend
npm run test:frontend
npm test
```

`test:backend` runs `python -m pytest`. `test:frontend` runs frontend lint followed by the
production build. `npm test` runs both suites in sequence.

## CI workflow

GitHub Actions runs on pushes to `main` and on pull requests:

1. The backend job checks out the repository, installs a pinned Python version, caches
   pip downloads, installs `requirements-dev.txt`, and runs `python -m pytest`.
2. The frontend job checks out the repository, installs a pinned Node version, restores
   the npm cache, runs `npm ci` in `frontend`, runs lint, and builds production assets.
3. Jobs use minimum read-only repository permissions and do not receive application
   secrets.
4. Concurrency cancels obsolete runs for the same branch or pull request.

## Security

- CI must never load `.env` credentials or contact the production database.
- Tests must not send real password-reset or verification emails.
- Secret values must not appear in fixtures, logs, snapshots, or workflow files.
- Workflow permissions are limited to repository-content reads.
- Third-party workflow actions use explicit major versions.

## Performance

- Backend and frontend jobs run in parallel.
- Dependency caches reduce repeated installation time.
- Unit and contract tests avoid database and network latency.
- Browser installation is deferred until stable end-to-end coverage is added.

## Implementation steps

1. Stop ignoring `/tests/` and retain the development requirements file.
2. Add transactional email-template tests.
3. Add root npm verification scripts matching CI commands.
4. Add the backend and frontend GitHub Actions jobs.
5. Update the changelog and testing documentation.
6. Install development dependencies in an isolated local environment.
7. Run backend tests, frontend lint, frontend build, and repository consistency checks.

## Acceptance criteria

- All test modules are visible to Git and contain no credentials.
- `python -m pytest` passes without a live database or email provider.
- Email-template tests cover verification and password-reset content and escaping.
- Frontend lint and production build pass.
- GitHub Actions runs backend and frontend jobs for pushes and pull requests.
- The workflow uses no production secrets and grants read-only permissions.
- Local root commands reproduce the CI quality gates.
- Documentation identifies the exact commands developers should run before pushing.
