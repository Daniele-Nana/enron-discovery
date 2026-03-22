from django.db import migrations

class Migration(migrations.Migration):
    atomic = False  # Nécessaire pour CREATE INDEX CONCURRENTLY (optionnel)
    dependencies = [
        ('discovery', '0007_alter_message_date'),  # Remplacez par la dernière migration de votre app
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_expediteur ON discovery_message (expediteur_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_message_expediteur;"
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_destinataires_collaborateur ON discovery_message_destinataires (collaborateur_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_destinataires_collaborateur;"
        ),
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_msg_dest_join ON discovery_message_destinataires (message_id, collaborateur_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_msg_dest_join;"
        ),
    ]