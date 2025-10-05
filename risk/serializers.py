from dataclasses import dataclass
from typing import Dict, Optional

FEATURE_ORDER = [
    'beneficio_ativo','tempo_beneficio_meses',
    'emprego_ativo','tempo_emprego_meses',
    'renda_media_6m','coef_var_renda','pct_meses_saldo_neg_6m',
    'utilizacao_cartao','pct_minimo_pago_3m','num_faturas_vencidas_3m',
    'endividamento_total','parcelas_renda','DPD_max_12m',
    'idade','tempo_rel_banco_meses'
]

@dataclass
class ScoreRequest:
    features: Dict[str, float]
    amount: Optional[float] = None
    term_months: Optional[int] = None
    fees: Optional[Dict[str, float]] = None

    @classmethod
    def from_json(cls, data: Dict):
        if "features" not in data or not isinstance(data["features"], dict):
            raise ValueError("payload deve conter 'features' como objeto JSON")
        return cls(
            features=data["features"],
            amount=data.get("amount"),
            term_months=data.get("term_months"),
            fees=data.get("fees")
        )

    def to_feature_vector(self):
        f = self.features
        missing = [k for k in FEATURE_ORDER if k not in f]
        if missing:
            raise ValueError(f"features ausentes: {missing}")
        return [float(f[k]) for k in FEATURE_ORDER]
