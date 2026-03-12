from django.db import models

class Collaborateur(models.Model):
    email = models.EmailField(unique=True)
    nom = models.CharField(max_length=200, blank=True)

class Message(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    date = models.DateTimeField()
    objet = models.CharField(max_length=500)
    corps = models.TextField()
    expediteur = models.ForeignKey(Collaborateur, on_delete=models.CASCADE, related_name='envoyes')
    destinataires = models.ManyToManyField(Collaborateur, related_name='recus')
    in_reply_to = models.CharField(max_length=255, blank=True, null=True)
