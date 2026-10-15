# Test Instructions

Prerequisites: Docker Engine, Docker Compose, Python 3, and Node.js 18+.

Run operational unit tests from the repository root:

    python3 -m unittest discover -s tests -v

Run API tests with the current source mounted read-only:

    docker compose run --rm --no-deps -v "$PWD/api:/app:ro" api python -m unittest discover -s tests -v

Build the API image first on a fresh clone:

    docker compose build api

Run frontend JavaScript scenarios:

    node tests/test_frontend.js

These tests simulate browser APIs; they are not browser rendering tests.

Run the separate disposable deployment and failure drill:

    python3 tests/integration_drill.py

It builds separate containers with fresh volumes and nondefault database
credentials, delays database readiness, exercises ticket operations through
the gateway, stops dependencies and runs restore/rollback checks.
Only the generated drill project's volumes and images are removed.

Run a restore drill against the currently configured PostgreSQL service:

    python3 tests/restore_drill.py

This creates two disposable databases, restores a new backup, checks data,
rejects a nonempty target and verifies transactional rollback.
The source database is not modified. Run without concurrent application writes.
The backup remains under backups/ and is ignored by Git.

Observed results on 15 October 2026: 4 operational unit tests,
13 API unit tests, 10 frontend scenarios and the disposable integration drill
passed. Runtime health/startup and real database recovery were also checked.

No tests create AWS resources. Integration tests require a running Docker daemon.
