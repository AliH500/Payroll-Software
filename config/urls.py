from django.contrib import admin
from django.urls import include, path

from config.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("employees/", include("apps.employees.urls")),
    path("compensation/", include("apps.compensation.urls")),
    path("payroll/", include("apps.payroll.urls")),
]
