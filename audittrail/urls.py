from graphene_django.views import GraphQLView
from django.views.decorators.csrf import csrf_exempt
from django.contrib import admin
from django.urls import path, include
from logger.schema import schema
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def metrics_view(request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('logger.urls')),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema))),
    path('metrics/', metrics_view),
    path('schema/', SpectacularAPIView.as_view(), name="schema"), 
    path('docs/', SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"), 
] 