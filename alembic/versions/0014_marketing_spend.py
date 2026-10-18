"""Marketing spend + objective/KPI tracking (V2 §2B.16–2B.18).

Spend links to a doctor/KOL, territory, date, amount, activity type and an
explicit product/brand set (join table, never free-text inference). An
objective/KPI row attaches to a spend row or stands alone.
"""
from alembic import op

revision = "0014_marketing_spend"
down_revision = "0013_sales_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE marketing.marketing_spend (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            kol_id uuid REFERENCES marketing.marketing_kol(id),
            territory_id uuid REFERENCES master_data.master_territory(id),
            spend_date date NOT NULL,
            amount numeric(14,2) NOT NULL CHECK (amount >= 0),
            activity_type varchar(40) NOT NULL,
            notes text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_marketing_spend_date ON marketing.marketing_spend(spend_date);
        CREATE INDEX ix_marketing_spend_kol ON marketing.marketing_spend(kol_id);

        CREATE TABLE marketing.marketing_spend_product (
            spend_id uuid NOT NULL REFERENCES marketing.marketing_spend(id) ON DELETE CASCADE,
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            PRIMARY KEY (spend_id, product_id)
        );

        CREATE TABLE marketing.marketing_objective (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            spend_id uuid REFERENCES marketing.marketing_spend(id) ON DELETE SET NULL,
            kol_id uuid REFERENCES marketing.marketing_kol(id),
            product_id uuid REFERENCES master_data.master_product(id),
            territory_id uuid REFERENCES master_data.master_territory(id),
            objective text NOT NULL,
            expected_kpi text,
            actual_result text,
            followup_notes text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_marketing_objective_spend ON marketing.marketing_objective(spend_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE marketing.marketing_objective;
        DROP TABLE marketing.marketing_spend_product;
        DROP TABLE marketing.marketing_spend;
    """)
