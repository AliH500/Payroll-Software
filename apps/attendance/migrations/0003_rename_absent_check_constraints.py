from django.db import migrations

# PostgreSQL renames a column in place on RenameField but keeps the implicit
# `>= 0` check-constraint's original name. After 0002 the two absent-related
# constraints guard the right columns under misleading names; realign the names.
# Ordered to avoid a name collision: free `..._days_absent_check` before reusing it.
FORWARD = """
ALTER TABLE attendance_attendancerecord
    RENAME CONSTRAINT attendance_attendancerecord_days_absent_check
    TO attendance_attendancerecord_days_total_absent_check;
ALTER TABLE attendance_attendancerecord
    RENAME CONSTRAINT attendance_attendancerecord_days_absent_without_leave_check
    TO attendance_attendancerecord_days_absent_check;
"""

REVERSE = """
ALTER TABLE attendance_attendancerecord
    RENAME CONSTRAINT attendance_attendancerecord_days_absent_check
    TO attendance_attendancerecord_days_absent_without_leave_check;
ALTER TABLE attendance_attendancerecord
    RENAME CONSTRAINT attendance_attendancerecord_days_total_absent_check
    TO attendance_attendancerecord_days_absent_check;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_rename_attendance_absent_fields"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
