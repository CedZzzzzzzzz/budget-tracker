# Automated Testing and Continuous Integration

## Overview

Budget Tracker includes an automated quality gate that checks changes before they are
merged or deployed. It detects regressions in behavior already covered by tests and
confirms that the frontend can still be linted and built for production.

This is a developer feature. It does not add a new screen to the application and it does
not resolve Git merge conflicts. It verifies the behavior of the code produced after a
change or merge.

## How it works

```text
Implement a feature
        |
Add or update its tests
        |
Run npm test locally
        |
Push the code and tests
        |
GitHub Actions runs the quality workflow
        |
Backend tests and frontend checks pass or fail
```

The workflow is stored in `.github/workflows/quality.yml`. It runs for pushes to `main`
and for pull requests.

## What is checked

### Backend tests

The backend job installs `requirements-dev.txt` and runs `python -m pytest`. Current
coverage includes:

- account deletion and session cleanup;
- full-account export behavior;
- spending anomaly detection;
- registration and email verification;
- password-reset and verification email templates;
- authentication, CSRF, and API response contracts;
- database migration constraints and indexes.

Backend tests mock database and email-provider boundaries. They do not connect to the
production Neon database or send live Brevo messages.

### Frontend checks

The frontend job runs:

```text
npm run lint
npm run build
```

Linting detects suspicious React and JavaScript patterns. The production build detects
invalid JSX, missing modules, broken imports, and bundling errors.

## Running the checks locally

From the project directory, create and activate a Python environment if one is not
already available:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --requirement requirements-dev.txt
```

Run the complete quality gate:

```powershell
npm test
```

Run one side independently:

```powershell
npm run test:backend
npm run test:frontend
```

A successful backend run reports the number of passing tests. A successful frontend run
finishes with a completed Vite production build. Warnings remain visible but only a
nonzero command result fails the workflow.

## Verifying the GitHub workflow

1. Commit the feature code and its tests.
2. Push the branch or open a pull request.
3. Open the repository's **Actions** tab.
4. Open the **Quality** workflow run.
5. Confirm that **Backend tests** and **Frontend checks** are green.
6. Open a failed job to see the failing command and its logs.

## Tests are still required for new features

Continuous integration runs tests; it does not invent them. A new feature can be broken
while the workflow stays green if no test describes the new behavior.

Each feature should normally be pushed with tests for:

- its successful path;
- invalid and boundary inputs;
- authentication, authorization, and user isolation;
- error responses and cleanup behavior;
- database or migration contracts when schema changes are involved;
- important frontend states where automated coverage is practical.

For example, a two-factor authentication feature should include tests for setup, valid
and invalid codes, login challenges, recovery, rate limits, and factor removal. The CI
workflow will then run those tests on every future change.

## Understanding failures

| Result | Meaning | Typical response |
| --- | --- | --- |
| Backend tests fail | An API, security rule, calculation, or data contract changed unexpectedly | Open the failed test and compare the expected behavior with the implementation |
| Frontend lint fails | JavaScript or React contains a likely correctness issue | Fix the reported file and rule |
| Frontend build fails | Production assets cannot be generated | Check imports, JSX syntax, environment references, and build output |
| All jobs pass | Every currently automated check succeeded | Review the feature manually and merge when the rest of the review is complete |

A green workflow does not prove the absence of every bug. It proves that all implemented
checks passed. Manual review and feature-specific tests remain necessary.

## Security and isolation

- The workflow has read-only repository permissions.
- No `.env` file or production secret is required.
- Tests use placeholder credentials and mocked service boundaries.
- CI does not send emails or modify production data.
- Backend and frontend jobs run independently and in parallel.
- Obsolete runs for the same branch or pull request are cancelled.

## Adding a backend test

Add a descriptively named `test_*.py` file under `tests/`, or add a focused test to the
matching module. Tests should be deterministic and should mock network, email, and
database boundaries unless the suite explicitly introduces an isolated integration
environment.

Run the backend suite before pushing:

```powershell
npm run test:backend
```

Commit the test alongside the implementation so future changes continue to verify the
feature.

## Troubleshooting

### Python or pytest is not found

Activate the virtual environment and install development dependencies:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install --requirement requirements-dev.txt
```

### Tests pass locally but fail in GitHub

Compare Python and Node versions, check case-sensitive file paths, and ensure every
required file was committed. CI runs without the local `.env`, so tests must not depend
on local credentials.

### A new feature is broken but CI is green

Add a test that reproduces the failure, confirm that it fails before the fix, implement
the correction, and rerun the complete quality gate.
