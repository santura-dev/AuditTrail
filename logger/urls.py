from django.urls import path
from .views import LogCreateView, LogListView

urlpatterns = [
    path('logs/', LogCreateView.as_view(), name='log-create'),
    path('logs/list/', LogListView.as_view(), name='log-list'),
]