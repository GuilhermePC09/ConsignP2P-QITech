# -*- coding: utf-8 -*-
"""
Treina o modelo pricing_linr1.joblib que mapeia PD -> taxa mensal sugerida,
usando diretamente a base train_LOGR1.csv (12k linhas).

Modos de rótulo:
- labels=historical:
    * Se o CSV tiver 'rate_monthly', usa-a como y.
    * Se NÃO tiver, calcula a taxa-alvo por unit economics (pricing.yaml).
- labels=synthetic:
    * Gera uma curva-alvo uniforme em um grid de PD.

Fonte do PD:
- --pd-source pd_true  : usa a coluna 'pd_true' do CSV.
- --pd-source pd_hat   : calcula com o seu modelo de risco (joblib) a partir de FEATURE_ORDER.

Exemplos:
1) Usar pd_true (recomendado se confiável) e gerar taxa pela unit economics:
   python mlops/training/pricing__LINR1/train_pricing.py \
     --conf mlops/conf/pricing.yaml \
     --outdir mlops/training/pricing__LINR1/outputs \
     --labels historical \
     --csv mlops/training/data/train_LOGR1.csv \
     --pd-source pd_true

2) Usar pd_hat (via pd_logr1.joblib) e gerar taxa pela unit economics:
   python ... --labels historical --csv mlops/training/data/train_LOGR1.csv \
     --pd-source pd_hat \
     --pd-model mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib
"""
import os, json, argparse, math, yaml
import numpy as np
import pandas as pd
from joblib import dump, load
from sklearn.linear_model import LinearRegression
from sklearn.isotonic import IsotonicRegression

# ======= ajuste aqui se necessário (ordem das features do seu LOGR1) =======
FEATURE_ORDER = [
    'beneficio_ativo','tempo_beneficio_meses',
    'emprego_ativo','tempo_emprego_meses',
    'renda_media_6m','coef_var_renda','pct_meses_saldo_neg_6m',
    'utilizacao_cartao','pct_minimo_pago_3m','num_faturas_vencidas_3m',
    'endividamento_total','parcelas_renda','DPD_max_12m',
    'idade','tempo_rel_banco_meses'
]
# ==========================================================================

def ensure_dirs(path):
    for s in ("models", "plots", "reports"):
        os.makedirs(os.path.join(path, s), exist_ok=True)

def load_conf(path):
    if not os.path.exists(path):
        raise SystemExit(f"[ERRO] Config não encontrada: {path}")
    with open(path, "r") as f:
        conf = yaml.safe_load(f)
    if not conf:
        raise SystemExit(f"[ERRO] Config vazia/ inválida: {path}")

    # defaults seguros
    conf.setdefault("mode", "model")
    conf.setdefault("caps", {"min_rate_monthly": 0.017, "max_rate_monthly": 0.045})
    conf.setdefault("unit_economics", {
        "funding_rate_monthly": 0.018,
        "opex_rate_monthly": 0.004,
        "lgd": 0.45,
        "margin_monthly": 0.006,
        "hazard_assumption": "flat",
        "k_smoothing": 0.85,
    })
    conf.setdefault("training", {
        "poly_degree": 2,
        "enforce_monotonic": True,
        "pd_min": 0.002,
        "pd_max": 0.60,
    })
    return conf

def target_curve_from_unit_econ(pd_vals, conf):
    ue = conf["unit_economics"]
    fund = float(ue["funding_rate_monthly"])
    opex = float(ue["opex_rate_monthly"])
    lgd  = float(ue["lgd"])
    marg = float(ue["margin_monthly"])
    k    = float(ue.get("k_smoothing", 0.85))
    # risco mensal aproximado (hazard flat)
    risk_month = (pd_vals / 12.0) * lgd * k
    rate = fund + opex + risk_month + marg
    return rate

def features(pd, degree):
    pd = np.asarray(pd, dtype=float).reshape(-1)
    if degree == 1:
        return pd.reshape(-1,1)
    return np.column_stack([pd, pd**2])  # polinômio leve

def fit_linr(pd_vals, y_target, degree, enforce_mono=True):
    X = features(pd_vals, degree)
    lr = LinearRegression(positive=True)  # coef >= 0 ajuda a monotonicidade
    lr.fit(X, y_target)
    preds = lr.predict(X)

    if enforce_mono:
        iso = IsotonicRegression(
            y_min=float(np.min(y_target)), y_max=float(np.max(y_target)),
            increasing=True, out_of_bounds="clip"
        )
        preds = iso.fit_transform(pd_vals, preds)
        return ("linr+isotonic", (lr, iso))
    return ("linr", (lr, None))

def get_pd_series(df, pd_source, pd_model_path):
    """
    Retorna uma série de PD no intervalo [0,1] a partir de:
    - 'pd_true' (coluna da base), ou
    - 'pd_hat' calculado com o joblib do LOGR1.
    Corrige o typo 'eneficio_ativo' -> 'beneficio_ativo' se existir.
    """
    # corrige header com typo caso exista
    if "eneficio_ativo" in df.columns and "beneficio_ativo" not in df.columns:
        df.rename(columns={"eneficio_ativo": "beneficio_ativo"}, inplace=True)

    if pd_source == "pd_true":
        if "pd_true" not in df.columns:
            raise SystemExit("[ERRO] pd_source=pd_true mas a coluna 'pd_true' não existe no CSV.")
        return df["pd_true"].astype(float).values

    # pd_hat
    if pd_model_path is None or not os.path.exists(pd_model_path):
        raise SystemExit("[ERRO] pd_source=pd_hat requer --pd-model com caminho válido para o joblib do LOGR1.")
    model = load(pd_model_path)

    missing = [c for c in FEATURE_ORDER if c not in df.columns]
    if missing:
        raise SystemExit(f"[ERRO] faltam features no CSV para calcular pd_hat: {missing}")

    X = df[FEATURE_ORDER].astype(float).values
    pd_hat = model.predict_proba(X)[:, 1]
    return pd_hat

def main(a):
    conf = load_conf(a.conf)
    outdir = a.outdir
    ensure_dirs(outdir)

    # faixa operacional de PD p/ treino
    pd_min = float(conf["training"]["pd_min"])
    pd_max = float(conf["training"]["pd_max"])

    if a.labels == "synthetic":
        # grid uniforme (útil para demonstração pura)
        pd_vals = np.linspace(pd_min, pd_max, 200)
        y = target_curve_from_unit_econ(pd_vals, conf)

    elif a.labels == "historical":
        if not a.csv:
            raise SystemExit("--csv é obrigatório com labels=historical")
        df = pd.read_csv(a.csv)

        # obtém a série de PD (true ou hat)
        pd_vals = get_pd_series(df, a.pd_source, a.pd_model)

        # limita à faixa e remove NaN/inf
        m = np.isfinite(pd_vals)
        pd_vals = pd_vals[m]
        df = df.loc[m].copy()
        pd_vals = np.clip(pd_vals, pd_min, pd_max)

        # rótulo y:
        if "rate_monthly" in df.columns:
            y = df.loc[m, "rate_monthly"].astype(float).values
        else:
            # gera taxa-alvo pela unit economics sobre o PD da base
            y = target_curve_from_unit_econ(pd_vals, conf)

        # ordena por PD (ajuda isotônica)
        ord_idx = np.argsort(pd_vals)
        pd_vals = pd_vals[ord_idx]
        y = y[ord_idx]

    else:
        raise SystemExit("labels deve ser 'synthetic' ou 'historical'")

    # treino do LINR1 (linear/quadrático + isotônica opcional)
    deg = int(conf["training"]["poly_degree"])
    tag, (lr, iso) = fit_linr(pd_vals, y, degree=deg,
                              enforce_mono=bool(conf["training"]["enforce_monotonic"]))

    # artefato do pricing
    artifact = {"type": tag, "lr": lr, "iso": iso, "caps": conf["caps"]}
    model_path = os.path.join(outdir, "models", "pricing_linr1.joblib")
    dump(artifact, model_path)

    meta = {
        "name": "pricing_linr1",
        "type": tag,
        "poly_degree": deg,
        "caps": conf["caps"],
        "labels": a.labels,
        "trained_on": os.path.abspath(a.csv) if a.labels=="historical" else "unit_economics",
        "pd_source": a.pd_source,
        "n_samples": int(len(pd_vals)),
        "conf_path": os.path.abspath(a.conf),
    }
    with open(os.path.join(outdir, "reports", "pricing_meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print("[OK] Modelo salvo em:", model_path)
    print("[OK] Meta:", meta)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--conf", default="mlops/conf/pricing.yaml")
    p.add_argument("--outdir", default="mlops/training/pricing__LINR1/outputs")
    p.add_argument("--labels", choices=["synthetic", "historical"], default="historical")
    p.add_argument("--csv", help="CSV base (ex.: mlops/training/data/train_LOGR1.csv)")
    p.add_argument("--pd-source", choices=["pd_true", "pd_hat"], default="pd_true",
                   help="Fonte do PD para pricing. 'pd_hat' usa --pd-model.")
    p.add_argument("--pd-model", help="Caminho do joblib do LOGR1, obrigatório se --pd-source=pd_hat")
    a = p.parse_args()
    main(a)
