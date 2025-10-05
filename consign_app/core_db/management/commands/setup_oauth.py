import os
import django
from django.core.management.base import BaseCommand
from oauth2_provider.models import Application
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Set up OAuth2 application for API authentication'

    def handle(self, *args, **options):
        # Delete existing applications
        apps_count = Application.objects.count()
        if apps_count > 0:
            Application.objects.all().delete()
            self.stdout.write(
                f'🗑️  Deleted {apps_count} existing applications')

        # Get or create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={'is_staff': True, 'is_superuser': True}
        )
        if created:
            admin_user.set_password('admin')
            admin_user.save()
            self.stdout.write('👤 Created admin user')

        # Create OAuth2 application using raw SQL to avoid hashing
        from django.db import connection

        with connection.cursor() as cursor:
            # Delete existing applications
            cursor.execute("DELETE FROM oauth2_provider_application")

            # Insert new application with plain text secret
            cursor.execute("""
                INSERT INTO oauth2_provider_application 
                (client_id, client_secret, name, client_type, authorization_grant_type, user_id, created, updated)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, [
                'p2p-client-id',
                'p2p-secret',  # Plain text secret
                'P2P API Client',
                Application.CLIENT_CONFIDENTIAL,
                Application.GRANT_CLIENT_CREDENTIALS,
                admin_user.id
            ])

        # Get the created application for display
        app = Application.objects.get(client_id='p2p-client-id')

        self.stdout.write(self.style.SUCCESS(
            '✅ OAuth2 Application created successfully!'))
        self.stdout.write('📋 Credentials:')
        self.stdout.write(f'   Client ID: {app.client_id}')
        self.stdout.write(f'   Client Secret: {app.client_secret}')
        self.stdout.write('   Grant Type: client_credentials')
        self.stdout.write('')
        self.stdout.write('🔗 Token URL: http://127.0.0.1:8000/o/token/')
        self.stdout.write('')
        self.stdout.write('📝 Example token request:')
        self.stdout.write('curl -X POST http://127.0.0.1:8000/o/token/ \\')
        self.stdout.write(
            '  -H "Content-Type: application/x-www-form-urlencoded" \\')
        self.stdout.write(
            '  -d "grant_type=client_credentials&client_id=p2p-client-id&client_secret=p2p-secret"')
