"""URL configuration for NetBox vCenter plugin."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.VCenterDashboardView.as_view(), name="dashboard"),
    path("refresh/<str:server>/", views.VCenterRefreshView.as_view(), name="refresh"),
    path("import/", views.VMImportView.as_view(), name="import"),
    path("compare/", views.VMComparisonView.as_view(), name="compare"),
]
