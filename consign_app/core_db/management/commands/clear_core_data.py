from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from consign_app.core_db.models import (
    AuditLog, LedgerEntry, Reconciliation, WebhookEvent, Document,
    ConsignmentAgreement, KycRisk, Payout, Disbursement, Payment,
    Installment, Contract, LoanOffer, Wallet, Borrower, Investor
)


class Command(BaseCommand):
    help = 'Delete all users and core_db data while preserving other app data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users-only',
            action='store_true',
            help='Delete only users, keep core_db data',
        )
        parser.add_argument(
            '--core-only',
            action='store_true',
            help='Delete only core_db data, keep users',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        users_only = options['users_only']
        core_only = options['core_only']

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY RUN - No data will be deleted'))

        total_deleted = 0

        # Delete core_db models FIRST (unless users-only specified)
        # This must come before deleting users due to foreign key constraints
        if not users_only:
            # Order matters for foreign key constraints
            models_to_clear = [
                ('AuditLog', AuditLog),
                ('LedgerEntry', LedgerEntry),
                ('Reconciliation', Reconciliation),
                ('WebhookEvent', WebhookEvent),
                ('Document', Document),
                ('ConsignmentAgreement', ConsignmentAgreement),
                ('KycRisk', KycRisk),
                ('Payout', Payout),
                ('Disbursement', Disbursement),
                ('Payment', Payment),
                ('Installment', Installment),
                ('Contract', Contract),
                ('LoanOffer', LoanOffer),
                ('Wallet', Wallet),
                ('Borrower', Borrower),
                ('Investor', Investor),
            ]

            for model_name, model_class in models_to_clear:
                try:
                    count = model_class.objects.count()
                    if count > 0:
                        if not dry_run:
                            model_class.objects.all().delete()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'{"Would delete" if dry_run else "Deleted"} {count} {model_name} records')
                        )
                        total_deleted += count
                    else:
                        self.stdout.write(f'No {model_name} records to delete')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error with {model_name}: {e}')
                    )

        # Delete users AFTER core_db models (unless core-only specified)
        if not core_only:
            user_count = User.objects.count()
            if user_count > 0:
                if not dry_run:
                    User.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{"Would delete" if dry_run else "Deleted"} {user_count} users')
                )
                total_deleted += user_count
            else:
                self.stdout.write('No users to delete')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN completed! Would delete {total_deleted} total records')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cleanup completed! Deleted {total_deleted} total records')
            )
