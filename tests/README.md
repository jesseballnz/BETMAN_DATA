# BETMAN Tests

This directory contains the integration and unit test suite for the BETMAN_DATA platform.

## Structure

```
tests/
  api/          — API service tests (FastAPI TestClient + pytest)
  consumer/     — Consumer service unit tests
  scoring/      — Score engine unit tests
  discovery/    — Discovery engine unit tests
  fixtures/     — Shared test fixtures and factory helpers
  conftest.py   — Shared pytest configuration
```

## Running Tests

```bash
# All tests
make test

# API tests only
make test-api

# Consumer tests only
make test-consumer
```

## Test Database

Integration tests use a separate test database. Set `TEST_DATABASE_URL` in your
`.env.test` file:

```
TEST_DATABASE_URL=******localhost:5432/betman_data_test
```

Run migrations against the test database before running integration tests:

```bash
psql $TEST_DATABASE_URL -f infra/migrations/001_initial_schema.sql
psql $TEST_DATABASE_URL -f infra/migrations/002_intelligence_layers.sql
psql $TEST_DATABASE_URL -f infra/migrations/003_pedigree_and_providers.sql
psql $TEST_DATABASE_URL -f infra/migrations/004_api_keys_and_security.sql
```

## Writing Tests

- Unit tests use `pytest` with `pytest-asyncio` for async test cases.
- API tests use FastAPI's `TestClient`; starter coverage is DB-optional and safe to run offline.
- Use fixtures in `tests/fixtures/` for common test data setup.
- All tests must be idempotent and clean up after themselves.
