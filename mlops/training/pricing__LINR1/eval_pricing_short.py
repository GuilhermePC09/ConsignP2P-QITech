import math
import os, yaml, argparse, numpy as np, pandas as pd, matplotlib.pyplot as plt
from joblib import load
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def load_conf(path):
    with open(path) as f: c = yaml.safe_load(f)
    ue = c["unit_economics"]; caps = c["caps"]
    return (float(ue["funding_rate_monthly"]), float(ue["opex_rate_monthly"]),
            float(ue["lgd"]), float(ue["margin_monthly"]), float(ue.get("k_smoothing",0.85))), caps

def target_rate(pd_vals, econ, caps):
    fund, opex, lgd, margin, k = econ
    y = fund + opex + (pd_vals/12.0)*lgd*k + margin
    return np.clip(y, caps["min_rate_monthly"], caps["max_rate_monthly"])

def predict_rate(art, pd_vals, caps):
    lr, iso = art["lr"], art.get("iso")
    pd_vals = np.asarray(pd_vals).reshape(-1)
    deg = 2 if hasattr(lr, "coef_") and getattr(lr, "coef_", None) is not None and len(np.ravel(lr.coef_))==2 else 1
    X = pd_vals.reshape(-1,1) if deg==1 else np.column_stack([pd_vals, pd_vals**2])
    y = lr.predict(X)
    if iso is not None: y = iso.predict(pd_vals)
    return np.clip(y, caps["min_rate_monthly"], caps["max_rate_monthly"])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mlops/training/pricing__LINR1/outputs/models/pricing_linr1.joblib")
    ap.add_argument("--conf",  default="mlops/conf/pricing.yaml")
    ap.add_argument("--csv",   default="mlops/training/pricing__LINR1/data/pricing_train.csv")  # colunas: pd[, rate_monthly]
    a = ap.parse_args()

    art = load(a.model)
    econ, caps = load_conf(a.conf)
    df = pd.read_csv(a.csv)

    if "pd" not in df.columns: raise SystemExit("CSV precisa de coluna 'pd'.")
    pd_vals = df["pd"].astype(float).clip(0.002, 0.60).values
    y_true = df["rate_monthly"].astype(float).values if "rate_monthly" in df.columns else target_rate(pd_vals, econ, caps)
    y_pred = predict_rate(art, pd_vals, caps)

    # métricas em bps
    mae  = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = math.sqrt(mse)
    r2   = r2_score(y_true, y_pred)
    maxae = np.max(np.abs(y_pred - y_true))
    to_bps = lambda x: round(x*1e4, 2)  # 0.0001 = 1 bp

    # monotonicidade
    o = np.argsort(pd_vals)
    mono_ok = bool(np.all(np.diff(y_pred[o]) >= -1e-12))

    # prints
    print({
        "MAE_bps": to_bps(mae),
        "RMSE_bps": to_bps(rmse),
        "MaxAE_bps": to_bps(maxae),
        "R2": round(float(r2), 6),
        "Monotonic": mono_ok,
        "Cap_min_%": round(float(np.mean(y_pred <= caps["min_rate_monthly"])*100),2),
        "Cap_max_%": round(float(np.mean(y_pred >= caps["max_rate_monthly"])*100),2),
    })

    # erros por decis de PD
    df_eval = pd.DataFrame({"pd": pd_vals, "y_true": y_true, "y_pred": y_pred, "err": y_pred - y_true})
    df_eval["decile"] = pd.qcut(df_eval["pd"], 10, labels=False, duplicates="drop")
    print(df_eval.groupby("decile")["err"].agg(["count","mean","median","std"]).assign(
        mean_bps=lambda x: x["mean"]*1e4, median_bps=lambda x: x["median"]*1e4, std_bps=lambda x: x["std"]*1e4
    ))

    # plot rápido
    plt.figure(figsize=(6,5))
    plt.scatter(pd_vals, y_true, s=8, alpha=0.4, label="alvo")
    plt.plot(pd_vals[o], y_pred[o], lw=2, label="modelo")
    plt.xlabel("PD (12m)"); plt.ylabel("Taxa mensal"); plt.title("PD vs taxa — alvo x modelo"); plt.legend(); plt.grid(True)
    plt.tight_layout(); plt.show()

    plt.figure(figsize=(6,4))
    plt.scatter(pd_vals, y_pred - y_true, s=8, alpha=0.5)
    plt.axhline(0, ls="--"); plt.xlabel("PD (12m)"); plt.ylabel("Resíduo (pred - alvo)")
    plt.title("Resíduos"); plt.grid(True); plt.tight_layout(); plt.show()
