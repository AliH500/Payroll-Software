from __future__ import annotations

from django.db import migrations, models


def backfill_employee_code(apps, schema_editor):
    """Give every existing employee a placeholder code so the NOT NULL + unique
    constraint can be applied. Real codes are supplied going forward via the form
    or CSV import; these placeholders only fill pre-existing rows.

    Runs as super-admin (transaction-local GUC) so Postgres RLS does not hide
    rows from the backfill, then NOT NULL would fail on the hidden nulls."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.is_super_admin', 'true', true)")
        cursor.execute(
            "UPDATE employees_employee SET employee_code = 'EMP-' || id "
            "WHERE employee_code IS NULL"
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0002_employee_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="employee_code",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.RunPython(backfill_employee_code, noop_reverse),
        migrations.AlterField(
            model_name="employee",
            name="employee_code",
            field=models.CharField(max_length=64),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=["company", "employee_code"],
                name="unique_company_employee_code",
            ),
        ),
    ]
