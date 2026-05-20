"""Postgres Row-Level Security policies on PII tables.

Layer three of the multi-tenant defense (after the default TenantManager and
the CI guard that scans for unannotated bypass calls). When the application
layer fails to scope a query by tenant, the database refuses to return rows
that belong to a different tenant.

Two policies per table:
- `tenant_isolation` — accepts rows where `company_id` matches the GUC
  `app.current_tenant_id` set per request by TenantResolutionMiddleware.
- `super_admin_bypass` — accepts every row when the GUC `app.is_super_admin`
  is 'true'. Used by the Django admin (super-admin only) and by tests.

`FORCE ROW LEVEL SECURITY` ensures the table owner (the Django DB user)
is also constrained — without it the application would bypass RLS entirely.
"""

from __future__ import annotations

from django.db import migrations

# (table_name, company_filter_clause_or_None)
# None signals "use parent payslip's company via a subquery" — see PayslipLine.
PII_TABLES_WITH_COMPANY = [
    "employees_employee",
    "payroll_payslip",
    "compensation_bonus",
    "compensation_deduction",
    "compensation_expensereimbursement",
    "audit_auditlogentry",
]

PAYSLIP_LINE_TABLE = "payroll_payslipline"

ENABLE_SQL = []
DISABLE_SQL = []

for _table in PII_TABLES_WITH_COMPANY:
    ENABLE_SQL.append(
        f"""
        ALTER TABLE {_table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {_table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON {_table}
            USING (
                company_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int
            );
        CREATE POLICY super_admin_bypass ON {_table}
            USING (current_setting('app.is_super_admin', true) = 'true');
        """
    )
    DISABLE_SQL.append(
        f"""
        DROP POLICY IF EXISTS tenant_isolation ON {_table};
        DROP POLICY IF EXISTS super_admin_bypass ON {_table};
        ALTER TABLE {_table} NO FORCE ROW LEVEL SECURITY;
        ALTER TABLE {_table} DISABLE ROW LEVEL SECURITY;
        """
    )

# PayslipLine has no company_id column — gate via its parent Payslip.
ENABLE_SQL.append(
    f"""
    ALTER TABLE {PAYSLIP_LINE_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {PAYSLIP_LINE_TABLE} FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON {PAYSLIP_LINE_TABLE}
        USING (
            payslip_id IN (
                SELECT id FROM payroll_payslip
                WHERE company_id =
                    NULLIF(current_setting('app.current_tenant_id', true), '')::int
            )
        );
    CREATE POLICY super_admin_bypass ON {PAYSLIP_LINE_TABLE}
        USING (current_setting('app.is_super_admin', true) = 'true');
    """
)
DISABLE_SQL.append(
    f"""
    DROP POLICY IF EXISTS tenant_isolation ON {PAYSLIP_LINE_TABLE};
    DROP POLICY IF EXISTS super_admin_bypass ON {PAYSLIP_LINE_TABLE};
    ALTER TABLE {PAYSLIP_LINE_TABLE} NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE {PAYSLIP_LINE_TABLE} DISABLE ROW LEVEL SECURITY;
    """
)


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0001_initial"),
        ("employees", "0002_employee_user"),
        ("compensation", "0001_initial"),
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql="\n".join(ENABLE_SQL), reverse_sql="\n".join(DISABLE_SQL)),
    ]
