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
    path('dossiers/<int:collaborateur_id>/', views.explorateur_dossiers, name='explorateur_dossiers'),
    path('autocomplete-expediteurs/', views.autocomplete_expediteurs, name='autocomplete_expediteurs'),
    path('autocomplete-destinataires/', views.autocomplete_destinataires, name='autocomplete_destinataires'),
    path('collaborateur/<int:collaborateur_id>/tous-emails/', views.tous_emails_collaborateur, name='tous_emails'),
    path('collaborateur/<int:collaborateur_id>/dossiers/<int:folder_id>/', views.contenu_dossier, name='contenu_dossier'),
    path('collaborateur/<int:collaborateur_id>/dossiers/', views.explorateur_dossiers, name='explorateur_dossiers'),
    path('collaborateur/<int:collaborateur_id>/dossier/<int:folder_id>/', views.contenu_dossier, name='contenu_dossier'),
    path('thread/<int:message_id>/', views.thread, name='thread'),
]