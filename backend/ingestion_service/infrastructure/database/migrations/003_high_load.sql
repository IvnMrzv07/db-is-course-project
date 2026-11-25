-- High-load replay: unlimited rate (0 = MAX), rates above 5,000 documents/s and operator cancellation.
-- Applied on every start after 002; the constraints are replaced only once.
DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint
                WHERE conrelid = 'replay_jobs'::regclass AND conname = 'replay_jobs_rate_v2') THEN
  ALTER TABLE replay_jobs DROP CONSTRAINT IF EXISTS replay_jobs_target_rate_check;
  ALTER TABLE replay_jobs DROP CONSTRAINT IF EXISTS replay_jobs_status_check;
  ALTER TABLE replay_jobs ADD CONSTRAINT replay_jobs_rate_v2
   CHECK (target_rate = 0 OR target_rate BETWEEN 10 AND 100000);
  ALTER TABLE replay_jobs ADD CONSTRAINT replay_jobs_status_v2
   CHECK (status IN ('running','paused','completed','failed','cancelled'));
 END IF;
END $$;
-- Superseded by replay_batches_unfinished (002), whose predicate matches the checkpoint query.
DROP INDEX IF EXISTS replay_batches_pending;
