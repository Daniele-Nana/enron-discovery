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
from django.db.models import Q
from django.core.cache import cache
from django.db.models.functions import ExtractHour
from django.db.models import Avg

def dashboard(request):
    # Données mises en cache
    top_senders = cache.get('top_senders')
    if not top_senders:
        top_senders = list(Collaborateur.objects.annotate(nb_envoyes=Count('envoyes')).order_by('-nb_envoyes')[:10])
        cache.set('top_senders', top_senders, 3600)  # 1 heure

    # Le reste des calculs (non mis en cache car changent peu)
    total_messages = Message.objects.count()
    total_collaborateurs = Collaborateur.objects.count()
    premier_email = Message.objects.aggregate(Min('date'))['date__min']
    dernier_email = Message.objects.filter(date__lte=timezone.now()).aggregate(Max('date'))['date__max']
    total_threads = Message.objects.filter(in_reply_to__isnull=False).count()
    
    # Statistiques mensuelles
    mois_stats = Message.objects.annotate(mois=TruncMonth('date')).values('mois').annotate(count=Count('id')).order_by('mois')
    mois_labels = [m['mois'].strftime('%Y-%m') for m in mois_stats if m['mois']]
    mois_data = [m['count'] for m in mois_stats]
    
    annees = Message.objects.annotate(annee=ExtractYear('date')).values_list('annee', flat=True).distinct().order_by('-annee')

     # Moyenne d'emails par jour
    if premier_email and dernier_email:
        total_days = (dernier_email - premier_email).days
        avg_per_day = total_messages / total_days if total_days > 0 else 0
    else:
        avg_per_day = 0

    # Heures les plus actives
    top_heures = Message.objects.annotate(heure=ExtractHour('date')).values('heure').annotate(count=Count('id')).order_by('-count')[:5]

    
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
        'avg_per_day': round(avg_per_day, 2),
        'top_heures': top_heures,
    }
    return render(request, 'discovery/dashboard.html', context)

def recherche(request):
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    expediteur_id = request.GET.get('expediteur', '')

    messages = Message.objects.all().order_by('-date')

    if query:
    # Recherche plein texte sur le champ search_vector (objet + corps)
        full_text = Q(search_vector=SearchQuery(query))
    # Recherche sur l'email de l'expéditeur (insensible à la casse)
        expediteur_match = Q(expediteur__email__icontains=query)
    # Recherche sur les emails des destinataires (insensible à la casse)
        destinataire_match = Q(destinataires__email__icontains=query)
    # Combinaison avec OR
        messages = messages.filter(full_text | expediteur_match | destinataire_match).distinct()

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
    collaborateur = get_object_or_404(Collaborateur, id=employee_id)

    # Destinataires les plus fréquents (personnes à qui il écrit)
    top_destinataires = Collaborateur.objects.filter(
        recus__expediteur=collaborateur  # messages reçus par le destinataire ET envoyés par collaborateur
    ).annotate(
        nb_echanges=Count('recus')
    ).order_by('-nb_echanges')[:10]

    # Expéditeurs les plus fréquents (personnes qui lui écrivent)
    top_expediteurs = Collaborateur.objects.filter(
        envoyes__destinataires=collaborateur  # messages envoyés par l'expéditeur ET reçus par collaborateur
    ).annotate(
        nb_echanges=Count('envoyes')
    ).order_by('-nb_echanges')[:10]

    context = {
        'collaborateur': collaborateur,
        'top_destinataires': top_destinataires,
        'top_expediteurs': top_expediteurs,
    }
    return render(request, 'discovery/influence.html', context)

def thread(request, message_id):
    # Récupère le message principal avec l'expéditeur (1 requête)
    message = get_object_or_404(Message.objects.select_related('expediteur'), id=message_id)

    def get_replies(msg, niveau=1):
        # Récupère les réponses directes avec leurs expéditeurs (optimisé)
        replies = Message.objects.select_related('expediteur').filter(in_reply_to=msg.message_id).order_by('date')
        result = []
        for reply in replies:
            reply.niveau = niveau
            result.append(reply)
            # Appel récursif pour les sous-réponses
            result.extend(get_replies(reply, niveau + 1))
        return result

    replies = get_replies(message)

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


