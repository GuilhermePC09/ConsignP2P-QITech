# consign_app/core_db/models.py
import uuid
from django.db import models

MONEY = dict(max_digits=18, decimal_places=2)
RATE  = dict(max_digits=9,  decimal_places=6)

class OFCreditDebitType(models.Model):
    codigo = models.CharField(primary_key=True, max_length=10)   
    descricao = models.CharField(max_length=120)

class OFBillStatus(models.Model):
    codigo = models.CharField(primary_key=True, max_length=20)   
    descricao = models.CharField(max_length=120)

class OFInstallmentStatus(models.Model):
    codigo = models.CharField(primary_key=True, max_length=20) 
    descricao = models.CharField(max_length=120)

class OFProductService(models.Model):
    codigo = models.CharField(primary_key=True, max_length=50)   # ex: ACCOUNTS, LOANS, CARDS...
    descricao = models.CharField(max_length=120)


class OFCustomer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cpf_number   = models.CharField(max_length=11, db_index=True)
    civil_name   = models.CharField(max_length=255)
    social_name  = models.CharField(max_length=255, blank=True)
    birth_date   = models.DateField(null=True, blank=True)

    # início do relacionamento com a instituição (quando disponível)
    start_date   = models.DateField(null=True, blank=True)

    # metadados
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

class OFCustomerProduct(models.Model):
    """Relação N:N entre cliente e produtos/serviços (em vez de JSON)."""
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer  = models.ForeignKey(OFCustomer, on_delete=models.CASCADE, db_index=True)
    product   = models.ForeignKey(OFProductService, on_delete=models.PROTECT, db_column="product_code")

    class Meta:
        unique_together = ("customer", "product")


class OFAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # identificador padronizado da conta (OF)
    account_id   = models.CharField(max_length=120, unique=True)

    compe_code   = models.CharField(max_length=3)   # banco
    branch_code  = models.CharField(max_length=10)  # agência
    number       = models.CharField(max_length=30)  # número da conta

    owner = models.ForeignKey(OFCustomer, on_delete=models.SET_NULL, null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

class OFAccountBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account   = models.ForeignKey(OFAccount, on_delete=models.CASCADE, db_index=True)
    available_amount = models.DecimalField(**MONEY)
    reference_date   = models.DateField(null=True, blank=True)

class OFAccountTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account   = models.ForeignKey(OFAccount, on_delete=models.CASCADE, db_index=True)
    transaction_id = models.CharField(max_length=120)  # único por conta
    booking_date   = models.DateField()
    amount         = models.DecimalField(**MONEY)
    credit_debit_type = models.ForeignKey(OFCreditDebitType, on_delete=models.PROTECT,
                                          db_column="credit_debit_type")
    description    = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("account", "transaction_id")


class OFCcAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    account_id   = models.CharField(max_length=120, unique=True)  # creditCardAccountId
    owner        = models.ForeignKey(OFCustomer, on_delete=models.SET_NULL, null=True, blank=True)
    credit_limit = models.DecimalField(**MONEY, null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

class OFCcBill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account   = models.ForeignKey(OFCcAccount, on_delete=models.CASCADE, db_index=True)
    bill_id   = models.CharField(max_length=120)  # único por conta
    due_date  = models.DateField()
    minimum_payment = models.DecimalField(**MONEY, default=0)
    status    = models.ForeignKey(OFBillStatus, on_delete=models.PROTECT, db_column="status_code")

    class Meta:
        unique_together = ("account", "bill_id")

class OFCcTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(OFCcAccount, on_delete=models.CASCADE, db_index=True)
    bill    = models.ForeignKey(OFCcBill, on_delete=models.SET_NULL, null=True, blank=True)
    amount  = models.DecimalField(**MONEY)
    booking_date = models.DateField(null=True, blank=True)
    description  = models.CharField(max_length=255, blank=True)


class OFLoanContract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract_id     = models.CharField(max_length=120, unique=True)
    owner           = models.ForeignKey(OFCustomer, on_delete=models.SET_NULL, null=True, blank=True)

    contract_amount = models.DecimalField(**MONEY)
    outstanding     = models.DecimalField(**MONEY, default=0)
    interest_rate   = models.DecimalField(**RATE)      # taxa contratada
    contract_date   = models.DateField()
    maturity_date   = models.DateField()

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

class OFLoanInstallment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract    = models.ForeignKey(OFLoanContract, on_delete=models.CASCADE, db_index=True)
    instalment_id = models.CharField(max_length=120)     # único por contrato
    due_date    = models.DateField()
    amount      = models.DecimalField(**MONEY)
    status      = models.ForeignKey(OFInstallmentStatus, on_delete=models.PROTECT,
                                    db_column="status_code")

    class Meta:
        unique_together = ("contract", "instalment_id")

class OFLoanPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract   = models.ForeignKey(OFLoanContract, on_delete=models.CASCADE, db_index=True)
    instalment = models.ForeignKey(OFLoanInstallment, on_delete=models.SET_NULL, null=True, blank=True)
    payment_date = models.DateField()
    amount       = models.DecimalField(**MONEY)
