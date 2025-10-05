import json
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
        X = [req.to_feature_vector()]
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    # 1) PD
    model = registry.get_pd_model()
    pd_hat = float(model.predict_proba(X)[0, 1])

    # 2) Score/Banda
    sc = registry.get_scorecard()
    score, band = sc.score_and_band(pd_hat)

    # 3) Pricing (taxa mensal sugerida pela LINR1/isotônica + caps)
    pricing = registry.get_pricing()
    rate = float(pricing.suggest_rate(pd_hat))

    # 4) Base do retorno (CET anual bruto = (1+i)^12 - 1)
    result = {
        "pd": round(pd_hat, 6),
        "score": int(score),
        "band": band,
        "rate_monthly": round(rate, 6),
        "rate_yearly_eff": round(eff_annual_from_monthly(rate), 6),
        "model": {"name": "pd_logr1", "path": registry.model_path},
        "pricing": pricing.info(),  # modo + caps + poly_degree
    }

    # 4.1) Vale a pena emprestar? (unit economics)
    # Requer o prazo para “mensalizar” o risco (pró-rata n/12)
    if req.term_months is not None:
        ue = pricing.components(pd_12m=pd_hat, n_months=int(req.term_months))
        i_min = float(ue["i_min"])
        ok = (rate >= i_min)
        result["unit_economics"] = {
            "el_over_P": round(ue["el_over_P"], 6),                     # % do principal
            "risk_component_monthly": round(ue["risk_component_monthly"], 6),
            "funding": round(ue["funding"], 6),
            "opex": round(ue["opex"], 6),
            "margin_target": round(ue["margin_target"], 6),
            "i_min_monthly": round(i_min, 6),
            "rate_vs_min_bps": int(round((rate - i_min) * 10000)),      # folga em bps
            "ok_to_lend": bool(ok),
        }

    # 4.2) PMT e CET com tarifas (se amount/term vierem)
    if req.amount is not None and req.term_months is not None:
        try:
            pmt = pmt_price(rate, int(req.term_months), float(req.amount))
            result["installment"] = round(pmt, 2)

            cet_m, cet_y = cet_from_flows(
                pv=float(req.amount),
                rate_monthly=rate,
                n_months=int(req.term_months),
                fees=req.fees or {},
            )
            result["cet_monthly"] = round(cet_m, 6)
            result["cet_yearly"] = round(cet_y, 6)
            result["fees"] = req.fees or {}
        except Exception as e:
            # não derruba a resposta se tiver erro de CET
            result["installment"] = None
            result["cet_monthly"] = None
            result["cet_yearly"] = None
            result["fees_error"] = str(e)

    return JsonResponse(result, status=200)
