# -*- coding: utf-8 -*-
"""
Gera um CSV com colunas 'pd' e 'rate_monthly' a partir da sua base train_LOGR1.csv,
para treinar o LINR1 com labels=historical no script atual.

Uso:
  # usando pd_true (mais simples)
  python mlops/training/pricing__LINR1/make_pricing_train.py \
    --csv mlops/training/data/train_LOGR1.csv \
    --conf mlops/conf/pricing.yaml \
    --pd-source pd_true \
    --out mlops/training/pricing__LINR1/data/pricing_train.csv

  # usando pd_hat (calcula com seu pd_logr1.joblib)
  python .../make_pricing_train.py \
    --csv mlops/training/data/train_LOGR1.csv \
    --conf mlops/conf/pricing.yaml \
    --pd-source pd_hat \
    --pd-model mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib \
    --out mlops/training/pricing__LINR1/data/pricing_train.csv
"""
import os, argparse, yaml
import numpy as np
import pandas as pd
from joblib import load

FEATURE_ORDER = [
    'beneficio_ativo','tempo_beneficio_meses',
    'emprego_ativo','tempo_emprego_meses',
    'renda_media_6m','coef_var_renda','pct_meses_saldo_neg_6m',
    'utilizacao_cartao','pct_minimo_pago_3m','num_faturas_vencidas_3m',
    'endividamento_total','parcelas_renda','DPD_max_12m',
    'idade','tempo_rel_banco_meses'
]

def load_conf(path):
    with open(path, "r") as f:
        conf = yaml.safe_load(f)
    # defaults mínimos
    caps = conf.get("caps", {"min_rate_monthly":0.017, "max_rate_monthly":0.045})
    ue   = conf.get("unit_economics", {})
    fund = float(ue.get("funding_rate_monthly", 0.018))
    opex = float(ue.get("opex_rate_monthly", 0.004))
    lgd  = float(ue.get("lgd", 0.45))
    marg = float(ue.get("margin_monthly", 0.006))
    k    = float(ue.get("k_smoothing", 0.85))
    tr   = conf.get("training", {})
    pd_min = float(tr.get("pd_min", 0.002))
    pd_max = float(tr.get("pd_max", 0.60))
    return caps, (fund, opex, lgd, marg, k), (pd_min, pd_max)

def compute_rate(pd_vals, econ, caps):
    fund, opex, lgd, marg, k = econ
    rate = fund + opex + (pd_vals/12.0)*lgd*k + marg
    rate = np.clip(rate, caps["min_rate_monthly"], caps["max_rate_monthly"])
    return rate

def main(args):
    caps, econ, (pd_min, pd_max) = load_conf(args.conf)
    df = pd.read_csv(args.csv)

    # corrige eventual typo no cabeçalho
    if "eneficio_ativo" in df.columns and "beneficio_ativo" not in df.columns:
        df.rename(columns={"eneficio_ativo":"beneficio_ativo"}, inplace=True)

    if args.pd_source == "pd_true":
        if "pd_true" not in df.columns:
            raise SystemExit("Coluna 'pd_true' não encontrada no CSV.")
        pd_vals = df["pd_true"].astype(float).values
    else:
        if not args.pd_model or not os.path.exists(args.pd_model):
            raise SystemExit("--pd-model é obrigatório e deve existir quando --pd-source=pd_hat.")
        missing = [c for c in FEATURE_ORDER if c not in df.columns]
        if missing:
            raise SystemExit(f"Faltam features no CSV para calcular pd_hat: {missing}")
        model = load(args.pd_model)
        X = df[FEATURE_ORDER].astype(float).values
        pd_vals = model.predict_proba(X)[:,1]

    pd_vals = np.clip(pd_vals, pd_min, pd_max)
    rate = compute_rate(pd_vals, econ, caps)

    out = pd.DataFrame({"pd": pd_vals, "rate_monthly": rate})
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out, index=False)
    print("[OK] pricing_train salvo em:", args.out)
    print(out.head())

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="mlops/training/data/train_LOGR1.csv")
    ap.add_argument("--conf", default="mlops/conf/pricing.yaml")
    ap.add_argument("--pd-source", choices=["pd_true","pd_hat"], default="pd_true")
    ap.add_argument("--pd-model", help="joblib do LOGR1 (se pd_hat)")
    ap.add_argument("--out", required=True, help="Arquivo de saída (pd, rate_monthly)")
    args = ap.parse_args()
    main(args)
