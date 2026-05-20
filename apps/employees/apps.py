from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.employees"
    label = "employees"
    verbose_name = "Employees"

    def ready(self) -> None:
        # Late import so the model is loaded only after the app registry is ready.
        from apps.audit.signals import register_audit
        from apps.employees.models import Employee

        register_audit(Employee)
