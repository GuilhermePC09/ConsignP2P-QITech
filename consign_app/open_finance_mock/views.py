from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .auth import require_bearer
from consign_app.open_finance_mock.models import (
    OFCustomer, OFCustomerProduct, OFProductService,
    OFAccount, OFAccountBalance, OFAccountTransaction, OFCreditDebitType,
    OFCcAccount, OFCcBill, OFCcTransaction, OFBillStatus,
    OFLoanContract, OFLoanInstallment, OFLoanPayment, OFInstallmentStatus
)

# ---------------------- helpers ----------------------
def _money(x: Optional[Decimal]) -> Optional[str]:
    return None if x is None else str(x)

def _date(d) -> Optional[str]:
    return None if not d else d.strftime("%Y-%m-%d")

def _ymd_ok(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False

def _ym_ok(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m")
        return True
    except Exception:
        return False

# ---------------------- OAuth (mock) ----------------------
@require_http_methods(["POST"])
@csrf_exempt
def token_view(request):
    now = datetime.utcnow()
    return JsonResponse({
        "access_token": "mock-openfinance-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "customers accounts credit-cards-accounts loans",
        "issued_at": int(now.timestamp()),
        "expires_at": int((now + timedelta(seconds=3600)).timestamp()),
    }, status=200)

# ---------------------- Customers v2 ----------------------
@require_http_methods(["GET"])
@require_bearer
def get_customer_identification(request):
    """
    GET /customers/v2/personal/identifications?cpf=XXXXXXXXXXX
    (Você também pode passar customerId=<uuid> se preferir.)
    """
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    customer_id = request.GET.get("customerId")

    qs = OFCustomer.objects.all()
    if customer_id:
        qs = qs.filter(id=customer_id)
    elif cpf:
        qs = qs.filter(cpf_number=cpf)
    else:
        return JsonResponse({"message": "Informe cpf ou customerId."}, status=400)

    c = qs.select_related().first()
    if not c:
        # mock mínimo
        payload = {
            "cpfNumber": cpf or "00000000000",
            "civilName": "Cliente Mock",
            "socialName": "",
            "birthDate": "1990-01-01",
            "startDate": "2020-01-01",
            "productsServices": []
        }
        return JsonResponse(payload, status=200, json_dumps_params={"ensure_ascii": False})

    # produtos/serviços contratados
    products = list(
        OFCustomerProduct.objects.filter(customer=c).select_related("product").values_list("product__codigo", flat=True)
    )

    payload = {
        "customerId": str(c.id),
        "cpfNumber": c.cpf_number,
        "civilName": c.civil_name,
        "socialName": c.social_name or "",
        "birthDate": _date(c.birth_date),
        "startDate": _date(c.start_date),
        "productsServices": products,  # ex.: ["ACCOUNTS","LOANS","CARDS"]
    }
    return JsonResponse(payload, status=200, json_dumps_params={"ensure_ascii": False})

# ---------------------- Accounts v2 ----------------------
@require_http_methods(["GET"])
@require_bearer
def list_accounts(request):
    """
    GET /accounts/v2/accounts?cpf=... | customerId=...
    """
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    customer_id = request.GET.get("customerId")

    owner: Optional[OFCustomer] = None
    if customer_id:
        owner = OFCustomer.objects.filter(id=customer_id).first()
    elif cpf:
        owner = OFCustomer.objects.filter(cpf_number=cpf).first()

    qs = OFAccount.objects.all()
    if owner:
        qs = qs.filter(owner=owner)

    data = [{
        "accountId": a.account_id,
        "compeCode": a.compe_code,
        "branchCode": a.branch_code,
        "number": a.number,
    } for a in qs.order_by("compe_code", "branch_code", "number")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def get_account_balances(request, account_id: str):
    """
    GET /accounts/v2/{accountId}/balances
    Retorna o último saldo conhecido (referenceDate mais recente).
    """
    acc = OFAccount.objects.filter(account_id=account_id).first()
    if not acc:
        return JsonResponse({"message": "Account not found"}, status=404)

    bal = (OFAccountBalance.objects
           .filter(account=acc)
           .order_by("-reference_date", "-id")
           .first())

    payload = {
        "accountId": account_id,
        "availableAmount": _money(bal.available_amount) if bal else "0",
        "referenceDate": _date(bal.reference_date) if bal else None
    }
    return JsonResponse(payload, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def get_account_transactions(request, account_id: str):
    """
    GET /accounts/v2/{accountId}/transactions?from=YYYY-MM-DD&to=YYYY-MM-DD&creditDebitType=CREDIT|DEBIT
    """
    acc = OFAccount.objects.filter(account_id=account_id).first()
    if not acc:
        return JsonResponse({"message": "Account not found"}, status=404)

    dfrom = request.GET.get("from")
    dto = request.GET.get("to")
    cdt = request.GET.get("creditDebitType")

    qs = OFAccountTransaction.objects.select_related("credit_debit_type").filter(account=acc)

    if dfrom and _ymd_ok(dfrom):
        qs = qs.filter(booking_date__gte=dfrom)
    if dto and _ymd_ok(dto):
        qs = qs.filter(booking_date__lte=dto)
    if cdt:
        qs = qs.filter(credit_debit_type_id=cdt)

    data = [{
        "transactionId": t.transaction_id,
        "bookingDate": _date(t.booking_date),
        "amount": _money(t.amount),
        "creditDebitType": t.credit_debit_type_id,
        "description": t.description or ""
    } for t in qs.order_by("-booking_date", "-id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

# ---------------------- Credit Cards v2 ----------------------
@require_http_methods(["GET"])
@require_bearer
def list_cc_accounts(request):
    """
    GET /credit-cards-accounts/v2/accounts?cpf=... | customerId=...
    """
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    customer_id = request.GET.get("customerId")

    owner: Optional[OFCustomer] = None
    if customer_id:
        owner = OFCustomer.objects.filter(id=customer_id).first()
    elif cpf:
        owner = OFCustomer.objects.filter(cpf_number=cpf).first()

    qs = OFCcAccount.objects.all()
    if owner:
        qs = qs.filter(owner=owner)

    data = [{
        "accountId": a.account_id,
        "creditLimit": _money(a.credit_limit),
    } for a in qs.order_by("account_id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def list_cc_bills(request, account_id: str):
    """
    GET /credit-cards-accounts/v2/{accountId}/bills?status=...&from=YYYY-MM&to=YYYY-MM
    """
    acc = OFCcAccount.objects.filter(account_id=account_id).first()
    if not acc:
        return JsonResponse({"message": "Credit card account not found"}, status=404)

    status_code = request.GET.get("status")    # opcional
    ym_from = request.GET.get("from")          # YYYY-MM
    ym_to = request.GET.get("to")

    qs = OFCcBill.objects.select_related("status").filter(account=acc)

    if status_code:
        qs = qs.filter(status_id=status_code)
    if ym_from and _ym_ok(ym_from):
        qs = qs.filter(due_date__gte=f"{ym_from}-01")
    if ym_to and _ym_ok(ym_to):
        qs = qs.filter(due_date__lte=f"{ym_to}-31")

    data = [{
        "billId": b.bill_id,
        "dueDate": _date(b.due_date),
        "minimumPayment": _money(b.minimum_payment),
        "status": b.status_id,
    } for b in qs.order_by("-due_date", "-id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def list_cc_transactions(request, account_id: str):
    """
    GET /credit-cards-accounts/v2/{accountId}/transactions?billId=...&from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    acc = OFCcAccount.objects.filter(account_id=account_id).first()
    if not acc:
        return JsonResponse({"message": "Credit card account not found"}, status=404)

    bill_id = request.GET.get("billId")
    dfrom = request.GET.get("from")
    dto = request.GET.get("to")

    qs = OFCcTransaction.objects.filter(account=acc)
    if bill_id:
        bill = OFCcBill.objects.filter(account=acc, bill_id=bill_id).first()
        qs = qs.filter(bill=bill) if bill else qs.none()
    if dfrom and _ymd_ok(dfrom):
        qs = qs.filter(booking_date__gte=dfrom)
    if dto and _ymd_ok(dto):
        qs = qs.filter(booking_date__lte=dto)

    data = [{
        "amount": _money(t.amount),
        "bookingDate": _date(t.booking_date),
        "description": t.description or "",
        "billId": t.bill.bill_id if t.bill else None,
    } for t in qs.order_by("-booking_date", "-id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

# ---------------------- Loans v2 ----------------------
@require_http_methods(["GET"])
@require_bearer
def list_loan_contracts(request):
    """
    GET /loans/v2/contracts?cpf=... | customerId=...
    """
    cpf = (request.GET.get("cpf") or "").replace(".", "").replace("-", "")
    customer_id = request.GET.get("customerId")

    owner: Optional[OFCustomer] = None
    if customer_id:
        owner = OFCustomer.objects.filter(id=customer_id).first()
    elif cpf:
        owner = OFCustomer.objects.filter(cpf_number=cpf).first()

    qs = OFLoanContract.objects.all()
    if owner:
        qs = qs.filter(owner=owner)

    data = [{
        "contractId": c.contract_id,
        "contractAmount": _money(c.contract_amount),
        "outstanding": _money(c.outstanding),
        "interestRate": str(c.interest_rate),
        "contractDate": _date(c.contract_date),
        "maturityDate": _date(c.maturity_date),
    } for c in qs.order_by("-contract_date", "-id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def get_loan_contract(request, contract_id: str):
    """
    GET /loans/v2/contracts/{contractId}
    """
    c = OFLoanContract.objects.filter(contract_id=contract_id).first()
    if not c:
        return JsonResponse({"message": "Contract not found"}, status=404)

    payload = {
        "contractId": c.contract_id,
        "contractAmount": _money(c.contract_amount),
        "outstanding": _money(c.outstanding),
        "interestRate": str(c.interest_rate),
        "contractDate": _date(c.contract_date),
        "maturityDate": _date(c.maturity_date),
    }
    return JsonResponse(payload, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def list_loan_payments(request, contract_id: str):
    """
    GET /loans/v2/contracts/{contractId}/payments
    """
    c = OFLoanContract.objects.filter(contract_id=contract_id).first()
    if not c:
        return JsonResponse({"message": "Contract not found"}, status=404)

    qs = OFLoanPayment.objects.select_related("instalment").filter(contract=c)
    data = [{
        "paymentDate": _date(p.payment_date),
        "amount": _money(p.amount),
        "instalmentId": p.instalment.instalment_id if p.instalment else None
    } for p in qs.order_by("-payment_date", "-id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})

@require_http_methods(["GET"])
@require_bearer
def list_loan_installments(request, contract_id: str):
    """
    GET /loans/v2/contracts/{contractId}/installments
    """
    c = OFLoanContract.objects.filter(contract_id=contract_id).first()
    if not c:
        return JsonResponse({"message": "Contract not found"}, status=404)

    qs = OFLoanInstallment.objects.select_related("status").filter(contract=c)
    data = [{
        "instalmentId": i.instalment_id,
        "dueDate": _date(i.due_date),
        "amount": _money(i.amount),
        "status": i.status_id
    } for i in qs.order_by("due_date", "instalment_id")]

    return JsonResponse({"data": data}, status=200, json_dumps_params={"ensure_ascii": False})
