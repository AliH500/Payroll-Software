from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.attendance"
    label = "attendance"
    verbose_name = "Attendance"

    def ready(self) -> None:
        from apps.attendance.models import AttendanceRecord, AttendanceSheet
        from apps.audit.signals import register_audit

        register_audit(AttendanceSheet)
        register_audit(AttendanceRecord)
