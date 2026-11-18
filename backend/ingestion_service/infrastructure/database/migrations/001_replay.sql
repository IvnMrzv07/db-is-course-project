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
CREATE TABLE IF NOT EXISTS replay_batches (
 id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES replay_jobs(id),
 start_offset integer NOT NULL, end_offset integer NOT NULL,
 status text NOT NULL DEFAULT 'pending',
 UNIQUE(job_id, start_offset)
);
CREATE TABLE IF NOT EXISTS replay_outbox (
 id uuid PRIMARY KEY REFERENCES replay_batches(id), payload jsonb NOT NULL,
 sent boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS replay_outbox_pending ON replay_outbox(created_at) WHERE NOT sent;
CREATE INDEX IF NOT EXISTS replay_batches_pending ON replay_batches(job_id,start_offset) WHERE status = 'pending';
