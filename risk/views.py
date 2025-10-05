import json
import pandas as pd
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from risk.serializers import ScoreRequest
from risk.services.registry import registry
from risk.calculators.pmt import pmt_price, eff_annual_from_monthly
from risk.calculators.cet import cet_from_flows

@csrf_exempt
def score_view(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Use POST com JSON.")
    try:
        payload = json.loads(request.body.decode("utf-8"))
        req = ScoreRequest.from_json(payload)
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    # --- MONTA O DATAFRAME NA MESMA "CARINHA" DO TREINO ---
    # copia as features do request
    f = dict(req.features or {})

    # feature derivada: 1 se CLT e INSS ativos ao mesmo tempo, senão 0
    f["ambos"] = int(bool(f.get("beneficio_ativo", 0)) and bool(f.get("emprego_ativo", 0)))

    # ordem de colunas usada no treino (as 16)
    expected_cols = [
        "beneficio_ativo",
        "tempo_beneficio_meses",
        "emprego_ativo",
        "tempo_emprego_meses",
        "renda_media_6m",
        "coef_var_renda",
        "pct_meses_saldo_neg_6m",
        "utilizacao_cartao",
        "pct_minimo_pago_3m",
        "num_faturas_vencidas_3m",
        "endividamento_total",
        "parcelas_renda",
        "DPD_max_12m",
        "idade",
        "tempo_rel_banco_meses",
        "ambos",                       
    ]

    # garante presença de todas as colunas (faltando -> preenche com 0.0)
    row = {c: float(f.get(c, 0.0)) for c in expected_cols}
    X_df = pd.DataFrame([row], columns=expected_cols)

    # 1) PD
    model = registry.get_pd_model()
    pd_hat = float(model.predict_proba(X_df)[0, 1])

    # 2) Score/Banda
    sc = registry.get_scorecard()
    score, band = sc.score_and_band(pd_hat)

    # 3) Pricing (taxa mensal sugerida)
    pricing = registry.get_pricing()
    rate = float(pricing.suggest_rate(pd_hat))

    # 4) PMT e CET (se amount/term vierem)
    result = {
        "pd": round(pd_hat, 6),
        "score": int(score),
        "band": band,
        "rate_monthly": round(rate, 6),
        "rate_yearly_eff": round(eff_annual_from_monthly(rate), 6),
        "model": {"name": "pd_logr1", "path": registry.model_path},
        "pricing": {"mode": pricing.mode},
    }

    if req.amount is not None and req.term_months is not None:
        try:
            pmt = pmt_price(rate, int(req.term_months), float(req.amount))
            result["installment"] = round(pmt, 2)

            cet_m, cet_y = cet_from_flows(
                pv=float(req.amount),
                rate_monthly=rate,
                n_months=int(req.term_months),
                fees=req.fees or {}
            )
            result["cet_monthly"] = round(cet_m, 6)
            result["cet_yearly"]  = round(cet_y, 6)
            result["fees"] = req.fees or {}
        except Exception as e:
            result["installment"] = None
            result["cet_monthly"] = None
            result["cet_yearly"] = None
            result["fees_error"] = str(e)

    return JsonResponse(result, status=200)