from django.apps import AppConfig


class PayrollConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payroll"
    label = "payroll"
    verbose_name = "Payroll"

    def ready(self) -> None:
        from apps.audit.signals import register_audit
        from apps.payroll.models import PayPeriod, Payslip

        register_audit(PayPeriod)
        register_audit(Payslip)
