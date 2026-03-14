from django.contrib.postgres.search import SearchVector, SearchQuery
from .models import Message, Collaborateur, Folder
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
from django.db.models import F
from django.http import JsonResponse
from collections import Counter
import re

def dashboard(request):
    # Statistiques rapides (pas de cache nécessaire)
    total_messages = Message.objects.count()
    total_collaborateurs = Collaborateur.objects.count()
    premier_email = Message.objects.aggregate(Min('date'))['date__min']
    dernier_email = Message.objects.filter(date__lte=timezone.now()).aggregate(Max('date'))['date__max']
    total_threads = Message.objects.filter(in_reply_to__isnull=False).count()

    # Données mises en cache
    cache_key = 'dashboard_stats'
    cached_data = cache.get(cache_key)
    if cached_data:
        top_senders = cached_data['top_senders']
        top_recipients = cached_data['top_recipients']   # ← ajout
        mois_labels = cached_data['mois_labels']
        mois_data = cached_data['mois_data']
        avg_per_day = cached_data['avg_per_day']
        top_heures = cached_data['top_heures']
        annees = cached_data['annees']
    else:
        # Top 10 expéditeurs
        top_senders = list(Collaborateur.objects.annotate(
            nb_envoyes=Count('envoyes')
        ).order_by('-nb_envoyes')[:10])

        # Top 10 destinataires (nouveau)
        top_recipients = list(Collaborateur.objects.annotate(
            nb_recus=Count('recus')
        ).order_by('-nb_recus')[:10])

        # Statistiques mensuelles
        mois_stats = Message.objects.annotate(
            mois=TruncMonth('date')
        ).values('mois').annotate(
            count=Count('id')
        ).order_by('mois')
        mois_labels = [m['mois'].strftime('%Y-%m') for m in mois_stats if m['mois']]
        mois_data = [m['count'] for m in mois_stats]

        # Moyenne par jour
        if premier_email and dernier_email:
            total_days = (dernier_email - premier_email).days
            avg_per_day = total_messages / total_days if total_days > 0 else 0
        else:
            avg_per_day = 0

        # Heures les plus actives
        top_heures = list(Message.objects.annotate(
            heure=ExtractHour('date')
        ).values('heure').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        # Années distinctes
        annees = list(Message.objects.annotate(
            annee=ExtractYear('date')
        ).values_list('annee', flat=True).distinct().order_by('-annee'))

        # Mise en cache pour 1 heure
        cache.set(cache_key, {
            'top_senders': top_senders,
            'top_recipients': top_recipients,   # ← ajout
            'mois_labels': mois_labels,
            'mois_data': mois_data,
            'avg_per_day': avg_per_day,
            'top_heures': top_heures,
            'annees': annees,
        }, 3600)

    context = {
        'total_messages': total_messages,
        'total_collaborateurs': total_collaborateurs,
        'premier_email': premier_email,
        'dernier_email': dernier_email,
        'total_threads': total_threads,
        'top_senders': top_senders,
        'top_recipients': top_recipients,
        'mois_labels': mois_labels,
        'mois_data': mois_data,
        'avg_per_day': avg_per_day,
        'top_heures': top_heures,
        'annees': annees,
    }
    return render(request, 'discovery/dashboard.html', context)

def recherche(request):
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    expediteur_id = request.GET.get('expediteur', '')
    destinataire_id = request.GET.get('destinataire', '')  # changement

    messages = Message.objects.all().order_by('-date')

    if query:
        messages = messages.filter(search_vector=SearchQuery(query, search_type='websearch'))

    if date_debut:
        messages = messages.filter(date__gte=date_debut)
    if date_fin:
        messages = messages.filter(date__lte=date_fin)
    if expediteur_id and expediteur_id.isdigit():
        messages = messages.filter(expediteur_id=int(expediteur_id))
    if destinataire_id and destinataire_id.isdigit():
        messages = messages.filter(destinataires__id=int(destinataire_id))

    paginator = Paginator(messages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Liste des expéditeurs (ceux qui ont envoyé au moins un message)
    expediteurs = Collaborateur.objects.filter(envoyes__isnull=False).distinct().order_by('email')
    # Liste des destinataires (ceux qui ont reçu au moins un message)
    destinataires = Collaborateur.objects.filter(recus__isnull=False).distinct().order_by('email')

    context = {
        'page_obj': page_obj,
        'query': query,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'expediteur_id': int(expediteur_id) if expediteur_id and expediteur_id.isdigit() else None,
        'destinataire_id': int(destinataire_id) if destinataire_id and destinataire_id.isdigit() else None,
        'expediteurs': expediteurs,
        'destinataires': destinataires,
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
    # Récupère le message principal avec l'expéditeur
    message = get_object_or_404(Message.objects.select_related('expediteur'), id=message_id)

    # Messages précédent et suivant (basés sur la date)
    previous_message = Message.objects.filter(date__lt=message.date).order_by('-date').first()
    next_message = Message.objects.filter(date__gt=message.date).order_by('date').first()

    # Fonction récursive pour obtenir les réponses avec indentation
    def get_replies(msg, niveau=1):
        replies = Message.objects.select_related('expediteur').filter(in_reply_to=msg.message_id).order_by('date')
        result = []
        for reply in replies:
            reply.niveau = niveau
            result.append(reply)
            result.extend(get_replies(reply, niveau + 1))
        return result

    replies = get_replies(message)

    context = {
        'message': message,
        'replies': replies,
        'previous_message': previous_message,
        'next_message': next_message,
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

def graphe_data(request):
    min_echanges = int(request.GET.get('min', 2))
    max_nodes = int(request.GET.get('max_nodes', 200))

    cache_key = f"graphe_data_{min_echanges}_{max_nodes}"
    data = cache.get(cache_key)
    if data:
        return JsonResponse(data)

    # Récupérer les collaborateurs les plus actifs
    collaborateurs = Collaborateur.objects.annotate(
        total=Count('envoyes') + Count('recus')
    ).filter(total__gt=0).order_by('-total')[:max_nodes]

    collab_ids = set(c.id for c in collaborateurs)
    nodes = []
    for c in collaborateurs:
        nodes.append({
            'id': c.id,
            'label': c.email,
            'title': f"{c.email} (total échanges: {c.total})",
            'value': c.total,
        })

    # Compter les échanges entre ces collaborateurs
    echanges = Message.objects.filter(
        expediteur__in=collab_ids,
        destinataires__in=collab_ids
    ).exclude(
        expediteur=F('destinataires')
    ).values('expediteur_id', 'destinataires').annotate(
        count=Count('id')
    ).filter(count__gte=min_echanges)

    edges = []
    for e in echanges:
        edges.append({
            'from': e['expediteur_id'],
            'to': e['destinataires'],  # ← 'destinataires' donne l'ID du destinataire
            'value': e['count'],
            'title': f"{e['count']} échanges",
        })

    data = {'nodes': nodes, 'edges': edges}
    cache.set(cache_key, data, 3600)
    return JsonResponse(data)

def graphe_interactif(request):
    return render(request, 'discovery/graphe_interactif.html')

STOP_WORDS = set("""
a about above after again against all am an and any are aren't as at be because been before being below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves
""".split())

def wordcloud_data(request):
    # Récupérer tous les objets non vides
    subjects = Message.objects.exclude(objet__isnull=True).exclude(objet='').values_list('objet', flat=True)
    
    # Concaténer
    text = ' '.join(subjects)
    
    # Extraire les mots de 3 lettres ou plus
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    
    # Filtrer les stop words
    words = [w for w in words if w not in STOP_WORDS]
    
    # Compter
    counter = Counter(words)
    
    # Garder les 40 mots les plus fréquents (vous pouvez ajuster)
    top_words = counter.most_common(40)
    
    # Formater
    data = [{'word': w, 'weight': c} for w, c in top_words]
    
    return JsonResponse(data, safe=False)

def explorateur_dossiers(request, collaborateur_id):
    collaborateur = get_object_or_404(Collaborateur, id=collaborateur_id)
    # Récupère tous les dossiers où ce collaborateur a envoyé des messages
    folders = Folder.objects.filter(
        messages__message__expediteur=collaborateur
    ).annotate(
        nb_emails=Count('messages__message', filter=Q(messages__message__expediteur=collaborateur))
    ).order_by('path')

    context = {
        'collaborateur': collaborateur,
        'folders': folders,
    }
    return render(request, 'discovery/explorateur_dossiers.html', context) 