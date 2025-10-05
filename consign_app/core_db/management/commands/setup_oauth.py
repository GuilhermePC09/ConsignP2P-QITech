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

            # Create OAuth2 applications using Django ORM
        # 1. Client Credentials Application (for system/API access)
        client_app = Application.objects.create(
            client_id='p2p-client-id',
            client_secret='p2p-secret',
            name='P2P API Client (Client Credentials)',
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            user=admin_user
        )

        # 2. Password Grant Application (for user authentication)
        password_app = Application.objects.create(
            client_id='p2p-password-client',
            client_secret='p2p-password-secret',
            name='P2P User Client (Password)',
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_PASSWORD,
            user=admin_user
        )

        # 3. Authorization Code Application (for web/mobile apps)
        auth_code_app = Application.objects.create(
            client_id='p2p-web-client',
            client_secret='p2p-web-secret',
            name='P2P Web Client (Authorization Code)',
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            user=admin_user,
            redirect_uris='http://127.0.0.1:8000/auth/callback/'
        )

        # Get the created applications for display
        apps = Application.objects.all().order_by('name')

        self.stdout.write(self.style.SUCCESS(
            '✅ OAuth2 Applications created successfully!'))

        for app in apps:
            self.stdout.write(f'\n📋 {app.name}:')
            self.stdout.write(f'   Client ID: {app.client_id}')
            self.stdout.write(f'   Client Secret: {app.client_secret}')
            self.stdout.write(f'   Grant Type: {app.authorization_grant_type}')

        self.stdout.write('\n🔗 URLs:')
        self.stdout.write('   Token URL: http://127.0.0.1:8000/o/token/')
        self.stdout.write(
            '   Authorization URL: http://127.0.0.1:8000/o/authorize/')
        self.stdout.write('')

        self.stdout.write('📝 Example client credentials request:')
        self.stdout.write('curl -X POST http://127.0.0.1:8000/o/token/ \\')
        self.stdout.write(
            '  -H "Content-Type: application/x-www-form-urlencoded" \\')
        self.stdout.write(
            '  -d "grant_type=client_credentials&client_id=p2p-client-id&client_secret=p2p-secret"')

        self.stdout.write('\n📝 Example password grant request (user login):')
        self.stdout.write('curl -X POST http://127.0.0.1:8000/o/token/ \\')
        self.stdout.write(
            '  -H "Content-Type: application/x-www-form-urlencoded" \\')
        self.stdout.write(
            '  -d "grant_type=password&client_id=p2p-password-client&client_secret=p2p-password-secret&username=USER&password=PASS"')
