from django.test import TestCase
from django.urls import reverse
from .models import Collaborateur, Message
from datetime import datetime

class CollaborateurModelTest(TestCase):
    def test_creation_collaborateur(self):
        c = Collaborateur.objects.create(email="test@test.com", nom="Test")
        self.assertEqual(c.email, "test@test.com")
        self.assertEqual(str(c), "test@test.com")

class MessageModelTest(TestCase):
    def setUp(self):
        self.exp = Collaborateur.objects.create(email="exp@test.com")
        self.dest = Collaborateur.objects.create(email="dest@test.com")

    def test_creation_message(self):
        msg = Message.objects.create(
            message_id="123",
            date=datetime.now(),
            objet="Objet",
            corps="Corps",
            expediteur=self.exp
        )
        msg.destinataires.add(self.dest)
        self.assertEqual(msg.objet, "Objet")
        self.assertEqual(msg.destinataires.count(), 1)

class ViewTest(TestCase):
    def setUp(self):
        self.exp = Collaborateur.objects.create(email="exp@test.com")
        Message.objects.create(
            message_id="123",
            date=datetime.now(),
            objet="Test",
            corps="Corps",
            expediteur=self.exp
        )

    def test_dashboard_view(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_recherche_view(self):
        response = self.client.get(reverse('recherche'))
        self.assertEqual(response.status_code, 200)