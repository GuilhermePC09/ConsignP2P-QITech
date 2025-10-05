import os
import django
from django.core.management.base import BaseCommand
from django.utils import timezone
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

        # Clear existing applications
        Application.objects.filter(client_id='p2p-client-id').delete()

        # Create new application using Django ORM
        app = Application.objects.create(
            client_id='p2p-client-id',
            client_secret='p2p-secret',
            name='P2P API Client',
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            user=admin_user
        )

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
