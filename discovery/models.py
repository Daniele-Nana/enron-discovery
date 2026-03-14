from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

class Collaborateur(models.Model):
    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.email

class Message(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    date = models.DateTimeField()
    objet = models.CharField(max_length=500)
    corps = models.TextField()
    expediteur = models.ForeignKey(Collaborateur, on_delete=models.CASCADE, related_name='envoyes')
    destinataires = models.ManyToManyField(Collaborateur, related_name='recus')
    in_reply_to = models.CharField(max_length=255, blank=True, null=True)
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['in_reply_to']),
            GinIndex(fields=['search_vector']),
        ]

class Folder(models.Model):
    name = models.CharField(max_length=255)
    path = models.TextField(unique=True)          # chemin complet relatif
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.path

class MessageFolder(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='folders')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='messages')

    class Meta:
        unique_together = ('message', 'folder')

