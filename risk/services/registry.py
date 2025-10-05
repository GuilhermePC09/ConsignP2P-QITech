# risk/services/registry.py
import os, yaml
import numpy as np
from joblib import load
from threading import Lock
from risk.odds import Scorecard

class _PricingWrapper:
    def __init__(self, artifact: dict, caps_fallback: dict | None = None, ue_defaults: dict | None = None):
        self.artifact = artifact or {}
        self.caps = self.artifact.get("caps") or (caps_fallback or {})
        self.ue = ue_defaults or {}

    # --- helpers de config
    @property
    def mode(self) -> str:
        # compat com código antigo que lia pricing.mode
        return self.artifact.get("type") or "unknown"

    @property
    def poly_degree(self) -> int | None:
        lr = self.artifact.get("lr")
        coef = getattr(lr, "coef_", None)
        if coef is None:
            return None
        return 2 if np.size(coef) >= 2 else 1

    def info(self) -> dict:
        return {
            "mode": self.mode,
            "poly_degree": self.poly_degree,
            "caps": self.caps,
        }

    def _ue(self, key: str, default: float = 0.0) -> float:
        val = self.ue.get(key, default)
        return float(0.0 if val is None else val)

    # --- precificação pelo modelo treinado (LINR1 +/- isotônica)
    def suggest_rate(self, pd_val: float) -> float:
        lr = self.artifact.get("lr")
        iso = self.artifact.get("iso")
        if lr is None:
            raise RuntimeError("Artifact de pricing inválido (faltando 'lr').")

        pd_arr = np.array([float(pd_val)], dtype=float)
        deg = 2 if (getattr(lr, "coef_", None) is not None and np.size(lr.coef_) >= 2) else 1
        X = pd_arr.reshape(-1, 1) if deg == 1 else np.column_stack([pd_arr, pd_arr**2])

        y = float(lr.predict(X)[0])
        if iso is not None:
            y = float(iso.predict(pd_arr)[0])

        if self.caps:
            y = float(np.clip(
                y,
                self.caps.get("min_rate_monthly", -np.inf),
                self.caps.get("max_rate_monthly",  np.inf),
            ))
        return y

    # --- regra mínima (funding + opex + risco + margem)
    def min_rate(
        self,
        pd_12m: float,
        n_months: int,
        *,
        lgd: float | None = None,
        funding: float | None = None,
        opex: float | None = None,
        margin: float | None = None,
    ) -> float:
        lgd     = float(self._ue("lgd", 0.45) if lgd     is None else lgd)
        funding = float(self._ue("funding_rate_monthly", 0.008) if funding is None else funding)
        opex    = float(self._ue("opex_rate_monthly",     0.003) if opex    is None else opex)
        margin  = float(self._ue("margin_monthly",        0.002) if margin  is None else margin)

        # EAD médio ~ 50% do principal (Price) -> EL/P = PD * LGD * 0.5
        el_over_P = float(pd_12m) * lgd * 0.5
        # "Mensaliza" pró-rata no hackathon: divide por (n/12)
        risk_month = el_over_P / (max(int(n_months), 1) / 12.0)

        i_min = funding + opex + risk_month + margin

        # opcionalmente respeita piso de caps (se houver)
        min_cap = self.caps.get("min_rate_monthly")
        if min_cap is not None:
            i_min = max(i_min, float(min_cap))
        return float(i_min)

    def components(
        self,
        pd_12m: float,
        n_months: int,
        *,
        lgd: float | None = None,
        funding: float | None = None,
        opex: float | None = None,
        margin: float | None = None,
    ) -> dict:
        lgd     = float(self._ue("lgd", 0.45) if lgd     is None else lgd)
        funding = float(self._ue("funding_rate_monthly", 0.008) if funding is None else funding)
        opex    = float(self._ue("opex_rate_monthly",     0.003) if opex    is None else opex)
        margin  = float(self._ue("margin_monthly",        0.002) if margin  is None else margin)

        el_over_P = float(pd_12m) * lgd * 0.5
        risk_month = el_over_P / (max(int(n_months), 1) / 12.0)
        i_min = funding + opex + risk_month + margin

        return {
            "pd_12m": float(pd_12m),
            "lgd": lgd,
            "ead_avg_pct": 0.5,
            "el_over_P": el_over_P,                 # como % do principal
            "risk_component_monthly": risk_month,   # componente mensal de risco
            "funding": funding,
            "opex": opex,
            "margin_target": margin,
            "i_min": i_min,
        }

class _Registry:
    _lock = Lock()
    _pd_model = None
    _scorecard = None
    _pricing = None

    def __init__(self):
        self.model_path = os.environ.get(
            "PD_MODEL_PATH",
            "mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib",
        )
        self.scoring_conf = os.environ.get(
            "SCORING_CONF",
            "mlops/conf/scoring.yaml",
        )
        self.pricing_model_path = os.environ.get(
            "PRICING_MODEL_PATH",
            "mlops/training/pricing__LINR1/outputs/models/pricing_linr1.joblib",
        )
        self.pricing_conf_path = os.environ.get(
            "PRICING_CONF_PATH",
            "mlops/conf/pricing.yaml",
        )

    def get_pd_model(self):
        if self._pd_model is None:
            with self._lock:
                if self._pd_model is None:
                    self._pd_model = load(self.model_path)
        return self._pd_model

    def get_scorecard(self):
        if self._scorecard is None:
            with self._lock:
                if self._scorecard is None:
                    with open(self.scoring_conf) as f:
                        conf = yaml.safe_load(f)
                    self._scorecard = Scorecard(conf)
        return self._scorecard

    def get_pricing(self) -> _PricingWrapper:
        if self._pricing is None:
            with self._lock:
                if self._pricing is None:
                    if not os.path.exists(self.pricing_model_path):
                        raise FileNotFoundError(f"PRICING joblib não encontrado em {self.pricing_model_path}")
                    artifact = load(self.pricing_model_path)

                    caps_fallback, ue_defaults = {}, {}
                    if os.path.exists(self.pricing_conf_path):
                        try:
                            with open(self.pricing_conf_path, "r") as f:
                                conf = yaml.safe_load(f) or {}
                            caps_fallback = conf.get("caps") or {}
                            ue_defaults   = conf.get("unit_economics") or {}
                        except Exception:
                            caps_fallback, ue_defaults = {}, {}

                    self._pricing = _PricingWrapper(
                        artifact=artifact,
                        caps_fallback=caps_fallback,
                        ue_defaults=ue_defaults,
                    )
        return self._pricing

registry = _Registry()
