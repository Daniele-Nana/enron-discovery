import os
import email
from email.utils import parsedate_to_datetime
import django
from pathlib import Path
import dateutil.parser

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enron_project.settings')
django.setup()

from discovery.models import Collaborateur, Message, Folder, MessageFolder

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

    message_id = get_header_str('Message-ID').strip('<>')
    if not message_id:
        rel_path = path.relative_to(Path.cwd())
        message_id = str(rel_path).replace('\\', '/')

    in_reply_to = get_header_str('In-Reply-To').strip('<>')
    if not in_reply_to:
        in_reply_to = None

    from_ = get_header_str('From')
    to = get_header_str('To')
    cc = get_header_str('Cc')
    bcc = get_header_str('Bcc')
    subject = get_header_str('Subject')
    date_str = get_header_str('Date')

    date = None
    if date_str:
        try:
            date = parsedate_to_datetime(date_str)
        except:
            pass
        if date is None:
            try:
                date = dateutil.parser.parse(date_str)
            except:
                pass
    if date is not None:
        if date.year < 1990 or date.year > 2005:
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

    if '-- ' in body:
        body = body.split('-- ')[0]

    return message_id, in_reply_to, from_, to, cc, bcc, subject, date, body

def get_or_create_folder(rel_path):
    """Crée récursivement les dossiers à partir du chemin relatif.
       rel_path est une chaîne comme 'allen-p/inbox' (sans le nom de fichier).
    """
    parts = rel_path.split(os.sep)
    current_path = ''
    parent = None
    for part in parts:
        if current_path:
            current_path = current_path + '/' + part
        else:
            current_path = part
        folder, _ = Folder.objects.get_or_create(
            path=current_path,
            defaults={'name': part, 'parent': parent}
        )
        parent = folder
    return parent  # le dernier dossier (celui qui contient le fichier)

def main():
    base = Path('maildir/allen-p')  # à adapter si besoin
    count = 0
    errors = 0
    for path in base.rglob('*'):
        if path.is_file():
            try:
                message_id, in_reply_to, from_, to, cc, bcc, subject, date, body = parse_eml(path)
                if not from_ or not date:
                    errors += 1
                    continue

                if Message.objects.filter(message_id=message_id).exists():
                    errors += 1
                    continue

                expediteur, _ = Collaborateur.objects.get_or_create(email=from_)

                msg = Message.objects.create(
                    message_id=message_id,
                    in_reply_to=in_reply_to,
                    date=date,
                    objet=subject,
                    corps=body,
                    expediteur=expediteur
                )

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

                # Gestion du dossier : on obtient le chemin relatif par rapport à la base
                # path.parent donne le dossier, puis on prend le relatif par rapport à base
                folder_rel = path.parent.relative_to(base)
                if str(folder_rel) != '.':
                    folder = get_or_create_folder(str(folder_rel))
                    MessageFolder.objects.get_or_create(message=msg, folder=folder)

                count += 1
                if count % 100 == 0:
                    print(f'{count} emails importés...')
            except Exception as e:
                print(f'Erreur sur {path} : {e}')
                errors += 1
    print(f'Import terminé. Total : {count} emails importés, {errors} erreurs.')

if __name__ == '__main__':
    main()