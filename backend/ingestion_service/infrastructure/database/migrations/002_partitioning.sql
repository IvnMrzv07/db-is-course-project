-- Declarative daily RANGE partitioning of the Ingestion outbox tables (plan item 5).
-- Applied on every start under advisory lock 912001, after partitioning.detach_legacy()
-- renamed pre-partitioning heap tables to *_legacy (their rows are copied back by
-- partitioning.copy_legacy() and the legacy tables are dropped in the same transaction).
--
-- PostgreSQL requires every PRIMARY KEY/UNIQUE constraint of a partitioned table to contain
-- the partition key, so keys become (id, created_at). Global uniqueness of id is still given
-- by construction: id = uuid5(job_id, start_offset) and start_offset = replay_jobs.produced is
-- advanced under SELECT ... FOR UPDATE of the job row in the same transaction.
-- A batch and its outbox entry are written in one transaction with the same created_at, so the
-- composite FK keeps them in partitions with identical bounds (aligned retention).
CREATE TABLE IF NOT EXISTS replay_batches (
 id uuid NOT NULL, job_id uuid NOT NULL REFERENCES replay_jobs(id),
 start_offset integer NOT NULL, end_offset integer NOT NULL,
 status text NOT NULL DEFAULT 'pending',
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT replay_batches_pk PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
CREATE TABLE IF NOT EXISTS replay_outbox (
 id uuid NOT NULL, payload jsonb NOT NULL,
 sent boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT replay_outbox_pk PRIMARY KEY (id, created_at),
 CONSTRAINT replay_outbox_batch_fk FOREIGN KEY (id, created_at) REFERENCES replay_batches(id, created_at)
) PARTITION BY RANGE (created_at);
-- Fallback partitions: a write never fails even if maintenance has not created the day yet.
-- Rows that land here are moved into a proper partition by partitioning.ensure_partitions().
CREATE TABLE IF NOT EXISTS replay_batches_default PARTITION OF replay_batches DEFAULT;
CREATE TABLE IF NOT EXISTS replay_outbox_default PARTITION OF replay_outbox DEFAULT;
CREATE INDEX IF NOT EXISTS replay_batches_job_offset ON replay_batches(job_id, start_offset);
CREATE INDEX IF NOT EXISTS replay_batches_pending ON replay_batches(job_id, start_offset) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS replay_outbox_pending ON replay_outbox(created_at) WHERE NOT sent;
