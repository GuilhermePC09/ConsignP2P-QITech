# qitech_mock/gen.py
from .rng import DRand
from decimal import Decimal

def _installments(d: DRand, principal: float, monthly_rate: float, n: int):
    # PRICE-like schedule, mock precision
    i = Decimal(str(monthly_rate))
    P = Decimal(str(principal))
    if i == 0:
        pmt = P / n
    else:
        pmt = P * (i * (1+i)**n) / ((1+i)**n - 1)
    items = []
    bal = P
    for k in range(1, n+1):
        interest = bal * i
        amort = pmt - interest
        if amort > bal:
            amort = bal
            pmt = amort + interest
        bal -= amort
        items.append({
            "installment_number": k,
            "installment_key": d.uuid4_like(),
            "due_date": d.date_from_today(25+(k-1)*27, 27*k+27),
            "total_amount": float(round(pmt, 2)),
            "principal_amount": float(round(amort, 2)),
            "interest_amount": float(round(interest, 2)),
            "fee_amount": 0.00,
            "installment_status": "pending"
        })
    return items

# ---------------- CaaS (PF) ----------------
def gen_onboarding_pf(d: DRand, body: dict):
    analysis = d.choice(["automatically_approved","automatically_denied","manual_analysis"])
    # simple skew: higher income → more likely approved
    if float(body.get("monthly_income") or 3000) > 6000:
        analysis = "automatically_approved"
    return {
        "id": body.get("id") or d.uuid4_like(),
        "analysis_status": analysis,
        "reason": None if analysis=="automatically_approved" else "Mocked reason"
    }

# ---------------- Documents ----------------
def gen_upload(d: DRand, md5: str|None):
    return {
        "document_key": d.uuid4_like(),
        "document_md5": md5 or "deadbeef" * 4
    }

def gen_document_url(d: DRand, document_key: str):
    return {
        "document_key": document_key,
        "document_url": f"https://example.mock/doc/{document_key}.pdf",
        "signed_document_url": f"https://example.mock/doc/{document_key}.signed.pdf",
        "expiration_datetime": d.datetime_iso(1, 2)
    }

# ---------------- LaaS: debt simulation/issue/query ----------------
def gen_debt_simulation(d: DRand, body: dict):
    fin = body.get("financial", {})
    n = int(fin.get("number_of_installments") or 12)
    monthly = float(fin.get("monthly_rate") or 0.019 + d.uniform(-0.002,0.002))
    principal = float(fin.get("principal") or 10000.0)
    items = _installments(d, principal, monthly, n)
    cet_y = (1.0 + monthly)**12 - 1.0
    return {
        "type": "debt",
        "key": d.uuid4_like(),
        "status": "simulated",
        "event_datetime": d.datetime_iso(),
        "data": {
            "pricing": {
                "principal": principal,
                "monthly_rate": round(monthly,6),
                "annual_cet": round(cet_y,6),
            },
            "installments": items
        }
    }

def gen_debt_issue(d: DRand, body: dict):
    fin = body.get("financial", {})
    n = int(fin.get("number_of_installments") or 12)
    monthly = float(fin.get("monthly_interest_rate") or 0.019 + d.uniform(-0.002,0.002))
    principal = float(fin.get("disbursed_amount") or 10000.0)
    debt_key = d.uuid4_like()
    items = _installments(d, principal, monthly, n)
    return {
        "webhook_type": "debt",
        "key": debt_key,
        "status": "waiting_signature",
        "event_datetime": d.datetime_iso(),
        "data": {
            "contract": {
                "number": f"CCB-{debt_key[:8]}",
                "urls": {
                    "unsigned": f"https://example.mock/ccb/{debt_key}.pdf",
                    "signed":   f"https://example.mock/ccb/{debt_key}.signed.pdf"
                }
            },
            "installments": items,
            "fees": [],
        }
    }

def gen_debt_query(d: DRand, q: dict):
    """
    Stateless query: if ?key=uuid given, reconstruct a single debt;
    otherwise return a paginated list derived from the user seed.
    """
    key = q.get("key")
    if key:
        # rebuild single debt from given key
        d_one = DRand("laas.debt.single", key)
        body = {"financial":{"number_of_installments": d_one.randint(6, 24),
                             "monthly_interest_rate": 0.017 + d_one.uniform(-0.003, 0.003),
                             "disbursed_amount": d_one.money(3000, 20000)}}
        return {"data": gen_debt_issue(d_one, body)}
    # list mode
    total = 5 + d.randint(0, 7)
    items = []
    for i in range(total):
        d_i = DRand("laas.debt.list", str(i), d.uuid4_like())
        items.append(gen_debt_issue(d_i, {"financial":{}}))
    return {
        "data": items,
        "pagination": {
            "current_page": 1, "next_page": None, "rows_per_page": total,
            "total_pages": 1, "total_rows": total
        }
    }

# ---------------- BaaS: account opening (PF) ----------------
def gen_account_request_pf(d: DRand, body: dict):
    req_key = d.uuid4_like()
    branch = str(d.randint(1, 3999)).zfill(4)
    number = str(d.randint(100000, 999999))
    return {
        "account_info": {"account_branch": branch, "account_digit": "0", "account_number": number},
        "account_request_key": req_key,
        "account_request_status": "processing"
    }

def gen_account_confirm_pf(d: DRand, account_request_key: str):
    return {"account_key": DRand("baas.account", account_request_key).uuid4_like()}

# ---------------- Pix ----------------
def gen_pix_transfer(d: DRand, body: dict):
    sent = d.choice([True, False])
    base = {
        "request_control_key": body.get("request_control_key") or d.uuid4_like(),
        "pix_transfer_key": d.uuid4_like(),
        "transaction_key": d.uuid4_like(),
        "created_at": d.datetime_iso(),
    }
    if sent:
        base["pix_transfer_status"] = "sent"
        return 201, base
    else:
        base["pix_transfer_status"] = "pending"
        return 202, base
