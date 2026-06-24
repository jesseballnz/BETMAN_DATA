-- Migration 004: API key scopes, quota controls, and secure seed data

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE tenant_api_keys
    ADD COLUMN IF NOT EXISTS scopes TEXT[] NOT NULL DEFAULT ARRAY['read']::TEXT[],
    ADD COLUMN IF NOT EXISTS requests_per_minute INTEGER,
    ADD COLUMN IF NOT EXISTS daily_quota INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_feeds_name_url ON feeds (name, url);

DO $$
DECLARE
    admin_hash TEXT := current_setting('app.admin_api_key_hash', true);
    admin_prefix TEXT := current_setting('app.admin_api_key_prefix', true);
    readonly_hash TEXT := current_setting('app.webapp_readonly_api_key_hash', true);
    readonly_prefix TEXT := current_setting('app.webapp_readonly_api_key_prefix', true);
    admin_tenant_id INTEGER;
    readonly_tenant_id INTEGER;
BEGIN
    INSERT INTO tenants (name, slug, contact_email, license_type, active)
    VALUES ('BETMAN Platform Admin', '_admin', 'security@betman.invalid', 'admin', true)
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        contact_email = EXCLUDED.contact_email,
        license_type = EXCLUDED.license_type,
        active = true
    RETURNING id INTO admin_tenant_id;

    INSERT INTO tenants (name, slug, contact_email, license_type, active)
    VALUES ('BETMAN Data Viewer', 'betman-data-viewer', 'support@betman.invalid', 'content_only', true)
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        contact_email = EXCLUDED.contact_email,
        license_type = EXCLUDED.license_type,
        active = true
    RETURNING id INTO readonly_tenant_id;

    IF admin_hash IS NOT NULL AND admin_hash <> '' AND admin_prefix IS NOT NULL AND admin_prefix <> '' THEN
        INSERT INTO tenant_api_keys (
            tenant_id, key_hash, key_prefix, label, is_admin, active, scopes, requests_per_minute
        )
        VALUES (
            admin_tenant_id, admin_hash, admin_prefix, 'platform-admin', true, true,
            ARRAY['admin', 'read', 'write']::TEXT[], 600
        )
        ON CONFLICT (key_hash) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id,
            key_prefix = EXCLUDED.key_prefix,
            label = EXCLUDED.label,
            is_admin = true,
            active = true,
            scopes = EXCLUDED.scopes,
            requests_per_minute = EXCLUDED.requests_per_minute;
    END IF;

    IF readonly_hash IS NOT NULL AND readonly_hash <> '' AND readonly_prefix IS NOT NULL AND readonly_prefix <> '' THEN
        INSERT INTO tenant_api_keys (
            tenant_id, key_hash, key_prefix, label, is_admin, active, scopes, requests_per_minute, daily_quota
        )
        VALUES (
            readonly_tenant_id, readonly_hash, readonly_prefix, 'webapp-readonly', false, true,
            ARRAY['read']::TEXT[], 240, 50000
        )
        ON CONFLICT (key_hash) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id,
            key_prefix = EXCLUDED.key_prefix,
            label = EXCLUDED.label,
            is_admin = false,
            active = true,
            scopes = EXCLUDED.scopes,
            requests_per_minute = EXCLUDED.requests_per_minute,
            daily_quota = EXCLUDED.daily_quota;
    END IF;
END $$;

INSERT INTO schema_migrations (version) VALUES ('004_api_keys_and_security.sql')
ON CONFLICT (version) DO NOTHING;
