-- S3 B5 RUNBOOK v2 — direct-SQL admin disable (fallback only; UI/API is primary)
-- Preconditions: operator authed as an OWNER; app down or admin API unreachable;
--                :username and :actor_id supplied by the operator (never trusted from network input).
-- Run on the PRODUCTION database only after reading DEPLOY_RUNBOOK.md; every step row-count-guarded.

BEGIN;

-- Guard: the target must exist, be active, and not be the last active owner.
SELECT count(*) AS guard_target_exists_active
  FROM platform.platform_user
 WHERE username = :username AND is_active;              -- expect exactly 1, else ROLLBACK
SELECT count(*) AS guard_other_active_owners
  FROM platform.platform_user
 WHERE is_owner AND is_active
   AND username <> :username;                           -- expect >= 1, else ROLLBACK

-- 1) disable + bump updated_at (updated_at bump is REQUIRED so a later
--    re-enable can never resurrect pre-disable tokens; P1-3 check removed,
--    so updated_at + session deletion are the only revocation levers left).
UPDATE platform.platform_user
   SET is_active = false, updated_at = now()
 WHERE username = :username AND is_active;
-- row-count guard: must report UPDATE 1; anything else => ROLLBACK, do not proceed.

-- 2) revoke sessions (same transaction; count matches platform_session rows for the user)
DELETE FROM platform.platform_session
 WHERE user_id = (SELECT id FROM platform.platform_user WHERE username = :username);
-- row-count guard: compare to pre-count below; mismatch => ROLLBACK.

-- 3) audit entry in the SAME transaction (audit.audit_log is append-only)
INSERT INTO audit.audit_log
       (actor_user_id, action, entity_type, entity_id, old_values, new_values, created_at)
SELECT u.id, 'user_disabled', 'platform_user', u.id,
       jsonb_build_object('is_active', true),
       jsonb_build_object('is_active', false, 'sessions_deleted', true),
       now()
  FROM platform.platform_user u WHERE u.username = :username;
-- row-count guard: INSERT 1 expected.

COMMIT;

-- Verify (post-commit):
SELECT username, is_active, updated_at FROM platform.platform_user WHERE username = :username;  -- is_active = f
SELECT count(*) FROM platform.platform_session WHERE user_id = (SELECT id FROM platform.platform_user WHERE username = :username);  -- 0
SELECT action, entity_type, created_at FROM audit.audit_log WHERE entity_id = (SELECT id FROM platform.platform_user WHERE username = :username) ORDER BY created_at DESC LIMIT 1;  -- user_disabled

-- RE-ENABLE ORDERING (strict):
--   1. Only AFTER the credential compromise reason is resolved and the user re-attests (owner decision).
--   2. Sessions stay DELETED (no restore); user logs in fresh.
--   3. One transaction: UPDATE platform.platform_user SET is_active=true, updated_at=now() WHERE username=:username AND is_active=false  (guard: UPDATE 1)
--      + INSERT audit.audit_log (actor_user_id, 'user_enabled', 'platform_user', ...) in the SAME transaction.
--   4. NEVER re-enable by touching is_active alone without the audit insert and updated_at bump.
--   5. If password was exposed: rotate the password FIRST (via UI/API after app recovery), then re-enable.
-- Primary path remains the admin UI/API (app/auth/repo.py write_user_administration), which already
-- does steps 1-3 atomically with the same audit semantics — use it whenever the app is reachable.
