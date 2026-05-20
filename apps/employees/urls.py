from django.urls import path

from apps.employees import views

app_name = "employees"

urlpatterns = [
    path("", views.EmployeeListView.as_view(), name="list"),
    path("new/", views.EmployeeCreateView.as_view(), name="create"),
    path("import/", views.csv_import_view, name="import_csv"),
    path("import/template.csv", views.csv_template_view, name="import_template"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.EmployeeDeleteView.as_view(), name="delete"),
    path(
        "<int:pk>/create-portal-account/",
        views.create_portal_account_view,
        name="create_portal_account",
    ),
]
