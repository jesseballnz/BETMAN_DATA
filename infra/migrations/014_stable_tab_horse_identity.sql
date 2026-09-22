\set ON_ERROR_STOP on

-- TAB entrant_id identifies a horse within one race entry and changes between
-- starts. horse_id is TAB's stable horse identity and is therefore the only
-- safe key for joining a current runner to retained historical starts.
ALTER TABLE runners
    ADD COLUMN IF NOT EXISTS external_horse_id TEXT;

CREATE INDEX IF NOT EXISTS idx_runners_external_horse_id
    ON runners (external_horse_id)
    WHERE external_horse_id IS NOT NULL;

-- Backfill only unambiguous provider mappings retained in the authoritative
-- raw payload store. Never infer identity from a horse name.
WITH provider_identity AS (
    SELECT
        runner->>'entrant_id' AS external_runner_id,
        min(runner->>'horse_id') AS external_horse_id
    FROM tab_event_payloads tep
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(tep.payload #> '{data,runners}') = 'array'
            THEN tep.payload #> '{data,runners}'
            ELSE '[]'::jsonb
        END
    ) AS runner
    WHERE NULLIF(runner->>'entrant_id', '') IS NOT NULL
      AND NULLIF(runner->>'horse_id', '') IS NOT NULL
    GROUP BY runner->>'entrant_id'
    HAVING count(DISTINCT runner->>'horse_id') = 1
)
UPDATE runners r
SET external_horse_id = identity.external_horse_id
FROM provider_identity identity
WHERE r.external_runner_id = identity.external_runner_id
  AND r.external_horse_id IS DISTINCT FROM identity.external_horse_id;

INSERT INTO schema_migrations (version) VALUES ('014_stable_tab_horse_identity.sql')
ON CONFLICT (version) DO NOTHING;
