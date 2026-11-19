CREATE TABLE IF NOT EXISTS replay_jobs (
 id uuid PRIMARY KEY, idempotency_key text UNIQUE NOT NULL, request_hash text NOT NULL,
 snapshot_id text NOT NULL, snapshot_hash text NOT NULL, total integer NOT NULL,
 status text NOT NULL CHECK (status IN ('running','paused','completed','failed')),
 target_rate integer NOT NULL CHECK(target_rate BETWEEN 10 AND 5000),
 produced integer NOT NULL DEFAULT 0, checkpoint integer NOT NULL DEFAULT 0,
 inserted integer NOT NULL DEFAULT 0, duplicates integer NOT NULL DEFAULT 0,
 rejected integer NOT NULL DEFAULT 0, validation_rejected integer NOT NULL DEFAULT 0,
 error text, next_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
-- replay_batches and replay_outbox are partitioned by created_at: see 002_partitioning.sql.
-- Databases created before that change had plain heap tables here; they are converted in place
-- by ingestion_service.infrastructure.database.partitioning.migrate().
