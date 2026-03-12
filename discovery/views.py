from django.shortcuts import render
from .models import Message

def dashboard(request):
    nb = Message.objects.count()
    return render(request, 'discovery/dashboard.html', {'nb': nb})
