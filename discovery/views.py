from django.contrib.postgres.search import SearchVector, SearchQuery
from .models import Message, Collaborateur
from django.shortcuts import render
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Count, Min, Max
from django.core.paginator import Paginator
from django.db import connection
from collections import namedtuple
from django.db.models.functions import TruncMonth
from datetime import datetime
from django.db.models.functions import ExtractYear

def dashboard(request):
    # Statistiques de base
    total_messages = Message.objects.count()
    total_collaborateurs = Collaborateur.objects.count()
    
    # Premier et dernier email
    dates = Message.objects.aggregate(premier=Min('date'), dernier=Max('date'))
    premier_email = dates['premier']
    dernier_email = dates['dernier']
    
    # Nombre de fils de discussion (messages avec in_reply_to non vide)
    total_threads = Message.objects.filter(in_reply_to__isnull=False).count()
    
    # Top 10 expéditeurs
    top_senders = Collaborateur.objects.annotate(
        nb_envoyes=Count('envoyes')
    ).order_by('-nb_envoyes')[:10]
    
    # Statistiques par mois (pour le graphique)
    mois_stats = Message.objects.annotate(
        mois=TruncMonth('date')
    ).values('mois').annotate(
        count=Count('id')
    ).order_by('mois')

        # Liste des années distinctes
    annees = Message.objects.annotate(annee=ExtractYear('date')).values_list('annee', flat=True).distinct().order_by('-annee')
    
    mois_labels = [m['mois'].strftime('%Y-%m') for m in mois_stats if m['mois']]
    mois_data = [m['count'] for m in mois_stats]
    
    context = {
        'total_messages': total_messages,
        'total_collaborateurs': total_collaborateurs,
        'premier_email': premier_email,
        'dernier_email': dernier_email,
        'total_threads': total_threads,
        'top_senders': top_senders,
        'mois_labels': mois_labels,
        'mois_data': mois_data,
        'annees': annees,
    }
    return render(request, 'discovery/dashboard.html', context)

def recherche(request):
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    expediteur_id = request.GET.get('expediteur', '')

    messages = Message.objects.all().order_by('-date')

    if query:
        messages = messages.filter(search_vector=SearchQuery(query))

    if date_debut:
        messages = messages.filter(date__gte=date_debut)
    if date_fin:
        messages = messages.filter(date__lte=date_fin)

    # Filtre sécurisé : on vérifie que expediteur_id est un nombre
    if expediteur_id and expediteur_id.isdigit():
        messages = messages.filter(expediteur_id=int(expediteur_id))

    # Pagination
    paginator = Paginator(messages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Liste des expéditeurs pour le menu déroulant
    expediteurs = Collaborateur.objects.filter(envoyes__isnull=False).distinct().order_by('email')

    context = {
        'page_obj': page_obj,
        'query': query,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'expediteur_id': int(expediteur_id) if expediteur_id and expediteur_id.isdigit() else None,
        'expediteurs': expediteurs,
    }
    return render(request, 'discovery/recherche.html', context)

def influence(request, employee_id):
    # Récupère le collaborateur ou renvoie une erreur 404
    employee = get_object_or_404(Collaborateur, id=employee_id)

    # Compte les destinataires des messages envoyés par cet employé
    # On regroupe par email du destinataire et on compte le nombre de messages
    contacts = Message.objects.filter(expediteur=employee)\
        .values('destinataires__email')\
        .annotate(count=Count('id'))\
        .order_by('-count')[:20]  # Top 20

    context = {
        'employee': employee,
        'contacts': contacts,
    }
    return render(request, 'discovery/influence.html', context)

def thread(request, message_id):
    # Récupère le message principal (par son ID) ou renvoie une erreur 404
    message = get_object_or_404(Message, id=message_id)

    # Récupère toutes les réponses : messages dont le champ in_reply_to correspond au message_id du message principal
    # Attention : in_reply_to stocke le message_id (string) du parent, pas l'ID numérique
    replies = Message.objects.filter(in_reply_to=message.message_id).order_by('date')

    context = {
        'message': message,
        'replies': replies,
    }
    return render(request, 'discovery/thread.html', context)

def thread_complet(request, message_id):
    # Récupère le message de départ
    message = get_object_or_404(Message, id=message_id)

    # Trouve la racine du fil (le premier message de la conversation)
    racine = message
    while racine.in_reply_to:
        try:
            racine = Message.objects.get(message_id=racine.in_reply_to)
        except Message.DoesNotExist:
            break

    # Requête SQL récursive avec jointure pour obtenir l'email
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH RECURSIVE thread AS (
                SELECT m.id, m.message_id, m.in_reply_to, m.objet, m.date, m.corps, c.email, 1 as niveau
                FROM discovery_message m
                JOIN discovery_collaborateur c ON m.expediteur_id = c.id
                WHERE m.id = %s
                UNION ALL
                SELECT m.id, m.message_id, m.in_reply_to, m.objet, m.date, m.corps, c.email, t.niveau + 1
                FROM discovery_message m
                INNER JOIN thread t ON m.in_reply_to = t.message_id
                JOIN discovery_collaborateur c ON m.expediteur_id = c.id
            )
            SELECT id, message_id, in_reply_to, objet, date, email, corps, niveau
            FROM thread
            ORDER BY date;
        """, [racine.id])

        rows = cursor.fetchall()

    # Définir un namedtuple pour accéder aux colonnes par nom
    MessageNode = namedtuple('MessageNode', ['id', 'message_id', 'in_reply_to', 'objet', 'date', 'email', 'corps', 'niveau'])
    messages_fil = [MessageNode(*row) for row in rows]

    context = {
        'messages_fil': messages_fil,
    }
    return render(request, 'discovery/thread_complet.html', context)

def graphe(request, collaborateur_id):
    collaborateur = get_object_or_404(Collaborateur, id=collaborateur_id)

    # Messages envoyés par ce collaborateur
    messages_envoyes = Message.objects.filter(expediteur=collaborateur)

    # Destinataires les plus fréquents (personnes à qui il écrit)
    top_destinataires = Collaborateur.objects.filter(recus__in=messages_envoyes).annotate(
        nb_echanges=Count('recus')
    ).order_by('-nb_echanges')[:10]

    # Messages reçus par ce collaborateur
    messages_recus = collaborateur.recus.all()

    # Expéditeurs les plus fréquents (personnes qui lui écrivent)
    top_expediteurs = Collaborateur.objects.filter(envoyes__in=messages_recus).annotate(
        nb_echanges=Count('envoyes')
    ).order_by('-nb_echanges')[:10]

    context = {
        'collaborateur': collaborateur,
        'top_destinataires': top_destinataires,
        'top_expediteurs': top_expediteurs,
    }
    return render(request, 'discovery/graphe.html', context)


