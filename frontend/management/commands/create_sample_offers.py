from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from consign_app.core_db.models import LoanOffer, Borrower
import random
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create sample loan offers for marketplace testing'

    def handle(self, *args, **options):
        # Clear only offers that are safe to delete (no contract relationships)
        safe_to_delete = LoanOffer.objects.filter(
            status='open').exclude(contract__isnull=False)
        deleted_count = safe_to_delete.count()
        safe_to_delete.delete()

        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Deleted {deleted_count} existing open offers')
            )

        # Get or create some borrowers
        borrowers = list(Borrower.objects.all()[:10])
        if not borrowers:
            self.stdout.write(
                self.style.WARNING(
                    'No borrowers found. Please create some borrowers first.')
            )
            return

        # Sample data for realistic offers
        amounts = [8750, 15500, 25000, 33200, 42000,
                   67500, 12300, 28900, 55600, 19800]
        rates = [1.9, 2.1, 2.5, 2.8, 3.2, 3.8, 2.3, 2.7, 1.8, 3.5]
        terms = [12, 18, 24, 30, 36, 48, 15, 20, 42, 27]
        statuses = ['open', 'draft', 'closed']

        for i in range(len(amounts)):
            # Pick a random borrower
            borrower = random.choice(borrowers)

            # Most offers should be open for marketplace
            status = random.choices(
                statuses,
                weights=[0.8, 0.1, 0.1],  # 80% open, 10% draft, 10% closed
                k=1
            )[0]

            # Valid until date (5-30 days from now)
            valid_days = random.randint(5, 30)
            valid_until = (timezone.now() + timedelta(days=valid_days)).date()

            # Calculate CET (simplified)
            monthly_rate = Decimal(str(rates[i]))
            annual_rate = (1 + monthly_rate/100) ** 12 - 1
            cet = annual_rate * 100

            offer = LoanOffer.objects.create(
                borrower=borrower,
                amount=Decimal(str(amounts[i])),
                rate=monthly_rate,
                term_months=terms[i],
                status=status,
                valid_until=valid_until,
                cet=cet
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Created offer: R$ {amounts[i]} @ {rates[i]}% for {terms[i]}m ({status})'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {len(amounts)} loan offers'
            )
        )
