from django.urls import path

from apps.compensation import views

app_name = "compensation"

urlpatterns = [
    path("", views.compensation_list, name="list"),
    path("new/<str:kind>/", views.compensation_create, name="create"),
]
