# qitech_mock/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .http import ok, err, parse_json, bearer_ok, method_guard
from .rng import DRand, derive_user_uuid
from . import gen

# Helper: get stable seed per request
def _seed(request, *extra_ids: str):
    body = parse_json(request) or {}
    user_uuid = request.headers.get("X-User-UUID")
    # try known identifiers from bodies/queries to help determinism
    fallbacks = [
        request.GET.get("key"),
        request.GET.get("requester_identifier_key"),
        body.get("requester_identifier_key"),
        body.get("account_owner",{}).get("document_number"),
        body.get("borrower",{}).get("document_number"),
    ] + list(extra_ids)
    user = derive_user_uuid(user_uuid, *fallbacks)
    return DRand(user, request.path)

# ---------------- CaaS: onboarding PF ----------------
@csrf_exempt
def onboarding_natural_person(request):
    if (r := method_guard(request, {"POST"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    body = parse_json(request)
    if body is None: return err("invalid json", 400)
    d = _seed(request, "caas.onboarding.pf")
    return ok(gen.gen_onboarding_pf(d, body), 200)

# ---------------- Documents ----------------
@csrf_exempt
def documents_upload(request):
    if (r := method_guard(request, {"POST"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    # For simplicity, accept JSON {document_md5: "..."} or multipart—both map to md5
    md5 = request.POST.get("document_md5") or (parse_json(request) or {}).get("document_md5")
    d = _seed(request, "docs.upload", str(md5))
    return ok(gen.gen_upload(d, md5), 200)

@csrf_exempt
def document_url(request, document_key):
    if (r := method_guard(request, {"GET"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    d = _seed(request, "docs.url", str(document_key))
    return ok(gen.gen_document_url(d, str(document_key)), 200)

# ---------------- LaaS: debts ----------------
@csrf_exempt
def debt_simulation(request):
    if (r := method_guard(request, {"POST"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    body = parse_json(request)
    if body is None: return err("invalid json", 400)
    d = _seed(request, "laas.debt_simulation")
    return ok(gen.gen_debt_simulation(d, body), 200)

@csrf_exempt
def debt(request):
    if request.method == "POST":
        if not bearer_ok(request): return err("missing/invalid bearer", 401)
        body = parse_json(request)
        if body is None: return err("invalid json", 400)
        d = _seed(request, "laas.debt.issue")
        return ok(gen.gen_debt_issue(d, body), 200)
    if request.method == "GET":
        if not bearer_ok(request): return err("missing/invalid bearer", 401)
        d = _seed(request, "laas.debt.search")
        return ok(gen.gen_debt_query(d, request.GET), 200)
    return HttpResponse(status=405)

@csrf_exempt
def debt_webhook(request):
    # sink → just accept and return 204
    return HttpResponse(status=204)

# ---------------- BaaS: account opening PF ----------------
@csrf_exempt
def account_request_checking(request):
    if (r := method_guard(request, {"POST"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    body = parse_json(request)
    if body is None: return err("invalid json", 400)
    d = _seed(request, "baas.account_request.checking")
    return ok(gen.gen_account_request_pf(d, body), 201)

@csrf_exempt
def account_request_checking_patch(request, account_request_key):
    if (r := method_guard(request, {"PATCH"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    d = _seed(request, "baas.account_request.checking.patch", str(account_request_key))
    return ok(gen.gen_account_confirm_pf(d, str(account_request_key)), 201)

# ---------------- BaaS: Pix ----------------
@csrf_exempt
def pix_transfer(request, account_key):
    if (r := method_guard(request, {"POST"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    body = parse_json(request)
    if body is None: return err("invalid json", 400)
    d = _seed(request, "baas.pix.transfer", str(account_key), str(body.get("request_control_key")))
    status, resp = gen.gen_pix_transfer(d, body)
    return ok(resp, status)

@csrf_exempt
def pix_webhook(request):
    return HttpResponse(status=204)

# ---------------- Optional: transactions (toy) ----------------
@csrf_exempt
def account_transactions(request, account_key):
    if (r := method_guard(request, {"GET"})): return r
    if not bearer_ok(request): return err("missing/invalid bearer", 401)
    d = _seed(request, "baas.account.tx", str(account_key))
    n = 5 + d.randint(0, 10)
    items = []
    for i in range(n):
        di = DRand("tx", str(account_key), str(i))
        amt = di.money(-500, 800)
        items.append({
            "transaction_key": di.uuid4_like(),
            "end_to_end_id": f"E2E{di.uuid4_like().replace('-','')[:15]}",
            "amount": amt,
            "currency": "BRL",
            "event_datetime": di.datetime_iso(-30, 0),
        })
    totals = {
        "credits": float(sum(a for a in (x["amount"] for x in items) if a > 0)),
        "debits": float(sum(-a for a in (x["amount"] for x in items) if a < 0)),
        "net": float(sum(x["amount"] for x in items)),
    }
    return ok({
        "period": {
            "start": request.GET.get("start") or d.datetime_iso(-30, -29),
            "end": request.GET.get("end") or d.datetime_iso(-1, 0),
        },
        "items": items,
        "totals": totals
    }, 200)
