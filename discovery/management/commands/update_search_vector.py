from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from discovery.models import Message

class Command(BaseCommand):
    help = 'Met à jour le champ search_vector pour tous les messages'

    def handle(self, *args, **options):
        # Mise à jour en une seule requête SQL
        Message.objects.update(search_vector=SearchVector('corps', 'objet'))
        self.stdout.write(self.style.SUCCESS('Search vector mis à jour avec succès.'))