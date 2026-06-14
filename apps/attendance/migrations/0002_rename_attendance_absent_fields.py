from django.db import migrations


class Migration(migrations.Migration):
    """Rename absent fields so the schema matches the CSV spec.

    Old `days_absent` held the total (absent + leave); old
    `days_absent_without_leave` held plain absences. The two renames must run in
    order: free up `days_absent` first, then reuse the name for plain absences.
    """

    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="attendancerecord",
            old_name="days_absent",
            new_name="days_total_absent",
        ),
        migrations.RenameField(
            model_name="attendancerecord",
            old_name="days_absent_without_leave",
            new_name="days_absent",
        ),
    ]
