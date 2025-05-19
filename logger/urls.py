from django.urls import path
from .views import LogCreateView, LogListView, LogExportView

urlpatterns = [
    path("logs/", LogCreateView.as_view(), name="log-create"),
    path("logs/list/", LogListView.as_view(), name="log-list"),
    path("logs/export/", LogExportView.as_view(), name="log-export"),
]