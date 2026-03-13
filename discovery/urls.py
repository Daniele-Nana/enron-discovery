from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('search/', views.recherche, name='recherche'),
    path('thread/<int:message_id>/', views.thread, name='thread'),
    path('influence/<int:employee_id>/', views.influence, name='influence'),
    path('thread_complet/<int:message_id>/', views.thread_complet, name='thread_complet'),
    path('graphe/<int:collaborateur_id>/', views.graphe, name='graphe'),
    path('graphe/', views.graphe_interactif, name='graphe_interactif'),
    path('graphe/data/', views.graphe_data, name='graphe_data'),
    path('wordcloud-data/', views.wordcloud_data, name='wordcloud_data'),
]