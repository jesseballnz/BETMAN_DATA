# BETMAN_DATA migrations

Migrations are plain SQL and remain safe to run with `psql -f` in sequence:

```bash
psql "$DATABASE_URL" -f infra/migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f infra/migrations/002_intelligence_layers.sql
psql "$DATABASE_URL" -f infra/migrations/003_pedigree_and_providers.sql
psql "$DATABASE_URL" -f infra/migrations/004_api_keys_and_security.sql
```

Each migration is written to be re-runnable (`IF NOT EXISTS`, guarded inserts, and `schema_migrations` tracking).
`make migrate` and the CI migration job also pass session settings so migration `004` can seed hashed admin and read-only API keys without ever storing raw keys in SQL.
