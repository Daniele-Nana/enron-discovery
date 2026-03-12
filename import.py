import os
import email
from email.utils import parsedate_to_datetime
import django
from pathlib import Path

# Configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enron_project.settings')
django.setup()

from discovery.models import Collaborateur, Message

def parse_eml(file_path):
    """
    Extrait les métadonnées et le corps d'un fichier email.
    Retourne (from_, to, subject, date, body) ou (None, None, None, None, None) en cas d'erreur.
    """
    try:
        with open(file_path, 'rb') as f:
            msg = email.message_from_binary_file(f)
    except Exception as e:
        print(f"   ❌ Erreur lecture {file_path}: {e}")
        return None, None, None, None, None

    # Récupération des en-têtes
    from_ = msg.get('From', '').strip()
    to = msg.get('To', '').strip()
    subject = msg.get('Subject', '').strip()
    date_str = msg.get('Date', '').strip()

    # Conversion de la date
    date = None
    if date_str:
        try:
            date = parsedate_to_datetime(date_str)
        except:
            pass

    # Extraction du corps
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(errors='ignore')
                    break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(errors='ignore')
    except Exception as e:
        print(f"   ❌ Erreur extraction corps {file_path}: {e}")

    # Suppression grossière des signatures (souvent après '-- ')
    if '-- ' in body:
        body = body.split('-- ')[0]

    return from_, to, subject, date, body


def get_or_create_collaborateur(email_address):
    """
    Nettoie une adresse email (ex: "Nom <email>") et crée/récupère un collaborateur.
    Retourne l'objet Collaborateur ou None si l'adresse est invalide.
    """
    if not email_address:
        return None
    email_address = email_address.strip()
    # Extrait l'adresse entre < > si présente
    if '<' in email_address and '>' in email_address:
        start = email_address.find('<')
        end = email_address.find('>')
        if start != -1 and end != -1:
            email_address = email_address[start+1:end]
    email_address = email_address.strip().lower()
    if not email_address:
        return None
    collaborateur, created = Collaborateur.objects.get_or_create(email=email_address)
    return collaborateur


def main():
    # Dossier à importer (choisis un sous-dossier pour le test, ex: 'allen-p')
    base_dir = Path('maildir/allen-p')  # ← modifie ici pour changer la cible

    if not base_dir.exists():
        print(f"❌ Le dossier {base_dir} n'existe pas.")
        print("   Vérifie que le chemin est correct.")
        return

    print(f"📂 Démarrage de l'import depuis {base_dir.absolute()}")
    total = 0

    # Parcours récursif de tous les fichiers
    for file_path in base_dir.rglob('*'):
        if not file_path.is_file():
            continue

        print(f"\n🔍 Fichier trouvé : {file_path}")

        from_, to, subject, date, body = parse_eml(file_path)
        if not from_:
            print("   ⚠️ Ignoré : pas d'expéditeur")
            continue
        if not date:
            print("   ⚠️ Ignoré : date invalide")
            continue

        expediteur = get_or_create_collaborateur(from_)
        if not expediteur:
            print(f"   ⚠️ Expéditeur invalide: {from_}")
            continue

        # Identifiant unique basé sur le chemin relatif (pour éviter les doublons)
        message_id = str(file_path.relative_to(base_dir.parent))  # utilise le chemin complet relatif à maildir
        print(f"   ✅ Expéditeur : {expediteur.email}")
        print(f"   📧 Sujet : {subject[:50]}..." if subject else "   📧 Sujet : (vide)")
        print(f"   📅 Date : {date}")

        try:
            msg = Message.objects.create(
                message_id=message_id,
                date=date,
                objet=subject[:500],  # limite de longueur
                corps=body,
                expediteur=expediteur
            )
        except Exception as e:
            print(f"   ❌ Erreur création message {message_id}: {e}")
            continue

        # Ajout des destinataires
        if to:
            dest_count = 0
            for addr in to.split(','):
                dest = get_or_create_collaborateur(addr)
                if dest:
                    msg.destinataires.add(dest)
                    dest_count += 1
            print(f"   👥 {dest_count} destinataires ajoutés")

        total += 1
        if total % 10 == 0:
            print(f"\n📊 {total} emails importés jusqu'à présent...\n")

    print(f"\n✅ Import terminé. Total : {total} emails.")


if __name__ == "__main__":
    main()