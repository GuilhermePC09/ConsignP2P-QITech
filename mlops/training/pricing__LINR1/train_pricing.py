# -*- coding: utf-8 -*-
"""
Treina o modelo pricing_linr1.joblib que mapeia PD -> taxa mensal sugerida.

Usos típicos:
1) Sem histórico (hackathon): gera curva-alvo por unit economics e ajusta LINR1.
   python mlops/training/pricing__LINR1/train_pricing.py \
     --pd-model mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib \
     --outdir mlops/training/risk__LINR1/outputs \
     --labels synthetic

2) Com histórico de taxa:
   python ... --labels historical --csv mlops/training/data/pricing_train.csv
   (csv deve ter colunas: pd, rate_monthly)
"""
import os, json, argparse, math, yaml
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.linear_model import LinearRegression
from sklearn.isotonic import IsotonicRegression

def ensure_dirs(path):
    for s in ("models", "plots", "reports"):
        os.makedirs(os.path.join(path, s), exist_ok=True)

def target_curve_from_unit_econ(pd_grid, conf):
    ue = conf["unit_economics"]
    fund = ue["funding_rate_monthly"]
    opex = ue["opex_rate_monthly"]
    lgd  = ue["lgd"]
    marg = ue["margin_monthly"]
    k    = ue.get("k_smoothing", 0.85)

    # risco mensal aproximado: PD_12m/12 * LGD (hazard flat)
    risk_month = (pd_grid / 12.0) * lgd * k
    rate = fund + opex + risk_month + marg
    return rate

def features(pd, degree):
    if degree == 1:
        return pd.reshape(-1,1)
    X = np.column_stack([pd, pd**2])  # polinômio leve
    return X

def fit_linr(pd_grid, y_target, degree, enforce_mono=True):
    # passo 1: regressão linear/polinomial
    X = features(pd_grid, degree)
    lr = LinearRegression(positive=True)  # força coeficientes >= 0 (monotonia ajuda)
    lr.fit(X, y_target)
    preds = lr.predict(X)

    if enforce_mono:
        # passo 2: isotônica por cima (apenas para garantir monotonia PD↑ → taxa↑)
        iso = IsotonicRegression(y_min=min(y_target), y_max=max(y_target), increasing=True, out_of_bounds="clip")
        preds = iso.fit_transform(pd_grid, preds)
        return ("linr+isotonic", (lr, iso))
    return ("linr", (lr, None))

def main(a):
    conf = yaml.safe_load(open(a.conf))
    outdir = a.outdir
    ensure_dirs(outdir)

    # grid de PD para treinar a função preço
    pd_min, pd_max = conf["training"]["pd_min"], conf["training"]["pd_max"]
    pd_grid = np.linspace(pd_min, pd_max, 200)

    if a.labels == "synthetic":
        y = target_curve_from_unit_econ(pd_grid, conf)
    elif a.labels == "historical":
        if not a.csv:
            raise SystemExit("--csv é obrigatório com labels=historical")
        df = pd.read_csv(a.csv)
        if not {"pd", "rate_monthly"} <= set(df.columns):
            raise SystemExit("CSV precisa de colunas: pd, rate_monthly")
        # recorta faixa e ordena
        df = df[(df["pd"].between(pd_min, pd_max))].sort_values("pd")
        pd_grid = df["pd"].values.astype(float)
        y = df["rate_monthly"].values.astype(float)
    else:
        raise SystemExit("labels deve ser 'synthetic' ou 'historical'")

    deg = int(conf["training"]["poly_degree"])
    tag, model_tuple = fit_linr(pd_grid, y, degree=deg, enforce_mono=conf["training"]["enforce_monotonic"])
    lr, iso = model_tuple

    # salva artefato como dict {type, lr, iso, caps}
    artifact = {
        "type": tag,
        "lr": lr,
        "iso": iso,
        "caps": conf["caps"],
    }
    model_path = os.path.join(outdir, "models", "pricing_linr1.joblib")
    dump(artifact, model_path)

    # salva meta
    meta = {
        "name": "pricing_linr1",
        "type": tag,
        "poly_degree": deg,
        "caps": conf["caps"],
        "labels": a.labels,
        "trained_on": "unit_economics" if a.labels=="synthetic" else a.csv,
    }
    with open(os.path.join(outdir, "reports", "pricing_meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print("[OK] Modelo salvo em:", model_path)
    print("[OK] Meta:", meta)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--conf", default="mlops/conf/pricing.yaml")
    p.add_argument("--outdir", default="mlops/training/pricing__LINR1/outputs")
    p.add_argument("--labels", choices=["synthetic", "historical"], default="synthetic")
    p.add_argument("--csv", help="CSV com colunas pd, rate_monthly (se labels=historical)")
    p.add_argument("--pd-model", help="não obrigatório; mantido para referência")
    a = p.parse_args()
    main(a)
