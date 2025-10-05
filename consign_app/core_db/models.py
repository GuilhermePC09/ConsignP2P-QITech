# core/models.py
import uuid
from django.db import models

# Helpers
MONEY = dict(max_digits=18, decimal_places=2)
RATE = dict(max_digits=9,  decimal_places=6)


class StampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    trace_id = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        abstract = True


class Investor(StampMixin):
    investor_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=16)                              # pf|pj
    name = models.CharField(max_length=255)
    document = models.CharField(
        max_length=32, db_index=True)           # CPF/CNPJ
    email = models.EmailField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    # none|pending|approved|rejected
    kyc_status = models.CharField(max_length=32, blank=True, default="none")
    suitability_profile = models.CharField(max_length=64, blank=True)
    preferred_payout_method = models.CharField(
        max_length=16, blank=True)  # pix|ted|wallet
    status = models.CharField(max_length=32, default="active")
    # definido ao final do arquivo para evitar referência circular:
    primary_wallet = models.ForeignKey(
        "Wallet", null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_of"
    )

    def __str__(self): return f"{self.name} ({self.document})"


class Borrower(StampMixin):
    borrower_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    document = models.CharField(max_length=32, db_index=True)           # CPF
    email = models.EmailField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    kyc_status = models.CharField(max_length=32, blank=True, default="none")
    credit_status = models.CharField(max_length=32, blank=True)
    risk_score = models.DecimalField(**RATE, null=True, blank=True)
    consigned_margin = models.DecimalField(**MONEY, null=True, blank=True)
    consignment_agreement = models.ForeignKey(
        "ConsignmentAgreement",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="current_borrowers",
        related_query_name="current_borrower",
    )

    def __str__(self): return f"{self.name} ({self.document})"


class Wallet(StampMixin):
    wallet_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    # investor|platform|escrow
    owner_type = models.CharField(max_length=32)
    # referência lógica - can be null for platform wallets
    owner_id = models.UUIDField(null=True, blank=True)
    currency = models.CharField(max_length=8, default="BRL")
    available_balance = models.DecimalField(**MONEY, default=0)
    blocked_balance = models.DecimalField(**MONEY, default=0)
    status = models.CharField(max_length=32, default="active")
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)
    account_key = models.CharField(max_length=255, blank=True, db_index=True)

    def __str__(self): return f"{self.wallet_id} ({self.owner_type})"


class LoanOffer(StampMixin):
    offer_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(Borrower, on_delete=models.CASCADE)
    amount = models.DecimalField(**MONEY)
    rate = models.DecimalField(**RATE)
    term_months = models.PositiveIntegerField()
    valid_until = models.DateField(null=True, blank=True)
    # draft|open|funded|closed
    status = models.CharField(max_length=32, default="draft")
    cet = models.DecimalField(**RATE, null=True, blank=True)
    apr = models.DecimalField(**RATE, null=True, blank=True)
    fees = models.JSONField(default=dict, blank=True)
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)


class Contract(StampMixin):
    contract_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(LoanOffer, on_delete=models.PROTECT)
    instrument = models.CharField(max_length=32, default="ccb")
    creditor_type = models.CharField(
        max_length=32, default="investor")  # investor|vehicle
    creditor_id = models.UUIDField(
        null=True, blank=True)                # ref. lógica
    ccb_number = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=32, default="created")
    principal_amount = models.DecimalField(**MONEY)
    rate = models.DecimalField(**RATE)
    term_months = models.PositiveIntegerField()
    schedule_policy = models.CharField(max_length=32, default="PRICE")
    disbursement_policy = models.CharField(max_length=64, blank=True)
    signature_bundle_id = models.CharField(max_length=255, blank=True)
    document_links = models.JSONField(default=dict, blank=True)
    debt_key = models.CharField(max_length=255, blank=True, db_index=True)
    requester_identifier_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)


class Installment(StampMixin):
    installment_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(db_index=True)
    due_date = models.DateField()
    amount_due = models.DecimalField(**MONEY)
    principal_component = models.DecimalField(**MONEY, default=0)
    interest_component = models.DecimalField(**MONEY, default=0)
    fees_component = models.DecimalField(**MONEY, default=0)
    status = models.CharField(max_length=32, default="pending")
    amount_paid = models.DecimalField(**MONEY, default=0)
    paid_at = models.DateTimeField(null=True, blank=True)
    carryover = models.DecimalField(**MONEY, default=0)
    installment_key = models.CharField(
        max_length=255, blank=True, db_index=True)


class Payment(StampMixin):
    payment_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    installment = models.ForeignKey(Installment, on_delete=models.PROTECT)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT)
    # convenio|pix|boleto|ted
    source = models.CharField(max_length=32)
    amount = models.DecimalField(**MONEY)
    paid_at = models.DateTimeField()
    # processing|settled|failed
    status = models.CharField(max_length=32, default="processing")
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)
    reconciliation_batch = models.ForeignKey(
        "Reconciliation", null=True, blank=True, on_delete=models.SET_NULL
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    pix_transfer_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    end_to_end_id = models.CharField(max_length=255, blank=True, db_index=True)
    transaction_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    request_control_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    idempotency_key = models.CharField(
        max_length=255, blank=True, db_index=True)


class Disbursement(StampMixin):
    disbursement_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT)
    # pix|ted
    method = models.CharField(max_length=16)
    amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=32, default="processing")
    requested_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    destination_account = models.JSONField(default=dict, blank=True)
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)
    pix_transfer_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    end_to_end_id = models.CharField(max_length=255, blank=True, db_index=True)
    transaction_key = models.CharField(
        max_length=255, blank=True, db_index=True)
    idempotency_key = models.CharField(
        max_length=255, blank=True, db_index=True)


class Payout(StampMixin):
    payout_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    investor = models.ForeignKey(Investor, on_delete=models.PROTECT)
    amount_gross = models.DecimalField(**MONEY, default=0)
    fees_total = models.DecimalField(**MONEY, default=0)
    amount_net = models.DecimalField(**MONEY, default=0)
    method = models.CharField(max_length=16, default="pix")
    status = models.CharField(max_length=32, default="processing")
    requested_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    calculation_period = models.JSONField(default=dict, blank=True)
    items = models.JSONField(default=list, blank=True)
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)
    idempotency_key = models.CharField(
        max_length=255, blank=True, db_index=True)


class KycRisk(StampMixin):
    assessment_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    # investor|borrower
    subject_type = models.CharField(max_length=16)
    subject_id = models.UUIDField()
    provider = models.CharField(max_length=64, default="qi_risk")
    status = models.CharField(max_length=32, default="pending")
    score = models.DecimalField(**RATE, null=True, blank=True)
    decision_reasons = models.JSONField(default=dict, blank=True)
    evidences = models.JSONField(default=dict, blank=True)
    natural_person_key = models.CharField(
        max_length=255, blank=True, null=True, db_index=True)
    legal_person_key = models.CharField(
        max_length=255, blank=True, null=True, db_index=True)
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True)


class ConsignmentAgreement(StampMixin):
    consignment_agreement_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    borrower = models.ForeignKey(
        "Borrower",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="agreements",
    )
    # órgão/empresa
    issuer = models.CharField(max_length=64)
    enrollment_id = models.CharField(max_length=64, db_index=True)
    consigned_margin = models.DecimalField(**MONEY, default=0)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="active")


class Document(StampMixin):
    document_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    # investor|borrower|contract|kyc
    owner_type = models.CharField(max_length=32)
    owner_id = models.UUIDField()
    doc_type = models.CharField(max_length=64)
    hash = models.CharField(max_length=128, db_index=True)
    uri = models.CharField(max_length=1024, blank=True)
    version = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=32, default="present")
    document_key = models.CharField(max_length=255, blank=True, db_index=True)


class WebhookEvent(StampMixin):
    event_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    # inbound|outbound
    direction = models.CharField(max_length=16)
    event = models.CharField(max_length=128, db_index=True)
    resource_type = models.CharField(max_length=64, db_index=True)
    resource_id = models.UUIDField(null=True, blank=True, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    processing_status = models.CharField(max_length=16, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(
        max_length=255, blank=True, db_index=True)


class Reconciliation(StampMixin):
    reconciliation_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    # bank|qitech|platform
    source = models.CharField(max_length=32, default="bank")
    totals_expected = models.JSONField(default=dict, blank=True)
    totals_actual = models.JSONField(default=dict, blank=True)
    differences = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, default="open")


class LedgerEntry(StampMixin):
    ledger_entry_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    entry_date = models.DateTimeField(db_index=True)
    debit_account = models.CharField(max_length=64)
    credit_account = models.CharField(max_length=64)
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=8, default="BRL")
    reference_type = models.CharField(max_length=64, blank=True)
    reference_id = models.UUIDField(null=True, blank=True, db_index=True)


class AuditLog(StampMixin):
    audit_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=64)
    actor_type = models.CharField(max_length=64, blank=True)
    actor_id = models.CharField(max_length=64, blank=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"AuditLog {self.audit_id}"


class InvestmentOffer(StampMixin):
    """Investment offers available in the marketplace"""
    RISK_CHOICES = [
        ('baixo', 'Baixo'),
        ('medio', 'Médio'),
        ('alto', 'Alto'),
    ]

    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('proposta', 'Proposta'),
        ('encerrada', 'Encerrada'),
    ]

    offer_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False)

    # Basic offer details
    amount = models.DecimalField(**MONEY, help_text="Loan amount")
    monthly_rate = models.DecimalField(
        **RATE, help_text="Monthly interest rate")
    annual_rate = models.DecimalField(**RATE, help_text="Annual CET rate")
    term_months = models.IntegerField(help_text="Loan term in months")

    # Risk and status
    risk_level = models.CharField(
        max_length=10, choices=RISK_CHOICES, default='medio')
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='aberta')

    # Validity
    valid_until = models.DateTimeField(help_text="Offer validity date")

    # Related borrower (optional, for linking to actual loans)
    borrower = models.ForeignKey(
        'Borrower',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='investment_offers'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Offer {self.amount} @ {self.monthly_rate}% for {self.term_months}m"


Investor._meta.get_field("primary_wallet").remote_field.model = Wallet
