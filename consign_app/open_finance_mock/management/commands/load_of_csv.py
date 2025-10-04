# consign_app/core_db/management/commands/load_of_csv.py
import csv, re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from consign_app.open_finance_mock.models import (
    OFCreditDebitType, OFBillStatus, OFInstallmentStatus, OFProductService,
    OFCustomer, OFCustomerProduct,
    OFAccount, OFAccountBalance, OFAccountTransaction,
    OFCcAccount, OFCcBill, OFCcTransaction,
    OFLoanContract, OFLoanInstallment, OFLoanPayment,
)

DIGITS = re.compile(r"\D+")

def norm_digits(s: str) -> str:
    return DIGITS.sub("", s or "")

def parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"invalid date: {s!r} (expected YYYY-MM-DD or DD/MM/YYYY)")

def parse_decimal(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # remove thousand separators and normalize decimal sep
    s = s.replace(" ", "")
    # common cases: "1.234,56" or "1,234.56"
    if s.count(",") == 1 and s.count(".") > 1:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"invalid decimal: {s!r}")

def parse_rate(s: str):
    """Accept '0.0235' or '2.35%' and return Decimal fraction."""
    s = (s or "").strip()
    if not s:
        return None
    if s.endswith("%"):
        base = parse_decimal(s[:-1])
        return (base or Decimal("0")) / Decimal("100")
    return parse_decimal(s)

def read_csv(path: str):
    p = Path(path)
    if not p.exists():
        raise CommandError(f"file not found: {p}")
    with p.open(newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)

# ----------------- Catalog loaders -----------------
def load_credit_debit_types(path: str):
    created = updated = 0
    for r in read_csv(path):
        code = (r.get("codigo") or r.get("code") or "").strip()
        desc = (r.get("descricao") or r.get("description") or "").strip()
        if not code:
            continue
        _, c = OFCreditDebitType.objects.update_or_create(codigo=code, defaults={"descricao": desc})
        created += int(c); updated += int(not c)
    return created, updated

def load_bill_statuses(path: str):
    created = updated = 0
    for r in read_csv(path):
        code = (r.get("codigo") or r.get("code") or "").strip()
        desc = (r.get("descricao") or r.get("description") or "").strip()
        if not code:
            continue
        _, c = OFBillStatus.objects.update_or_create(codigo=code, defaults={"descricao": desc})
        created += int(c); updated += int(not c)
    return created, updated

def load_installment_statuses(path: str):
    created = updated = 0
    for r in read_csv(path):
        code = (r.get("codigo") or r.get("code") or "").strip()
        desc = (r.get("descricao") or r.get("description") or "").strip()
        if not code:
            continue
        _, c = OFInstallmentStatus.objects.update_or_create(codigo=code, defaults={"descricao": desc})
        created += int(c); updated += int(not c)
    return created, updated

def load_product_services(path: str):
    created = updated = 0
    for r in read_csv(path):
        code = (r.get("codigo") or r.get("code") or "").strip()
        desc = (r.get("descricao") or r.get("description") or "").strip()
        if not code:
            continue
        _, c = OFProductService.objects.update_or_create(codigo=code, defaults={"descricao": desc})
        created += int(c); updated += int(not c)
    return created, updated

# ----------------- Customers -----------------
def load_customers(path: str):
    created = updated = 0
    for r in read_csv(path):
        cpf   = norm_digits(r.get("cpf_number") or r.get("cpf") or "")
        if not cpf:
            continue
        civ   = (r.get("civil_name") or "").strip()
        soc   = (r.get("social_name") or "").strip()
        bdate = parse_date(r.get("birth_date") or "")
        sdate = parse_date(r.get("start_date") or "")
        # choose cpf as natural key (idempotent)
        _, c = OFCustomer.objects.update_or_create(
            cpf_number=cpf,
            defaults=dict(civil_name=civ, social_name=soc, birth_date=bdate, start_date=sdate),
        )
        created += int(c); updated += int(not c)
    return created, updated

def load_customer_products(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        cpf   = norm_digits(r.get("cpf_number") or r.get("cpf") or "")
        pcode = (r.get("product_code") or r.get("product") or "").strip()
        if not (cpf and pcode):
            skipped += 1; continue
        # allow description to upsert catalog
        pdesc = (r.get("product_description") or "").strip()
        if pdesc:
            OFProductService.objects.update_or_create(codigo=pcode, defaults={"descricao": pdesc})
        try:
            cust = OFCustomer.objects.get(cpf_number=cpf)
        except OFCustomer.DoesNotExist:
            raise CommandError(f"customer not found for cpf={cpf!r} (load customers first)")
        prod = OFProductService.objects.get(codigo=pcode)
        _, c = OFCustomerProduct.objects.update_or_create(customer=cust, product=prod)
        created += int(c); updated += int(not c)
    return created, updated, skipped

# ----------------- Accounts -----------------
def load_accounts(path: str):
    created = updated = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        if not acc_id:
            continue
        compe  = (r.get("compe_code") or "").strip()
        branch = (r.get("branch_code") or "").strip()
        number = (r.get("number") or "").strip()
        owner  = norm_digits(r.get("owner_cpf") or "")
        owner_obj = None
        if owner:
            try:
                owner_obj = OFCustomer.objects.get(cpf_number=owner)
            except OFCustomer.DoesNotExist:
                raise CommandError(f"owner not found for account_id={acc_id!r} cpf={owner!r}")
        _, c = OFAccount.objects.update_or_create(
            account_id=acc_id,
            defaults=dict(compe_code=compe, branch_code=branch, number=number, owner=owner_obj),
        )
        created += int(c); updated += int(not c)
    return created, updated

def load_account_balances(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        if not acc_id:
            skipped += 1; continue
        amount = parse_decimal(r.get("available_amount") or "0")
        ref    = parse_date(r.get("reference_date") or "")
        try:
            acc = OFAccount.objects.get(account_id=acc_id)
        except OFAccount.DoesNotExist:
            raise CommandError(f"account not found for balance (account_id={acc_id!r})")
        # allow one balance per (account, reference_date); if date empty, overwrite latest
        _, c = OFAccountBalance.objects.update_or_create(
            account=acc, reference_date=ref, defaults=dict(available_amount=amount)
        )
        created += int(c); updated += int(not c)
    return created, updated, skipped

def load_account_transactions(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        tx_id  = (r.get("transaction_id") or "").strip()
        if not (acc_id and tx_id):
            skipped += 1; continue
        date   = parse_date(r.get("booking_date") or "")
        amount = parse_decimal(r.get("amount") or "0")
        cdt    = (r.get("credit_debit_type") or r.get("creditDebitType") or "").strip()
        desc   = (r.get("description") or "").strip()

        try:
            acc = OFAccount.objects.get(account_id=acc_id)
        except OFAccount.DoesNotExist:
            raise CommandError(f"account not found for transaction (account_id={acc_id!r})")

        # upsert catalog if description came
        cdt_desc = (r.get("credit_debit_description") or "").strip()
        if cdt_desc:
            OFCreditDebitType.objects.update_or_create(codigo=cdt, defaults={"descricao": cdt_desc})

        cdt_obj = OFCreditDebitType.objects.get(codigo=cdt)

        _, c = OFAccountTransaction.objects.update_or_create(
            account=acc, transaction_id=tx_id,
            defaults=dict(booking_date=date, amount=amount, credit_debit_type=cdt_obj, description=desc),
        )
        created += int(c); updated += int(not c)
    return created, updated, skipped

# ----------------- Credit Cards -----------------
def load_cc_accounts(path: str):
    created = updated = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        if not acc_id:
            continue
        owner  = norm_digits(r.get("owner_cpf") or "")
        limit_ = parse_decimal(r.get("credit_limit") or "")
        owner_obj = None
        if owner:
            try:
                owner_obj = OFCustomer.objects.get(cpf_number=owner)
            except OFCustomer.DoesNotExist:
                raise CommandError(f"owner not found for cc account (account_id={acc_id!r}, cpf={owner!r})")
        _, c = OFCcAccount.objects.update_or_create(
            account_id=acc_id,
            defaults=dict(owner=owner_obj, credit_limit=limit_),
        )
        created += int(c); updated += int(not c)
    return created, updated

def load_cc_bills(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        bill_id = (r.get("bill_id") or "").strip()
        if not (acc_id and bill_id):
            skipped += 1; continue
        due   = parse_date(r.get("due_date") or "")
        minpay = parse_decimal(r.get("minimum_payment") or "0")
        status = (r.get("status_code") or "").strip()
        status_desc = (r.get("status_description") or "").strip()
        if status_desc:
            OFBillStatus.objects.update_or_create(codigo=status, defaults={"descricao": status_desc})
        try:
            acc = OFCcAccount.objects.get(account_id=acc_id)
        except OFCcAccount.DoesNotExist:
            raise CommandError(f"cc account not found for bill (account_id={acc_id!r})")
        status_obj = OFBillStatus.objects.get(codigo=status)
        _, c = OFCcBill.objects.update_or_create(
            account=acc, bill_id=bill_id,
            defaults=dict(due_date=due, minimum_payment=minpay, status=status_obj),
        )
        created += int(c); updated += int(not c)
    return created, updated, skipped

def load_cc_transactions(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        acc_id = (r.get("account_id") or "").strip()
        amount = parse_decimal(r.get("amount") or "0")
        bdate  = parse_date(r.get("booking_date") or "")
        desc   = (r.get("description") or "").strip()
        bill_id = (r.get("bill_id") or "").strip()  # optional
        if not acc_id:
            skipped += 1; continue
        try:
            acc = OFCcAccount.objects.get(account_id=acc_id)
        except OFCcAccount.DoesNotExist:
            raise CommandError(f"cc account not found for transaction (account_id={acc_id!r})")
        bill_obj = None
        if bill_id:
            bill_obj = OFCcBill.objects.filter(account=acc, bill_id=bill_id).first()
            if bill_obj is None:
                raise CommandError(f"bill not found (account_id={acc_id!r}, bill_id={bill_id!r})")
        # no natural unique in model; generate a stable composite key via update_or_create on fields that should be unique per CSV row
        obj, created_flag = OFCcTransaction.objects.get_or_create(
            account=acc, bill=bill_obj, amount=amount, booking_date=bdate, description=desc
        )
        created += int(created_flag); updated += int(not created_flag)
    return created, updated, skipped

# ----------------- Loans -----------------
def load_loan_contracts(path: str):
    created = updated = 0
    for r in read_csv(path):
        cid   = (r.get("contract_id") or "").strip()
        if not cid:
            continue
        owner = norm_digits(r.get("owner_cpf") or "")
        owner_obj = None
        if owner:
            try:
                owner_obj = OFCustomer.objects.get(cpf_number=owner)
            except OFCustomer.DoesNotExist:
                raise CommandError(f"owner not found for loan contract (contract_id={cid!r}, cpf={owner!r})")
        c_amount = parse_decimal(r.get("contract_amount") or "0")
        outstanding = parse_decimal(r.get("outstanding") or "0")
        rate  = parse_rate(r.get("interest_rate") or "")
        cdate = parse_date(r.get("contract_date") or "")
        mdate = parse_date(r.get("maturity_date") or "")
        _, c = OFLoanContract.objects.update_or_create(
            contract_id=cid,
            defaults=dict(
                owner=owner_obj,
                contract_amount=c_amount,
                outstanding=outstanding,
                interest_rate=rate or Decimal("0"),
                contract_date=cdate,
                maturity_date=mdate,
            ),
        )
        created += int(c); updated += int(not c)
    return created, updated

def load_loan_installments(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        cid = (r.get("contract_id") or "").strip()
        iid = (r.get("instalment_id") or r.get("installment_id") or "").strip()
        if not (cid and iid):
            skipped += 1; continue
        due   = parse_date(r.get("due_date") or "")
        amount = parse_decimal(r.get("amount") or "0")
        status = (r.get("status_code") or "").strip()
        status_desc = (r.get("status_description") or "").strip()
        if status_desc:
            OFInstallmentStatus.objects.update_or_create(codigo=status, defaults={"descricao": status_desc})
        try:
            contract = OFLoanContract.objects.get(contract_id=cid)
        except OFLoanContract.DoesNotExist:
            raise CommandError(f"loan contract not found for instalment (contract_id={cid!r})")
        status_obj = OFInstallmentStatus.objects.get(codigo=status)
        _, c = OFLoanInstallment.objects.update_or_create(
            contract=contract, instalment_id=iid,
            defaults=dict(due_date=due, amount=amount, status=status_obj),
        )
        created += int(c); updated += int(not c)
    return created, updated, skipped

def load_loan_payments(path: str):
    created = updated = skipped = 0
    for r in read_csv(path):
        cid = (r.get("contract_id") or "").strip()
        if not cid:
            skipped += 1; continue
        pdate  = parse_date(r.get("payment_date") or "")
        amount = parse_decimal(r.get("amount") or "0")
        iid    = (r.get("instalment_id") or r.get("installment_id") or "").strip()
        try:
            contract = OFLoanContract.objects.get(contract_id=cid)
        except OFLoanContract.DoesNotExist:
            raise CommandError(f"loan contract not found for payment (contract_id={cid!r})")
        inst = None
        if iid:
            inst = OFLoanInstallment.objects.filter(contract=contract, instalment_id=iid).first()
            if inst is None:
                raise CommandError(f"instalment not found for payment (contract_id={cid!r}, instalment_id={iid!r})")
        # use get_or_create on (contract, instalment, payment_date, amount)
        obj, created_flag = OFLoanPayment.objects.get_or_create(
            contract=contract, instalment=inst, payment_date=pdate, amount=amount
        )
        created += int(created_flag); updated += int(not created_flag)
    return created, updated, skipped

# ----------------- command -----------------
class Command(BaseCommand):
    help = "Load Open Finance mock CSV files into models."

    def add_arguments(self, parser):
        # catalogs
        parser.add_argument("--of-credit-debit-types", help="CSV: codigo, descricao")
        parser.add_argument("--of-bill-statuses", help="CSV: codigo, descricao")
        parser.add_argument("--of-installment-statuses", help="CSV: codigo, descricao")
        parser.add_argument("--of-product-services", help="CSV: codigo, descricao")

        # customers
        parser.add_argument("--of-customers", help="CSV: cpf_number, civil_name, social_name, birth_date, start_date")
        parser.add_argument("--of-customer-products", help="CSV: cpf_number, product_code[, product_description]")

        # accounts
        parser.add_argument("--of-accounts", help="CSV: account_id, compe_code, branch_code, number, owner_cpf")
        parser.add_argument("--of-account-balances", help="CSV: account_id, available_amount, reference_date")
        parser.add_argument("--of-account-transactions", help="CSV: account_id, transaction_id, booking_date, amount, credit_debit_type[, description, credit_debit_description]")

        # credit cards
        parser.add_argument("--of-cc-accounts", help="CSV: account_id, owner_cpf, credit_limit")
        parser.add_argument("--of-cc-bills", help="CSV: account_id, bill_id, due_date, minimum_payment, status_code[, status_description]")
        parser.add_argument("--of-cc-transactions", help="CSV: account_id, amount, booking_date[, description, bill_id]")

        # loans
        parser.add_argument("--of-loan-contracts", help="CSV: contract_id, owner_cpf, contract_amount, outstanding, interest_rate, contract_date, maturity_date")
        parser.add_argument("--of-loan-instalments", help="CSV: contract_id, instalment_id, due_date, amount, status_code[, status_description]")
        parser.add_argument("--of-loan-payments", help="CSV: contract_id, payment_date, amount[, instalment_id]")

    @transaction.atomic
    def handle(self, *args, **opts):
        report = []

        # catalogs
        if opts.get("of_credit_debit_types"):
            c, u = load_credit_debit_types(opts["of_credit_debit_types"]); report.append(f"OF credit/debit types   : +{c} / ~{u}")
        if opts.get("of_bill_statuses"):
            c, u = load_bill_statuses(opts["of_bill_statuses"]); report.append(f"OF bill statuses        : +{c} / ~{u}")
        if opts.get("of_installment_statuses"):
            c, u = load_installment_statuses(opts["of_installment_statuses"]); report.append(f"OF instalment statuses  : +{c} / ~{u}")
        if opts.get("of_product_services"):
            c, u = load_product_services(opts["of_product_services"]); report.append(f"OF product/services     : +{c} / ~{u}")

        # customers
        if opts.get("of_customers"):
            c, u = load_customers(opts["of_customers"]); report.append(f"OF customers            : +{c} / ~{u}")
        if opts.get("of_customer_products"):
            c, u, s = load_customer_products(opts["of_customer_products"]); report.append(f"OF customer-products    : +{c} / ~{u} / skipped={s}")

        # accounts
        if opts.get("of_accounts"):
            c, u = load_accounts(opts["of_accounts"]); report.append(f"OF accounts             : +{c} / ~{u}")
        if opts.get("of_account_balances"):
            c, u, s = load_account_balances(opts["of_account_balances"]); report.append(f"OF account balances     : +{c} / ~{u} / skipped={s}")
        if opts.get("of_account_transactions"):
            c, u, s = load_account_transactions(opts["of_account_transactions"]); report.append(f"OF account transactions : +{c} / ~{u} / skipped={s}")

        # credit cards
        if opts.get("of_cc_accounts"):
            c, u = load_cc_accounts(opts["of_cc_accounts"]); report.append(f"OF cc accounts          : +{c} / ~{u}")
        if opts.get("of_cc_bills"):
            c, u, s = load_cc_bills(opts["of_cc_bills"]); report.append(f"OF cc bills             : +{c} / ~{u} / skipped={s}")
        if opts.get("of_cc_transactions"):
            c, u, s = load_cc_transactions(opts["of_cc_transactions"]); report.append(f"OF cc transactions      : +{c} / ~{u} / skipped={s}")

        # loans
        if opts.get("of_loan_contracts"):
            c, u = load_loan_contracts(opts["of_loan_contracts"]); report.append(f"OF loan contracts       : +{c} / ~{u}")
        if opts.get("of_loan_instalments"):
            c, u, s = load_loan_installments(opts["of_loan_instalments"]); report.append(f"OF loan instalments     : +{c} / ~{u} / skipped={s}")
        if opts.get("of_loan_payments"):
            c, u, s = load_loan_payments(opts["of_loan_payments"]); report.append(f"OF loan payments        : +{c} / ~{u} / skipped={s}")

        if not report:
            raise CommandError("No CSV provided. See --help.")
        self.stdout.write("\n".join(report))
