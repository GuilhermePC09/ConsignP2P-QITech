# consign_app/api/feature_builder.py
from __future__ import annotations

import requests
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from django.urls import reverse


# ======================
# Nomes/paths internos
# ======================
# Dataprev (têm 'name' no urls.py)
DP_BENEFICIOS_NAME = "mock_beneficios"
DP_RELACOES_NAME   = "mock_relacoes_trabalhistas"

# Open Finance (sem 'name' nas rotas → usar path literal relativo ao include /of/)
OF_IDENT_PATH      = "/of/customers/v2/personal/identifications"
OF_ACCOUNTS_PATH   = "/of/accounts/v2/accounts"
OF_ACC_BAL_PATH    = "/of/accounts/v2/{account_id}/balances"
OF_ACC_TX_PATH     = "/of/accounts/v2/{account_id}/transactions"

OF_CC_ACCOUNTS     = "/of/credit-cards-accounts/v2/accounts"
OF_CC_BILLS_PATH   = "/of/credit-cards-accounts/v2/{account_id}/bills"
OF_CC_TX_PATH      = "/of/credit-cards-accounts/v2/{account_id}/transactions"

OF_LOANS_CONTRACTS = "/of/loans/v2/contracts"
OF_LOAN_INST_PATH  = "/of/loans/v2/contracts/{contract_id}/installments"
OF_LOAN_PAY_PATH   = "/of/loans/v2/contracts/{contract_id}/payments"

# Tokens mock (fallback quando não houver Authorization no request)
DATAPREV_TOKEN = "mock-access-token"
OPENFIN_TOKEN  = "mock-openfinance-token"


# ======================
# Erro específico
# ======================
class FeatureBuildError(ValueError):
    """Erro ao montar as features (dados ausentes/HTTP erro/JSON inválido)."""


# ======================
# Helpers
# ======================
def _months_between(d0: date, d1: date) -> int:
    return max(1, (d1.year - d0.year) * 12 + (d1.month - d0.month))

def _ym(d: date) -> str:
    return d.strftime("%Y-%m")

def _abs_url(request, *, name: Optional[str] = None, path: Optional[str] = None, args: Optional[list] = None) -> str:
    """
    Monta URL absoluta usando:
      - reverse(name, args=...) quando 'name' existir; ou
      - path literal (ex.: '/of/...') quando 'path' for usado.
    """
    if name:
        rel = reverse(name, args=args or [])
    elif path:
        rel = path
    else:
        raise RuntimeError("Forneça 'name' ou 'path' para montar a URL.")
    return request.build_absolute_uri(rel)

def _auth_headers(request, *, prefer_header: bool, fallback_token: str) -> Dict[str, str]:
    """
    Se prefer_header=True, tenta reutilizar Authorization do request.
    Se não existir, usa fallback_token (mocks aceitam qualquer Bearer).
    """
    headers = {"Content-Type": "application/json"}
    auth = request.META.get("HTTP_AUTHORIZATION")
    if prefer_header and auth:
        headers["Authorization"] = auth
    else:
        headers["Authorization"] = f"Bearer {fallback_token}"
    return headers

def _json_ok(resp: requests.Response, what: str) -> Dict[str, Any]:
    try:
        resp.raise_for_status()
    except requests.RequestException as e:
        raise FeatureBuildError(f"{what}: HTTP error -> {e}")
    try:
        return resp.json()
    except Exception as e:
        raise FeatureBuildError(f"{what}: JSON inválido") from e

def _first(obj_list, what: str) -> Dict[str, Any]:
    if not isinstance(obj_list, list) or not obj_list:
        raise FeatureBuildError(f"{what}: lista vazia")
    if not isinstance(obj_list[0], dict):
        raise FeatureBuildError(f"{what}: item inválido (esperado objeto)")
    return obj_list[0]

def _parse_money(s) -> Decimal:
    if s is None:
        return Decimal("0")
    try:
        return Decimal(str(s))
    except (InvalidOperation, ValueError):
        return Decimal("0")

def _parse_date_ymd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def _last_n_months(n: int, ref: Optional[date] = None) -> List[str]:
    """Retorna lista de 'YYYY-MM' dos últimos n meses (mais recente por último)."""
    ref = ref or date.today()
    months = []
    y, m = ref.year, ref.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))  # do mais antigo ao mais recente


# ======================
# Função principal
# ======================
def build_features_for_borrower(
    *,
    request,
    cpf: str,
    amount: float,
    term_months: int,
    overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Monta o dicionário com as 15 features exigidas pelo /risk/score, 100% a partir dos endpoints.
    """
    overrides = overrides or {}
    today = date.today()

    # ===== 1) Dataprev: Benefícios =====
    url_ben = _abs_url(request, name=DP_BENEFICIOS_NAME)
    h_ben   = _auth_headers(request, prefer_header=True, fallback_token=DATAPREV_TOKEN)
    ben_resp = requests.get(url_ben, params={"cpf": cpf}, headers=h_ben, timeout=5)
    ben_root = _json_ok(ben_resp, "Dataprev/benefícios")
    ben = _first(ben_root.get("beneficios", []), "Dataprev/benefícios")

    sit_desc = ben.get("descricaoSituacao")
    dt_ini_s = ben.get("dataInicio")
    if not sit_desc or not dt_ini_s:
        raise FeatureBuildError("Dataprev/benefícios: falta descricaoSituacao ou dataInicio")
    try:
        dt_ini = _parse_date_ymd(dt_ini_s)
    except Exception:
        raise FeatureBuildError("Dataprev/benefícios: dataInicio inválida (YYYY-MM-DD)")

    beneficio_ativo = 1 if str(sit_desc).upper() == "ATIVO" else 0
    tempo_beneficio_meses = _months_between(dt_ini, today)

    # ===== 2) Dataprev: Relação trabalhista =====
    url_rel = _abs_url(request, name=DP_RELACOES_NAME)
    h_rel   = _auth_headers(request, prefer_header=True, fallback_token=DATAPREV_TOKEN)
    rel_resp = requests.get(url_rel, params={"cpf": cpf}, headers=h_rel, timeout=5)
    rel_root = _json_ok(rel_resp, "Dataprev/relações-trabalhistas")
    rel = _first(rel_root.get("relacoesTrabalhistas", []), "Dataprev/relações-trabalhistas")

    adm_s = rel.get("dataAdmissao")
    if not adm_s:
        raise FeatureBuildError("Dataprev/relações-trabalhistas: falta dataAdmissao")
    try:
        adm = _parse_date_ymd(adm_s)
    except Exception:
        raise FeatureBuildError("Dataprev/relações-trabalhistas: dataAdmissao inválida (YYYY-MM-DD)")

    enc_s = rel.get("dataEncerramento")
    emprego_ativo = 1 if not enc_s else 0
    tempo_emprego_meses = _months_between(adm, today)

    # ===== 3) Open Finance: Identificação → idade, tempo de relacionamento =====
    url_ident = _abs_url(request, path=OF_IDENT_PATH)
    h_of      = _auth_headers(request, prefer_header=True, fallback_token=OPENFIN_TOKEN)
    ident_resp = requests.get(url_ident, params={"cpf": cpf}, headers=h_of, timeout=5)
    ident = _json_ok(ident_resp, "OpenFinance/identificação")

    birth_s = ident.get("birthDate")
    start_s = ident.get("startDate")
    if not birth_s or not start_s:
        raise FeatureBuildError("OpenFinance/identificação: falta birthDate/startDate")

    try:
        birth = _parse_date_ymd(birth_s)
        start = _parse_date_ymd(start_s)
    except Exception:
        raise FeatureBuildError("OpenFinance/identificação: datas inválidas (YYYY-MM-DD)")

    idade = max(18, today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day)))
    tempo_rel_banco_meses = _months_between(start, today)

    # ===== 4) Open Finance: Accounts → renda (6m), coef_var, % meses negativos =====
    url_acc = _abs_url(request, path=OF_ACCOUNTS_PATH)
    acc_resp = requests.get(url_acc, params={"cpf": cpf}, headers=h_of, timeout=5)
    acc_root = _json_ok(acc_resp, "OpenFinance/accounts")
    accounts = acc_root.get("data", [])
    if not isinstance(accounts, list) or not accounts:
        raise FeatureBuildError("OpenFinance/accounts: nenhuma conta encontrada")

    # Período: últimos 6 meses (YYYY-MM) e datas para filtro
    months6: List[str] = _last_n_months(6, today)
    date_from = (today.replace(day=1) - timedelta(days=180)).strftime("%Y-%m-%d")
    date_to   = today.strftime("%Y-%m-%d")

    # Agregadores
    income_per_month: Dict[str, Decimal] = {m: Decimal("0") for m in months6}
    net_per_month: Dict[str, Decimal] = {m: Decimal("0") for m in months6}

    for acc in accounts:
        acc_id = acc.get("accountId")
        if not acc_id:
            continue

        # Transações no intervalo
        tx_url = _abs_url(request, path=OF_ACC_TX_PATH.format(account_id=acc_id))
        tx_resp = requests.get(
            tx_url,
            params={"from": date_from, "to": date_to},
            headers=h_of,
            timeout=5
        )
        tx_root = _json_ok(tx_resp, f"OpenFinance/transactions ({acc_id})")
        txs = tx_root.get("data", [])
        if not isinstance(txs, list):
            raise FeatureBuildError(f"OpenFinance/transactions: campo 'data' inválido ({acc_id})")

        for tx in txs:
            d_s = tx.get("bookingDate")
            amt = _parse_money(tx.get("amount"))
            cdt = (tx.get("creditDebitType") or "").upper()  # "CREDIT"/"DEBIT"
            if not d_s:
                continue
            ym = d_s[:7]
            if ym not in income_per_month:
                continue  # fora da janela 6m
            if cdt == "CREDIT":
                income_per_month[ym] += amt
                net_per_month[ym]    += amt
            elif cdt == "DEBIT":
                net_per_month[ym]    -= amt

    # renda_media_6m e coef_var_renda
    monthly_vals = [income_per_month[m] for m in months6]  # mantém meses sem renda como 0
    total_income_6m = sum(monthly_vals, Decimal("0"))
    renda_media_6m = float( (total_income_6m / Decimal(6)) if Decimal(6) > 0 else Decimal("0") )

    # coeficiente de variação = std / mean (se mean==0, define 0)
    if total_income_6m > 0:
        mean = total_income_6m / Decimal(6)
        # variância amostral (n-1); se n==1 (não é o caso aqui), cairia em 0
        diffsq = [(x - mean) ** 2 for x in monthly_vals]
        variance = sum(diffsq, Decimal("0")) / Decimal(5)
        std = variance.sqrt()
        coef_var_renda = float(std / mean) if mean != 0 else 0.0
    else:
        coef_var_renda = 0.0

    # % meses com saldo líquido do mês negativo (proxy de "saldo negativo")
    neg_months = sum(1 for m in months6 if net_per_month[m] < 0)
    pct_meses_saldo_neg_6m = float(neg_months / 6.0)

    # ===== 5) Open Finance: Cartões → utilização, % mínimo 3m, nº faturas vencidas 3m =====
    url_cc = _abs_url(request, path=OF_CC_ACCOUNTS)
    cc_resp = requests.get(url_cc, params={"cpf": cpf}, headers=h_of, timeout=5)
    cc_root = _json_ok(cc_resp, "OpenFinance/cartões")
    cc_accounts = cc_root.get("data", [])
    if not isinstance(cc_accounts, list) or not cc_accounts:
        raise FeatureBuildError("OpenFinance/cartões: nenhuma conta de cartão encontrada")

    # Janelas
    ym_3m = _last_n_months(3, today)  # ex.: ['2025-07','2025-08','2025-09'] se hoje for 2025-10
    ym_from = ym_3m[0]
    ym_to   = ym_3m[-1]

    # Utilização: (gasto de bills OPEN) / soma(limites). Se não houver OPEN, usa gastos últimos 30 dias.
    total_limit = Decimal("0")
    spend_open_bills = Decimal("0")

    # Para % mínimo 3m e nº vencidas 3m
    minimo_ratios: List[Decimal] = []
    overdue_count_3m = 0

    for cca in cc_accounts:
        cc_id = cca.get("accountId")
        limit_amt = _parse_money(cca.get("creditLimit"))
        total_limit += limit_amt

        # Bills (últimos 3 meses, qualquer status; depois filtramos por status)
        bills_url = _abs_url(request, path=OF_CC_BILLS_PATH.format(account_id=cc_id))
        bills_resp = requests.get(
            bills_url,
            params={"from": ym_from, "to": ym_to},
            headers=h_of,
            timeout=5
        )
        bills_root = _json_ok(bills_resp, f"OpenFinance/bills ({cc_id})")
        bills = bills_root.get("data", [])
        if not isinstance(bills, list):
            raise FeatureBuildError(f"OpenFinance/bills: campo 'data' inválido ({cc_id})")

        # Para cada bill, buscamos transactions?billId=...
        for bill in bills:
            bill_id = bill.get("billId")
            due_s   = bill.get("dueDate")
            status  = (bill.get("status") or "").upper()
            min_pay = _parse_money(bill.get("minimumPayment"))

            if status == "OVERDUE":
                overdue_count_3m += 1

            if not bill_id or not due_s:
                continue

            # Transações da fatura
            cc_tx_url = _abs_url(request, path=OF_CC_TX_PATH.format(account_id=cc_id))
            cc_tx_resp = requests.get(cc_tx_url, params={"billId": bill_id}, headers=h_of, timeout=5)
            cc_tx_root = _json_ok(cc_tx_resp, f"OpenFinance/cc-transactions ({cc_id}, {bill_id})")
            cc_txs = cc_tx_root.get("data", [])
            if not isinstance(cc_txs, list):
                raise FeatureBuildError(f"OpenFinance/cc-transactions: campo 'data' inválido ({cc_id},{bill_id})")

            bill_total = Decimal("0")
            for t in cc_txs:
                bill_total += _parse_money(t.get("amount"))

            # Utilização: somamos o total das bills com status OPEN
            if status == "OPEN":
                spend_open_bills += bill_total

            # pct_minimo_pago_3m ~ minimumPayment / total_da_fatura (se total>0)
            if bill_total > 0:
                minimo_ratios.append( (min_pay / bill_total) )

    # Utilização do cartão (clamp não necessário, mas evita divisão por zero)
    if total_limit > 0:
        utilizacao_cartao = float(spend_open_bills / total_limit)
    else:
        # Sem limite disponível → consideramos utilização 0
        utilizacao_cartao = 0.0

    # % mínimo 3m = média dos ratios (se houver faturas com total>0)
    if minimo_ratios:
        pct_minimo_pago_3m = float( sum(minimo_ratios, Decimal("0")) / Decimal(len(minimo_ratios)) )
    else:
        pct_minimo_pago_3m = 0.0

    num_faturas_vencidas_3m = int(overdue_count_3m)

    # ===== 6) Open Finance: Loans → endividamento_total, parcelas_renda, DPD_max_12m =====
    url_loans = _abs_url(request, path=OF_LOANS_CONTRACTS)
    loans_resp = requests.get(url_loans, params={"cpf": cpf}, headers=h_of, timeout=5)
    loans_root = _json_ok(loans_resp, "OpenFinance/loans")
    loans = loans_root.get("data", [])
    if not isinstance(loans, list):
        raise FeatureBuildError("OpenFinance/loans: campo 'data' inválido")

    total_outstanding = Decimal("0")
    contract_ids: List[str] = []
    for c in loans:
        cid = c.get("contractId")
        if cid:
            contract_ids.append(cid)
        total_outstanding += _parse_money(c.get("outstanding"))

    renda_mensal = Decimal(str(renda_media_6m))
    renda_anual = renda_mensal * Decimal(12)
    endividamento_total = float((total_outstanding / renda_anual) if renda_anual > 0 else Decimal("0"))

    # Parcelas no próximo ~35 dias
    today_ord = today.toordinal()
    horizonte_ord = today_ord + 35
    soma_parcelas_prox_mes = Decimal("0")

    # DPD máximo nos últimos 12 meses
    inicio_janela_12m = date(today.year - 1, today.month, today.day)
    dpd_max = 0

    for contract_id in contract_ids:
        # installments
        inst_url = _abs_url(request, path=OF_LOAN_INST_PATH.format(contract_id=contract_id))
        inst_resp = requests.get(inst_url, headers=h_of, timeout=5)
        inst_root = _json_ok(inst_resp, f"OpenFinance/installments ({contract_id})")
        installments = inst_root.get("data", [])
        if not isinstance(installments, list):
            raise FeatureBuildError(f"OpenFinance/installments: campo 'data' inválido ({contract_id})")

        # payments
        pay_url = _abs_url(request, path=OF_LOAN_PAY_PATH.format(contract_id=contract_id))
        pay_resp = requests.get(pay_url, headers=h_of, timeout=5)
        pay_root = _json_ok(pay_resp, f"OpenFinance/payments ({contract_id})")
        payments = pay_root.get("data", [])
        payments_by_inst: Dict[str, date] = {}
        if isinstance(payments, list):
            for p in payments:
                inst_id = p.get("instalmentId")
                pdate_s = p.get("paymentDate")
                if inst_id and pdate_s:
                    payments_by_inst[inst_id] = _parse_date_ymd(pdate_s)

        # percorre parcelas
        for inst in installments:
            inst_id = inst.get("instalmentId")
            due_s = inst.get("dueDate")
            amt_s = inst.get("amount")
            status = (inst.get("status") or "").upper()
            if not due_s or not amt_s:
                continue

            due = _parse_date_ymd(due_s)
            amt = _parse_money(amt_s)

            # soma parcelas do próximo mês (~35 dias)
            if today_ord <= due.toordinal() <= horizonte_ord:
                soma_parcelas_prox_mes += amt

            # DPD na janela de 12 meses
            if due >= inicio_janela_12m:
                if status == "PAID" and inst_id in payments_by_inst:
                    dpd = (payments_by_inst[inst_id] - due).days
                    dpd_max = max(dpd_max, max(0, dpd))
                else:
                    if due < today:
                        dpd = (today - due).days
                        dpd_max = max(dpd_max, dpd)

    parcelas_renda = float((soma_parcelas_prox_mes / renda_mensal) if renda_mensal > 0 else Decimal("0"))
    DPD_max_12m = int(dpd_max)

    # ===== 7) Monta features + overrides =====
    features: Dict[str, Any] = {
        "beneficio_ativo": beneficio_ativo,
        "tempo_beneficio_meses": tempo_beneficio_meses,
        "emprego_ativo": emprego_ativo,
        "tempo_emprego_meses": tempo_emprego_meses,
        "renda_media_6m": float(renda_media_6m),
        "coef_var_renda": float(coef_var_renda),
        "pct_meses_saldo_neg_6m": float(pct_meses_saldo_neg_6m),
        "utilizacao_cartao": float(utilizacao_cartao),
        "pct_minimo_pago_3m": float(pct_minimo_pago_3m),
        "num_faturas_vencidas_3m": int(num_faturas_vencidas_3m),
        "endividamento_total": float(endividamento_total),
        "parcelas_renda": float(parcelas_renda),
        "DPD_max_12m": int(DPD_max_12m),
        "idade": int(idade),
        "tempo_rel_banco_meses": int(tempo_rel_banco_meses),
    }

    for k, v in overrides.items():
        if k in features and v is not None:
            features[k] = v

    # Validação final: todas as 15 chaves presentes
    required = {
        "beneficio_ativo","tempo_beneficio_meses",
        "emprego_ativo","tempo_emprego_meses",
        "renda_media_6m","coef_var_renda","pct_meses_saldo_neg_6m",
        "utilizacao_cartao","pct_minimo_pago_3m","num_faturas_vencidas_3m",
        "endividamento_total","parcelas_renda","DPD_max_12m",
        "idade","tempo_rel_banco_meses"
    }
    miss = [k for k in required if k not in features]
    if miss:
        raise FeatureBuildError(f"Features incompletas: ausentes {miss}")

    return features
