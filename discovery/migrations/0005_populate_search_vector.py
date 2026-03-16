from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('discovery', '0001_initial'),  # Remplacez par la dernière migration appliquée avant celle-ci
    ]

    operations = [
        migrations.RunSQL(
            sql='''
            UPDATE discovery_message
            SET search_vector = 
                setweight(to_tsvector('english', coalesce(objet, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(corps, '')), 'B');
            ''',
            reverse_sql=migrations.RunSQL.noop,  # Pas de retour arrière possible simplement
        ),
    ]
