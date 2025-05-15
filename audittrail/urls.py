from graphene_django.views import GraphQLView
from django.views.decorators.csrf import csrf_exempt
from django.contrib import admin
from django.urls import path, include
from logger.schema import schema


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('logger.urls')),
    path("graphql/", csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema))),
]
