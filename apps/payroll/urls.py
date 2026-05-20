from django.urls import path

from apps.payroll import views

app_name = "payroll"

urlpatterns = [
    path("periods/", views.PayPeriodListView.as_view(), name="period_list"),
    path("periods/new/", views.PayPeriodCreateView.as_view(), name="period_create"),
    path("periods/<int:pk>/", views.PayPeriodDetailView.as_view(), name="period_detail"),
    path("periods/<int:pk>/run/", views.run_payroll_view, name="period_run"),
    path("periods/<int:pk>/close/", views.close_period_view, name="period_close"),
    path("periods/<int:pk>/print/", views.PeriodPayslipsPrintView.as_view(), name="period_print"),
    path("payslips/", views.PayslipListView.as_view(), name="payslip_list"),
    path("payslips/<int:pk>/", views.PayslipDetailView.as_view(), name="payslip_detail"),
    path("my/", views.MyPayslipsView.as_view(), name="my_payslip_list"),
    path("my/<int:pk>/", views.MyPayslipDetailView.as_view(), name="my_payslip_detail"),
]
