import os
import email
from email.utils import parsedate_to_datetime
import django
from pathlib import Path

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

    # Récupérer le vrai Message-ID de l'en-tête
    message_id = get_header_str('Message-ID').strip('<>')
    if not message_id:
        # Fallback : chemin relatif unique
        rel_path = path.relative_to(Path.cwd())
        message_id = str(rel_path).replace('\\', '/')

    from_ = get_header_str('From')
    to = get_header_str('To')
    cc = get_header_str('Cc')
    bcc = get_header_str('Bcc')
    subject = get_header_str('Subject')
    date_str = get_header_str('Date')

    try:
        date = parsedate_to_datetime(date_str)
    except:
        date = None

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

    # Nettoyage simple (supprimer la signature après '-- ')
    if '-- ' in body:
        body = body.split('-- ')[0]

    return message_id, from_, to, cc, bcc, subject, date, body

def main():
    base = Path('maildir')  # ou 'test_import' pour l'échantillon
    count = 0
    for path in base.rglob('*'):
        if path.is_file():
            try:
                message_id, from_, to, cc, bcc, subject, date, body = parse_eml(path)
                if not from_ or not date:
                    continue

                # Vérifier si le message existe déjà
                if Message.objects.filter(message_id=message_id).exists():
                    continue

                # Expéditeur
                expediteur, _ = Collaborateur.objects.get_or_create(email=from_)

                # Créer le message
                msg = Message.objects.create(
                    message_id=message_id,
                    date=date,
                    objet=subject,
                    corps=body,
                    expediteur=expediteur
                )

                # Fonction pour ajouter les destinataires
                def add_recipients(addr_str, type_):
                    if addr_str:
                        for adr in addr_str.split(','):
                            adr = adr.strip()
                            if adr:
                                dest, _ = Collaborateur.objects.get_or_create(email=adr)
                                # Si tu as un champ pour le type, tu pourrais l'utiliser ici
                                msg.destinataires.add(dest)

                add_recipients(to, 'to')
                add_recipients(cc, 'cc')
                add_recipients(bcc, 'bcc')

                count += 1
                if count % 100 == 0:
                    print(f'{count} emails importés...')
            except Exception as e:
                print(f'Erreur sur {path} : {e}')
    print(f'Import terminé. Total : {count} emails.')

if __name__ == '__main__':
    main()