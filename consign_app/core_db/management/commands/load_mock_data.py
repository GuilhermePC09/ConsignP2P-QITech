"""
Management command to load P2P platform mock data from CSV files
"""
import csv
import json
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from consign_app.core_db.models import (
    Investor, Borrower, Wallet, LoanOffer, Contract, Installment,
    Payment, Disbursement, KycRisk, ConsignmentAgreement, Document
)


def read_csv(file_path: str):
    """Read CSV file and return rows as dictionaries"""
    path = Path(file_path)
    if not path.exists():
        raise CommandError(f"CSV file not found: {file_path}")

    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(date_str: str):
    """Parse date string in various formats"""
    if not date_str or date_str.strip() == "":
        return None

    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}")


def parse_datetime(datetime_str: str):
    """Parse datetime string"""
    if not datetime_str or datetime_str.strip() == "":
        return None

    datetime_str = datetime_str.strip()
    # Handle date-only formats by adding default time
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(datetime_str, fmt)
            return timezone.make_aware(dt.replace(hour=0, minute=0, second=0))
        except ValueError:
            continue

    # Handle datetime formats
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(datetime_str, fmt)
            return timezone.make_aware(dt)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime format: {datetime_str}")


class Command(BaseCommand):
    help = 'Load P2P platform mock data from CSV files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before loading mock data',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data',
            help='Directory containing CSV files (default: data)',
        )

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])

        if not data_dir.exists():
            raise CommandError(f"Data directory not found: {data_dir}")

        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            self.clear_data()

        self.stdout.write(self.style.SUCCESS(
            'Loading P2P mock data from CSV files...'))

        # Load without atomic transaction to allow partial success
        # Load in dependency order
        wallets_count = self.load_wallets(data_dir / "p2p_wallets.csv")
        investors_count = self.load_investors(data_dir / "p2p_investors.csv")
        agreements_count = self.load_consignment_agreements(
            data_dir / "p2p_consignment_agreements.csv")
        borrowers_count = self.load_borrowers(data_dir / "p2p_borrowers.csv")
        kyc_count = self.load_kyc_risk(data_dir / "p2p_kyc_risk.csv")
        offers_count = self.load_loan_offers(data_dir / "p2p_loan_offers.csv")
        contracts_count = self.load_contracts(data_dir / "p2p_contracts.csv")
        disbursements_count = self.load_disbursements(
            data_dir / "p2p_disbursements.csv")
        installments_count = self.load_installments(
            data_dir / "p2p_installments.csv")
        payments_count = self.load_payments(data_dir / "p2p_payments.csv")
        documents_count = self.load_documents(data_dir / "p2p_documents.csv")

        # Now link borrowers and consignment agreements
        self.link_borrower_agreements(
            data_dir / "p2p_consignment_agreements.csv")

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully loaded:\n'
                f'  {wallets_count} wallets\n'
                f'  {investors_count} investors\n'
                f'  {borrowers_count} borrowers\n'
                f'  {agreements_count} consignment agreements\n'
                f'  {kyc_count} KYC assessments\n'
                f'  {offers_count} loan offers\n'
                f'  {contracts_count} contracts\n'
                f'  {disbursements_count} disbursements\n'
                f'  {installments_count} installments\n'
                f'  {payments_count} payments\n'
                f'  {documents_count} documents'
            )
        )

    def clear_data(self):
        """Clear existing data"""
        Document.objects.all().delete()
        Payment.objects.all().delete()
        Installment.objects.all().delete()
        Disbursement.objects.all().delete()
        Contract.objects.all().delete()
        LoanOffer.objects.all().delete()
        KycRisk.objects.all().delete()
        ConsignmentAgreement.objects.all().delete()
        Borrower.objects.all().delete()
        Investor.objects.all().delete()
        Wallet.objects.all().delete()

    def load_wallets(self, csv_file: Path) -> int:
        """Load wallet data"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                # Create wallet even if owner_id is missing. Some mock data
                # references wallets that may not have owner_id populated; it's
                # safer to create the wallet with owner_id=None rather than
                # skipping it which causes downstream FK failures.
                owner_id_val = None
                if row.get('owner_id'):
                    try:
                        owner_id_val = uuid.UUID(row['owner_id'])
                    except Exception:
                        owner_id_val = None

                Wallet.objects.create(
                    wallet_id=uuid.UUID(row['wallet_id']),
                    owner_type=row.get('owner_type', ''),
                    owner_id=owner_id_val,
                    currency=row['currency'] if row['currency'] else 'BRL',
                    available_balance=Decimal(row['available_balance']),
                    blocked_balance=Decimal(row['blocked_balance']),
                    status=row['status'] if row['status'] else 'active',
                    external_reference=row.get('external_reference', ''),
                    account_key=row['account_key'] if row['account_key'] else '',
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                    trace_id=row.get('trace_id', ''),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading wallet {row.get("wallet_id", "unknown")}: {e}')
                )

        return count

    def load_investors(self, csv_file: Path) -> int:
        """Load investor data"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                primary_wallet = None
                # Some CSVs use different header names or reference wallets
                # that may not be present. Be tolerant: try to resolve the
                # primary wallet, but don't fail the whole investor load if
                # the wallet is missing.
                primary_wallet_id = row.get(
                    'primary_wallet_id') or row.get('primary_wallet')
                if primary_wallet_id:
                    try:
                        primary_wallet = Wallet.objects.get(
                            wallet_id=uuid.UUID(primary_wallet_id))
                    except Exception:
                        primary_wallet = None

                Investor.objects.create(
                    investor_id=uuid.UUID(row['investor_id']),
                    type=row['type'],
                    name=row['name'],
                    document=row['document'],
                    email=row['email'] if row['email'] else '',
                    phone_number=row['phone_number'] if row['phone_number'] else '',
                    kyc_status=row['kyc_status'] if row['kyc_status'] else '',
                    suitability_profile=row['suitability_profile'] if row['suitability_profile'] else '',
                    preferred_payout_method=row['preferred_payout_method'] if row['preferred_payout_method'] else '',
                    status=row['status'] if row['status'] else 'active',
                    primary_wallet=primary_wallet,
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                    trace_id=row['trace_id'] if row['trace_id'] else '',
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading investor {row.get("investor_id", "unknown")}: {e}')
                )

        return count

    def load_consignment_agreements(self, csv_file: Path) -> int:
        """Load consignment agreement data"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                # Create agreements without borrower references initially
                # We'll update them later when borrowers are loaded
                ConsignmentAgreement.objects.create(
                    consignment_agreement_id=uuid.UUID(
                        row['consignment_agreement_id']),
                    borrower=None,  # Will be updated later
                    issuer=row['issuer'],
                    enrollment_id=row['enrollment_id'],
                    consigned_margin=Decimal(
                        row['consigned_margin']) if row['consigned_margin'] else 0,
                    valid_from=parse_date(
                        row['valid_from']) if row['valid_from'] else None,
                    valid_to=parse_date(
                        row['valid_to']) if row['valid_to'] else None,
                    status=row.get('status', 'active'),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                    trace_id=row['trace_id'] if row['trace_id'] else '',
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading consignment agreement {row.get("consignment_agreement_id", "unknown")}: {e}')
                )

        return count

    def load_borrowers(self, csv_file: Path) -> int:
        """Load borrower data"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                # CSVs may use 'consignment_agreement' or
                # 'consignment_agreement_id' as the column. Accept both.
                agreement = None
                ca_field = row.get('consignment_agreement_id') or row.get(
                    'consignment_agreement')
                if ca_field:
                    try:
                        agreement = ConsignmentAgreement.objects.get(
                            consignment_agreement_id=uuid.UUID(ca_field))
                    except Exception:
                        agreement = None

                Borrower.objects.create(
                    borrower_id=uuid.UUID(row['borrower_id']),
                    name=row['name'],
                    document=row['document'],
                    email=row['email'] if row['email'] else '',
                    phone_number=row['phone_number'] if row['phone_number'] else '',
                    kyc_status=row['kyc_status'] if row['kyc_status'] else '',
                    credit_status=row['credit_status'] if row['credit_status'] else '',
                    risk_score=Decimal(
                        row['risk_score']) if row['risk_score'] else None,
                    consigned_margin=Decimal(
                        row['consigned_margin']) if row['consigned_margin'] else None,
                    consignment_agreement=agreement,
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                    trace_id=row.get('trace_id', ''),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading borrower {row.get("borrower_id", "unknown")}: {e}')
                )

        return count

    def load_kyc_risk(self, csv_file: Path) -> int:
        """Load KYC risk assessment data"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                KycRisk.objects.create(
                    assessment_id=uuid.UUID(row['assessment_id']),
                    subject_type=row['subject_type'],
                    subject_id=uuid.UUID(row['subject_id']),
                    provider=row['provider'],
                    status=row['status'],
                    score=Decimal(row['score']) if row['score'] else None,
                    decision_reasons=row['decision_reasons'],
                    evidences=row['evidences'],
                    natural_person_key=row['natural_person_key'] if row['natural_person_key'] else None,
                    legal_person_key=row['legal_person_key'] if row['legal_person_key'] else None,
                    # Database enforces NOT NULL for external_reference in
                    # this project; default to empty string when missing.
                    external_reference=row.get('external_reference', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                    trace_id=row['trace_id'] if row['trace_id'] else None,
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error loading KYC data: {e}')
                )

        return count

    def load_loan_offers(self, csv_file: Path) -> int:
        """Load loan offers"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                # Some loan offer rows may reference borrowers that weren't
                # loaded (CSV mismatch). If borrower is missing, skip the
                # offer gracefully.
                try:
                    borrower = Borrower.objects.get(
                        borrower_id=uuid.UUID(row['borrower_id']))
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping loan offer {row.get('offer_id', row.get('offer', 'unknown'))} - borrower not found: {e}"
                        )
                    )
                    continue

                LoanOffer.objects.create(
                    offer_id=uuid.UUID(row.get('offer_id')
                                       or row.get('offer')),
                    borrower=borrower,
                    amount=Decimal(row['amount']),
                    rate=Decimal(row['rate']),  # Correct field name
                    term_months=int(row['term_months']),
                    valid_until=parse_date(
                        row['valid_until']) if row['valid_until'] else None,
                    status=row['status'],
                    cet=Decimal(row['cet']) if row.get('cet') else None,
                    apr=Decimal(row['apr']) if row.get('apr') else None,
                    fees=json.loads(row['fees']) if row.get('fees') else {},
                    external_reference=row.get('external_reference', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading loan offer {row.get("offer_id", row.get("offer", "unknown"))}: {e}')
                )

        return count

    def load_contracts(self, csv_file: Path) -> int:
        """Load contracts"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                # Get the offer this contract is based on. Accept CSVs that
                # name the column 'offer' instead of 'offer_id'.
                offer_field = row.get('offer_id') or row.get('offer')
                if not offer_field:
                    raise KeyError('offer_id')

                offer = LoanOffer.objects.get(
                    offer_id=uuid.UUID(offer_field))

                Contract.objects.create(
                    contract_id=uuid.UUID(row['contract_id']),
                    offer=offer,
                    instrument=row.get('instrument', 'ccb'),
                    creditor_type=row.get('creditor_type', 'investor'),
                    creditor_id=uuid.UUID(row['creditor_id']) if row.get(
                        'creditor_id') else None,
                    ccb_number=row.get('ccb_number', ''),
                    status=row.get('status', 'created'),
                    principal_amount=Decimal(row['principal_amount']),
                    rate=Decimal(row['rate']),
                    term_months=int(row['term_months']),
                    schedule_policy=row.get('schedule_policy', 'PRICE'),
                    disbursement_policy=row.get('disbursement_policy', ''),
                    signature_bundle_id=row.get('signature_bundle_id', ''),
                    document_links=json.loads(row['document_links']) if row.get(
                        'document_links') else {},
                    debt_key=row.get('debt_key', ''),
                    requester_identifier_key=row.get(
                        'requester_identifier_key', ''),
                    signed_at=parse_datetime(row['signed_at']) if row.get(
                        'signed_at') else None,
                    activated_at=parse_datetime(row['activated_at']) if row.get(
                        'activated_at') else None,
                    closed_at=parse_datetime(row['closed_at']) if row.get(
                        'closed_at') else None,
                    idempotency_key=row.get('idempotency_key', ''),
                    external_reference=row.get('external_reference', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading contract {row.get("contract_id", "unknown")}: {e}')
                )

        return count

    def load_disbursements(self, csv_file: Path) -> int:
        """Load disbursements"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                contract = Contract.objects.get(
                    contract_id=uuid.UUID(row['contract_id']))

                Disbursement.objects.create(
                    disbursement_id=uuid.UUID(row['disbursement_id']),
                    contract=contract,
                    method=row.get('method', 'pix'),
                    amount=Decimal(row['amount']),
                    status=row.get('status', 'processing'),
                    requested_at=parse_datetime(row['requested_at']) if row.get(
                        'requested_at') else None,
                    settled_at=parse_datetime(row['settled_at']) if row.get(
                        'settled_at') else None,
                    destination_account=json.loads(row['destination_account']) if row.get(
                        'destination_account') else {},
                    external_reference=row.get('external_reference', ''),
                    pix_transfer_key=row.get('pix_transfer_key', ''),
                    end_to_end_id=row.get('end_to_end_id', ''),
                    transaction_key=row.get('transaction_key', ''),
                    idempotency_key=row.get('idempotency_key', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading disbursement {row.get("disbursement_id", "unknown")}: {e}')
                )

        return count

    def load_installments(self, csv_file: Path) -> int:
        """Load installments"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                contract = Contract.objects.get(
                    contract_id=uuid.UUID(row['contract_id']))

                Installment.objects.create(
                    installment_id=uuid.UUID(row['installment_id']),
                    contract=contract,
                    sequence=int(row['sequence']),
                    due_date=parse_date(row['due_date']),
                    amount_due=Decimal(row['amount_due']),
                    principal_component=Decimal(row['principal_component']),
                    interest_component=Decimal(row['interest_component']),
                    fees_component=Decimal(row['fees_component']),
                    status=row.get('status', 'pending'),
                    amount_paid=Decimal(row.get('amount_paid', '0')),
                    paid_at=parse_datetime(row['paid_at']) if row.get(
                        'paid_at') else None,
                    carryover=Decimal(row.get('carryover', '0')),
                    installment_key=row.get('installment_key', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading installment {row.get("installment_id", "unknown")}: {e}')
                )

        return count

    def load_payments(self, csv_file: Path) -> int:
        """Load payments"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                installment = Installment.objects.get(
                    installment_id=uuid.UUID(row['installment_id']))
                contract = Contract.objects.get(
                    contract_id=uuid.UUID(row['contract_id']))

                # Handle optional reconciliation_batch_id
                reconciliation_batch = None
                if row.get('reconciliation_batch_id'):
                    try:
                        from consign_app.core_db.models import Reconciliation
                        reconciliation_batch = Reconciliation.objects.get(
                            reconciliation_id=uuid.UUID(row['reconciliation_batch_id']))
                    except Reconciliation.DoesNotExist:
                        pass  # Skip if reconciliation doesn't exist

                Payment.objects.create(
                    payment_id=uuid.UUID(row['payment_id']),
                    installment=installment,
                    contract=contract,
                    source=row['source'],  # Correct field name
                    amount=Decimal(row['amount']),
                    paid_at=parse_datetime(row['paid_at']),
                    status=row.get('status', 'processing'),
                    external_reference=row.get('external_reference', ''),
                    reconciliation_batch=reconciliation_batch,
                    raw_payload=json.loads(row['raw_payload']) if row.get(
                        'raw_payload') else {},
                    pix_transfer_key=row.get('pix_transfer_key', ''),
                    end_to_end_id=row.get('end_to_end_id', ''),
                    transaction_key=row.get('transaction_key', ''),
                    request_control_key=row.get('request_control_key', ''),
                    idempotency_key=row.get('idempotency_key', ''),
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading payment {row.get("payment_id", "unknown")}: {e}')
                )

        return count

    def load_documents(self, csv_file: Path) -> int:
        """Load documents"""
        rows = read_csv(csv_file)
        count = 0

        for row in rows:
            try:
                Document.objects.create(
                    # Correct primary key field
                    document_id=uuid.UUID(row['document_id']),
                    owner_type=row['owner_type'],  # Match model field
                    owner_id=uuid.UUID(row['owner_id']),  # Match model field
                    doc_type=row['doc_type'],  # Match model field
                    hash=row['hash'],  # Match model field
                    uri=row['uri'],  # Match model field
                    created_at=parse_datetime(row['created_at']),
                    updated_at=parse_datetime(row['updated_at']),
                )
                count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error loading document {row.get("document_id", "unknown")}: {e}')
                )

        return count

    def link_borrower_agreements(self, csv_file: Path):
        """Link borrowers and consignment agreements after both are loaded"""
        rows = read_csv(csv_file)
        linked_count = 0

        for row in rows:
            try:
                # Accept both 'borrower' and 'borrower_id' column names in
                # the consignment agreements CSV when linking.
                borrower_field = row.get('borrower_id') or row.get('borrower')
                if borrower_field:
                    agreement = ConsignmentAgreement.objects.get(
                        consignment_agreement_id=uuid.UUID(row['consignment_agreement_id']))
                    borrower = Borrower.objects.get(
                        borrower_id=uuid.UUID(borrower_field))

                    # Update agreement to reference borrower
                    agreement.borrower = borrower
                    agreement.save()
                    linked_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error linking borrower {row.get("borrower_id", "unknown")} to agreement {row.get("consignment_agreement_id", "unknown")}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Linked {linked_count} borrower-agreement relationships'))
