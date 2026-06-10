from django.urls import path

from apps.attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.AttendancePeriodListView.as_view(), name="period_list"),
    path("template.csv", views.attendance_template_view, name="import_template"),
    path("<int:period_pk>/", views.attendance_sheet_view, name="sheet"),
    path("<int:period_pk>/import/", views.attendance_import_view, name="import_csv"),
]
