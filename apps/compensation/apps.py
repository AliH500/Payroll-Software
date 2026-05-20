from django.apps import AppConfig


class CompensationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.compensation"
    label = "compensation"
    verbose_name = "Compensation"

    def ready(self) -> None:
        from apps.audit.signals import register_audit
        from apps.compensation.models import Bonus, Deduction, ExpenseReimbursement

        register_audit(Bonus)
        register_audit(Deduction)
        register_audit(ExpenseReimbursement)
