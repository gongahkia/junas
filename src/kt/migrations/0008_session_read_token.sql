ALTER TABLE sessions ADD COLUMN read_token_hash TEXT;

-- Preserve compatibility for sessions created before read-token hardening.
-- Existing sessions can use host_secret as the read token until rotated/recreated.
UPDATE sessions
SET read_token_hash = host_secret_hash
WHERE read_token_hash IS NULL OR read_token_hash = '';
