# logger/urls.py (corrected)
print("Loading logger/urls.py")
from django.urls import path
from .views import LogCreateView, LogListView, LogExportView, ArchiveLogsView

urlpatterns = [
    path("logs/", LogCreateView.as_view(), name="log-create"),
    path("logs/list/", LogListView.as_view(), name="log-list"),  
    path("logs/export/", LogExportView.as_view(), name="log-export"), 
    path("logs/archive/", ArchiveLogsView.as_view(), name="log-archive"),
]