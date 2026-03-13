import os
import email
from email.utils import parsedate_to_datetime
import django
from pathlib import Path
import dateutil.parser  # Nécessite : pip install python-dateutil

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enron_project.settings')
django.setup()

from discovery.models import Collaborateur, Message

def parse_eml(path):
    with open(path, 'rb') as f:
        msg = email.message_from_binary_file(f)

    def get_header_str(header_name):
        header = msg.get(header_name, '')
        if header:
            if hasattr(header, 'decode'):
                try:
                    return header.decode()
                except:
                    return str(header)
            else:
                return str(header)
        return ''

    # --- Message-ID ---
    message_id = get_header_str('Message-ID').strip('<>')
    if not message_id:
        # Fallback : chemin relatif unique
        rel_path = path.relative_to(Path.cwd())
        message_id = str(rel_path).replace('\\', '/')

    # --- In-Reply-To (nouveau) ---
    in_reply_to = get_header_str('In-Reply-To').strip('<>')
    if not in_reply_to:
        in_reply_to = None

    # --- En-têtes courants ---
    from_ = get_header_str('From')
    to = get_header_str('To')
    cc = get_header_str('Cc')
    bcc = get_header_str('Bcc')
    subject = get_header_str('Subject')
    date_str = get_header_str('Date')

    # --- Parsing robuste de la date ---
    date = None
    if date_str:
        # Essai avec le format standard des emails
        try:
            date = parsedate_to_datetime(date_str)
        except:
            pass
        if date is None:
            try:
                # Essai avec dateutil (très tolérant)
                date = dateutil.parser.parse(date_str)
            except:
                pass

    # Filtre les dates aberrantes (le corpus Enron est de 1998-2002)
    if date is not None:
        if date.year < 1990 or date.year > 2005:
            date = None   # on ignore les dates trop éloignées

    # --- Extraction du corps texte ---
    body = ""
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

    # Suppression de la signature classique "-- "
    if '-- ' in body:
        body = body.split('-- ')[0]

    return message_id, in_reply_to, from_, to, cc, bcc, subject, date, body

def main():
    base = Path('maildir')  # ou 'test_import' pour un échantillon
    count = 0
    errors = 0

    for path in base.rglob('*'):
        if path.is_file():
            try:
                # Récupération des données avec le nouveau champ in_reply_to
                message_id, in_reply_to, from_, to, cc, bcc, subject, date, body = parse_eml(path)

                # On ignore les messages sans expéditeur ou sans date valide
                if not from_ or not date:
                    errors += 1
                    continue

                # Évite les doublons (déjà présents dans la base)
                if Message.objects.filter(message_id=message_id).exists():
                    errors += 1
                    continue

                # Création ou récupération de l'expéditeur
                expediteur, _ = Collaborateur.objects.get_or_create(email=from_)

                # Création du message avec in_reply_to
                msg = Message.objects.create(
                    message_id=message_id,
                    in_reply_to=in_reply_to,   # ← AJOUT IMPORTANT
                    date=date,
                    objet=subject,
                    corps=body,
                    expediteur=expediteur
                )

                # Ajout des destinataires (to, cc, bcc)
                def add_recipients(addr_str, type_):
                    if addr_str:
                        for adr in addr_str.split(','):
                            adr = adr.strip()
                            if adr:
                                dest, _ = Collaborateur.objects.get_or_create(email=adr)
                                msg.destinataires.add(dest)

                add_recipients(to, 'to')
                add_recipients(cc, 'cc')
                add_recipients(bcc, 'bcc')

                count += 1
                if count % 1000 == 0:
                    print(f'{count} emails importés...')
            except Exception as e:
                print(f'Erreur sur {path} : {e}')
                errors += 1

    print(f'Import terminé. Total : {count} emails importés, {errors} erreurs.')

if __name__ == '__main__':
    main()