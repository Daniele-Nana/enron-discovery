from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from .models import Message, Collaborateur, Folder
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Min, Max, Avg, Q, F
from django.core.paginator import Paginator
from django.db import connection
from collections import namedtuple, Counter, defaultdict
from django.db.models.functions import TruncMonth, ExtractWeekDay, ExtractHour, ExtractYear, TruncDay, TruncWeek
from datetime import datetime, timedelta
from django.core.cache import cache
from django.http import JsonResponse
import re

def dashboard(request):
    total_messages = Message.objects.count()
    total_collaborateurs = Collaborateur.objects.count()
    premier_email = Message.objects.aggregate(Min('date'))['date__min']
    dernier_email = Message.objects.filter(date__lte=timezone.now()).aggregate(Max('date'))['date__max']
    total_threads = Message.objects.filter(in_reply_to__isnull=False).count()

    if premier_email and dernier_email:
        period_days = (dernier_email - premier_email).days
    else:
        period_days = 0

    cache_key = 'dashboard_stats'
    cached_data = cache.get(cache_key)

    if cached_data:
        top_senders = cached_data['top_senders']
        top_recipients = cached_data['top_recipients']
        mois_labels = cached_data['mois_labels']
        mois_data = cached_data['mois_data']
        avg_per_day = cached_data['avg_per_day']
        top_heures = cached_data['top_heures']
        annees = cached_data['annees']
        top_weekdays = cached_data.get('top_weekdays', [])
        avg_per_week = cached_data.get('avg_per_week', 0)
        avg_per_month = cached_data.get('avg_per_month', 0)
        avg_per_year = cached_data.get('avg_per_year', 0)
        distinct_days = cached_data.get('distinct_days', 0)
    else:
        # --- Top expéditeurs ---
        top_senders = list(Collaborateur.objects.annotate(
            nb_envoyes=Count('envoyes')
        ).order_by('-nb_envoyes')[:10])

        # --- Top destinataires ---
        top_recipients = list(Collaborateur.objects.annotate(
            nb_recus=Count('recus')
        ).order_by('-nb_recus')[:10])

        # --- Graphique mensuel ---
        mois_stats = Message.objects.annotate(
            mois=TruncMonth('date')
        ).values('mois').annotate(
            count=Count('id')
        ).order_by('mois')
        mois_labels = [m['mois'].strftime('%Y-%m') for m in mois_stats if m['mois']]
        mois_data = [m['count'] for m in mois_stats]

        # --- Moyenne par jour ---
        if premier_email and dernier_email:
            total_days = (dernier_email - premier_email).days
            avg_per_day = round(total_messages / total_days) if total_days > 0 else 0
        else:
            avg_per_day = 0

        # --- Heures actives ---
        top_heures = list(Message.objects.annotate(
            heure=ExtractHour('date')
        ).values('heure').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        # --- Années distinctes ---
        annees = list(Message.objects.annotate(
            annee=ExtractYear('date')
        ).values_list('annee', flat=True).distinct().order_by('-annee'))

        # --- Jours de la semaine les plus actifs ---
        jour_semaine_stats = Message.objects.annotate(
            jour_semaine=ExtractWeekDay('date')
        ).values('jour_semaine').annotate(
            cnt=Count('id')
        ).order_by('-cnt')[:5]

        jours_map = {
            1: 'Dimanche', 2: 'Lundi', 3: 'Mardi', 4: 'Mercredi',
            5: 'Jeudi', 6: 'Vendredi', 7: 'Samedi'
        }
        top_weekdays = [
            {'name': jours_map.get(stat['jour_semaine'], 'Inconnu'), 'count': stat['cnt']}
            for stat in jour_semaine_stats
        ]

        # --- Moyenne par semaine ---
        distinct_weeks = Message.objects.dates('date', 'week').count()
        avg_per_week = round(total_messages / distinct_weeks) if distinct_weeks else 0

        # --- Moyenne par mois ---
        distinct_months = mois_stats.count()
        avg_per_month = round(total_messages / distinct_months) if distinct_months else 0

        # --- Moyenne par an ---
        distinct_years = len(annees)
        avg_per_year = round(total_messages / distinct_years) if distinct_years else 0

        # --- Nombre de jours distincts avec emails ---
        distinct_days = Message.objects.dates('date', 'day').count()

        # Mise en cache
        cache.set(cache_key, {
            'top_senders': top_senders,
            'top_recipients': top_recipients,
            'mois_labels': mois_labels,
            'mois_data': mois_data,
            'avg_per_day': avg_per_day,
            'top_heures': top_heures,
            'annees': annees,
            'top_weekdays': top_weekdays,
            'avg_per_week': avg_per_week,
            'avg_per_month': avg_per_month,
            'avg_per_year': avg_per_year,
            'distinct_days': distinct_days,
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
        'top_weekdays': top_weekdays,
        'avg_per_week': avg_per_week,
        'avg_per_month': avg_per_month,
        'avg_per_year': avg_per_year,
        'distinct_days': distinct_days,
        'period_days': period_days,
    }
    return render(request, 'discovery/dashboard.html', context)

def recherche(request):
    query = request.GET.get('q', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    expediteur_id = request.GET.get('expediteur', '')
    destinataire_id = request.GET.get('destinataire', '')
    sort = request.GET.get('sort', '-date')  # nouveau paramètre

    messages = Message.objects.prefetch_related('destinataires').select_related('expediteur').all()

    if query:
        # Utiliser SearchVector pour la recherche plein texte
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
        search_vector = SearchVector('objet', weight='A') + SearchVector('corps', weight='B')
        search_query = SearchQuery(query, search_type='websearch')
        messages = messages.annotate(
            rank=SearchRank(search_vector, search_query)
        ).filter(search_vector=search_query)

    if date_debut:
        try:
            start_date = datetime.strptime(date_debut, '%Y-%m-%d')
            messages = messages.filter(date__gte=start_date)
        except ValueError:
            pass

    if date_fin:
        try:
            end_date = datetime.strptime(date_fin, '%Y-%m-%d') + timedelta(days=1)
            messages = messages.filter(date__lt=end_date)
        except ValueError:
            pass

    if expediteur_id and expediteur_id.isdigit():
        messages = messages.filter(expediteur_id=int(expediteur_id))
    if destinataire_id and destinataire_id.isdigit():
        messages = messages.filter(destinataires__id=int(destinataire_id))

    # Application du tri
    if sort == 'relevance' and query:
        messages = messages.order_by('-rank')
    elif sort == 'date':
        messages = messages.order_by('date')
    else:  # par défaut : -date (le plus récent en premier)
        messages = messages.order_by('-date')

    paginator = Paginator(messages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Récupération des objets sélectionnés pour la pré‑sélection dans le template
    selected_expediteur = None
    if expediteur_id and expediteur_id.isdigit():
        try:
            selected_expediteur = Collaborateur.objects.get(pk=expediteur_id)
        except Collaborateur.DoesNotExist:
            pass

    selected_destinataire = None
    if destinataire_id and destinataire_id.isdigit():
        try:
            selected_destinataire = Collaborateur.objects.get(pk=destinataire_id)
        except Collaborateur.DoesNotExist:
            pass

    # Listes complètes (optionnelles, peuvent être supprimées si vous utilisez AJAX)
    expediteurs = Collaborateur.objects.filter(envoyes__isnull=False).distinct().order_by('email')
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
        'selected_expediteur': selected_expediteur,
        'selected_destinataire': selected_destinataire,
        'sort': sort,  # transmettre au template pour conserver le choix
    }
    return render(request, 'discovery/recherche.html', context)

def influence(request, employee_id):
    collaborateur = get_object_or_404(Collaborateur, id=employee_id)
    thread_id = request.GET.get('thread_id')  # récupère l'ID du message source

    sent_count = Message.objects.filter(expediteur=collaborateur).count()
    received_count = Message.objects.filter(destinataires=collaborateur).count()

    top_destinataires = Collaborateur.objects.filter(
        recus__expediteur=collaborateur
    ).annotate(
        nb_echanges=Count('recus')
    ).order_by('-nb_echanges')[:10]

    top_expediteurs = Collaborateur.objects.filter(
        envoyes__destinataires=collaborateur
    ).annotate(
        nb_echanges=Count('envoyes')
    ).order_by('-nb_echanges')[:10]

    context = {
        'collaborateur': collaborateur,
        'sent_count': sent_count,
        'received_count': received_count,
        'top_destinataires': top_destinataires,
        'top_expediteurs': top_expediteurs,
        'thread_id': thread_id,  # nouveau
    }
    return render(request, 'discovery/influence.html', context)

def thread(request, message_id):
    message = get_object_or_404(Message.objects.select_related('expediteur'), id=message_id)
    folder_id = request.GET.get('folder_id')

    previous_message = Message.objects.filter(date__lt=message.date).order_by('-date').first()
    next_message = Message.objects.filter(date__gt=message.date).order_by('date').first()

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
        'folder_id': folder_id,
    }
    return render(request, 'discovery/thread.html', context)

def thread_complet(request, message_id):
    message = get_object_or_404(Message, id=message_id)

    racine = message
    while racine.in_reply_to:
        try:
            racine = Message.objects.get(message_id=racine.in_reply_to)
        except Message.DoesNotExist:
            break

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH RECURSIVE thread AS (
                SELECT m.id, m.message_id, m.in_reply_to, m.objet, m.date, m.corps,
                       c.email, c.id as expediteur_id, 1 as niveau
                FROM discovery_message m
                JOIN discovery_collaborateur c ON m.expediteur_id = c.id
                WHERE m.id = %s
                UNION ALL
                SELECT m.id, m.message_id, m.in_reply_to, m.objet, m.date, m.corps,
                       c.email, c.id as expediteur_id, t.niveau + 1
                FROM discovery_message m
                INNER JOIN thread t ON m.in_reply_to = t.message_id
                JOIN discovery_collaborateur c ON m.expediteur_id = c.id
            )
            SELECT id, message_id, in_reply_to, objet, date, email, corps, niveau, expediteur_id
            FROM thread
            ORDER BY date;
        """, [racine.id])

        rows = cursor.fetchall()

    # Créer une liste de dictionnaires pour ajouter les destinataires
    MessageNode = namedtuple('MessageNode', ['id', 'message_id', 'in_reply_to', 'objet', 'date', 'email', 'corps', 'niveau', 'expediteur_id'])
    messages_fil = [MessageNode(*row)._asdict() for row in rows]

    # Récupérer les destinataires pour tous ces messages
    message_ids = [m['id'] for m in messages_fil]
    if message_ids:
        dest_query = Message.destinataires.through.objects.filter(
            message_id__in=message_ids
        ).select_related('collaborateur')
        dest_par_msg = defaultdict(list)
        for dest in dest_query:
            dest_par_msg[dest.message_id].append(dest.collaborateur)

        for msg in messages_fil:
            msg['destinataires'] = dest_par_msg.get(msg['id'], [])
    else:
        for msg in messages_fil:
            msg['destinataires'] = []

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
    max_nodes = int(request.GET.get('max_nodes', 80))  # réduit à 80 pour de meilleures performances
    cache_key = f"graphe_data_{min_echanges}_{max_nodes}"
    data = cache.get(cache_key)
    if data:
        return JsonResponse(data)

    # 1. Récupérer les collaborateurs les plus actifs
    collaborateurs = Collaborateur.objects.annotate(
        total=Count('envoyes') + Count('recus')
    ).filter(total__gt=0).order_by('-total')[:max_nodes]
    collab_ids = [c.id for c in collaborateurs]

    if not collab_ids:
        return JsonResponse({'nodes': [], 'edges': []})

    # 2. Construire les nœuds
    nodes = [{
        'id': c.id,
        'label': c.email,
        'title': f"{c.email} (total échanges: {c.total})",
        'value': c.total
    } for c in collaborateurs]

    # 3. Requête SQL brute avec les IDs en paramètres
    # On construit la liste des placeholders pour les IDs
    ids_placeholder = ','.join(['%s'] * len(collab_ids))
    query = f"""
        SELECT m.expediteur_id, dmd.collaborateur_id, COUNT(*) as nb
        FROM discovery_message_destinataires dmd
        INNER JOIN discovery_message m ON dmd.message_id = m.id
        WHERE m.expediteur_id IN ({ids_placeholder})
          AND dmd.collaborateur_id IN ({ids_placeholder})
          AND m.expediteur_id != dmd.collaborateur_id
        GROUP BY m.expediteur_id, dmd.collaborateur_id
        HAVING COUNT(*) >= %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, collab_ids + collab_ids + [min_echanges])
        rows = cursor.fetchall()

    edges = [{
        'from': row[0],
        'to': row[1],
        'value': row[2],
        'title': f"{row[2]} échanges"
    } for row in rows]

    result = {'nodes': nodes, 'edges': edges}
    cache.set(cache_key, result, 3600)  # cache 1 heure
    return JsonResponse(result)

def graphe_interactif(request):
    return render(request, 'discovery/graphe_interactif.html')

STOP_WORDS = set("""
a about above after again against all am an and any are aren't as at be because been before being below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further fwd had hadn't has hasn't have haven't having he he'd he'll he's here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves
""".split())

def wordcloud_data(request):
    # Clé de cache unique
    cache_key = 'wordcloud_data'
    data = cache.get(cache_key)
    
    if data is None:
        # Calcul long (effectué uniquement si le cache est vide)
        subjects = Message.objects.exclude(objet__isnull=True).exclude(objet='').values_list('objet', flat=True)
        text = ' '.join(subjects)
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOP_WORDS]
        counter = Counter(words)
        top_words = counter.most_common(40)
        data = [{'word': w, 'weight': c} for w, c in top_words]
        
        # Stocker pour 1 heure (3600 secondes)
        cache.set(cache_key, data, 3600)
    
    return JsonResponse(data, safe=False)

def explorateur_dossiers(request, collaborateur_id):
    collaborateur = get_object_or_404(Collaborateur, id=collaborateur_id)
    thread_id = request.GET.get('thread_id')  # pour revenir au fil

    folders = Folder.objects.filter(
        messages__message__expediteur=collaborateur
    ).annotate(
        nb_emails=Count('messages__message', filter=Q(messages__message__expediteur=collaborateur))
    ).order_by('path')

    context = {
        'collaborateur': collaborateur,
        'folders': folders,
        'thread_id': thread_id,
    }
    return render(request, 'discovery/explorateur_dossiers.html', context)

def autocomplete_expediteurs(request):
    term = request.GET.get('q', '')
    expediteurs = Collaborateur.objects.filter(envoyes__isnull=False).distinct()
    if term:
        expediteurs = expediteurs.filter(email__icontains=term)
    results = [{'id': e.id, 'text': e.email} for e in expediteurs[:20]]
    return JsonResponse({'results': results})

def autocomplete_destinataires(request):
    term = request.GET.get('q', '')
    destinataires = Collaborateur.objects.filter(recus__isnull=False).distinct()
    if term:
        destinataires = destinataires.filter(email__icontains=term)
    results = [{'id': d.id, 'text': d.email} for d in destinataires[:20]]
    return JsonResponse({'results': results})
 
def tous_emails_collaborateur(request, collaborateur_id):
    collaborateur = get_object_or_404(Collaborateur, pk=collaborateur_id)

    # Récupérer le numéro de page pour la clé de cache
    page = request.GET.get('page', 1)
    cache_key = f"tous_emails_{collaborateur_id}_{page}"
    page_obj = cache.get(cache_key)

    if page_obj is None:
        # Requête optimisée avec select_related et prefetch_related
        messages = Message.objects.filter(
            Q(expediteur=collaborateur) | Q(destinataires=collaborateur)
        ).distinct().select_related('expediteur').prefetch_related('destinataires').order_by('-date')

        paginator = Paginator(messages, 20)
        page_obj = paginator.get_page(page)

        # Mettre en cache pour 15 minutes (900 secondes)
        cache.set(cache_key, page_obj, 900)

    context = {
        'collaborateur': collaborateur,
        'page_obj': page_obj,
    }
    return render(request, 'discovery/tous_emails.html', context)

def contenu_dossier(request, collaborateur_id, folder_id):
    collaborateur = get_object_or_404(Collaborateur, id=collaborateur_id)
    folder = get_object_or_404(Folder, id=folder_id)
    messages = Message.objects.filter(
        expediteur=collaborateur,
        folders__folder=folder
    ).select_related('expediteur').prefetch_related('destinataires').order_by('-date')
    paginator = Paginator(messages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'collaborateur': collaborateur,
        'folder': folder,
        'page_obj': page_obj,
    }
    return render(request, 'discovery/contenu_dossier.html', context)

def graphe_utilisateur(request, collaborateur_id):
    collaborateur = get_object_or_404(Collaborateur, id=collaborateur_id)

    # Récupérer les collaborateurs avec lesquels il interagit le plus
    # (destinataires et expéditeurs)
    destinataires = Collaborateur.objects.filter(
        recus__expediteur=collaborateur
    ).annotate(
        nb_echanges=Count('recus')
    ).order_by('-nb_echanges')[:20]

    expediteurs = Collaborateur.objects.filter(
        envoyes__destinataires=collaborateur
    ).annotate(
        nb_echanges=Count('envoyes')
    ).order_by('-nb_echanges')[:20]

    # Fusionner les deux listes (sans doublons)
    connexions = {}
    for d in destinataires:
        connexions[d.id] = {'email': d.email, 'nb': d.nb_echanges, 'type': 'destinataire'}
    for e in expediteurs:
        if e.id in connexions:
            connexions[e.id]['nb'] += e.nb_echanges
            connexions[e.id]['type'] = 'mutuel'
        else:
            connexions[e.id] = {'email': e.email, 'nb': e.nb_echanges, 'type': 'expediteur'}

    # Trier par nombre d'échanges
    connexions_list = sorted(connexions.items(), key=lambda x: x[1]['nb'], reverse=True)[:20]

    # Construire les nœuds (collaborateur central + connexions)
    nodes = [{'id': collaborateur.id, 'label': collaborateur.email, 'group': 'central'}]
    for c_id, data in connexions_list:
        nodes.append({'id': c_id, 'label': data['email'], 'group': data['type']})

    # Construire les arêtes
    edges = []
    for c_id, data in connexions_list:
        edges.append({'from': collaborateur.id, 'to': c_id, 'value': data['nb'], 'title': f"{data['nb']} échanges"})

    # Passer les données au template
    context = {
        'collaborateur': collaborateur,
        'nodes': nodes,
        'edges': edges,
    }
    return render(request, 'discovery/graphe_utilisateur.html', context)
