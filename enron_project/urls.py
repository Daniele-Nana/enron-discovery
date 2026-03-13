
from django.contrib import admin
from django.urls import path, include
from discovery import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('', include('discovery.urls')),
]