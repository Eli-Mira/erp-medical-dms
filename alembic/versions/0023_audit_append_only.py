"""Reject mutation and truncation of the append-only audit log."""

from alembic import op

revision = "0023_audit_append_only"
down_revision = "0022_territory_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION audit.reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit.audit_log is append-only' USING ERRCODE = '42501';
        END $$;
        CREATE TRIGGER audit_log_no_update_delete
            BEFORE UPDATE OR DELETE ON audit.audit_log
            FOR EACH ROW EXECUTE FUNCTION audit.reject_audit_mutation();
        CREATE TRIGGER audit_log_no_truncate
            BEFORE TRUNCATE ON audit.audit_log
            FOR EACH STATEMENT EXECUTE FUNCTION audit.reject_audit_mutation();
        REVOKE UPDATE, DELETE, TRUNCATE ON audit.audit_log FROM PUBLIC;
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER audit_log_no_truncate ON audit.audit_log;
        DROP TRIGGER audit_log_no_update_delete ON audit.audit_log;
        DROP FUNCTION audit.reject_audit_mutation();
    """)
