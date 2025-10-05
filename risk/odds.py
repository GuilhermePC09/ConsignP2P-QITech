# Conversão PD ↔ odds ↔ score, + bandas (0–1000)

import math
from typing import Dict, Tuple

class Scorecard:
    def __init__(self, conf: Dict):
        sc = conf["scorecard"]
        self.S0  = float(sc["S0"])
        self.O0  = float(sc["O0"])
        self.PDO = float(sc["PDO"])

        lim = conf.get("limits", {})
        self.pd_floor   = float(lim.get("pd_floor", 0.002))
        self.pd_ceiling = float(lim.get("pd_ceiling", 0.60))
        self.score_min  = int(lim.get("score_min", 0))
        self.score_max  = int(lim.get("score_max", 1000))

        self.bands_conf = conf["bands"]
        self._bands_sorted = sorted(self.bands_conf.items(),
                                    key=lambda kv: kv[1]["min"],
                                    reverse=True)
        self._k = self.PDO / math.log(2.0)

    @staticmethod
    def pd_to_odds(pd: float) -> float:
        return (1.0 - pd) / pd

    @staticmethod
    def odds_to_pd(odds: float) -> float:
        return 1.0 / (1.0 + odds)

    def pd_clip(self, pd: float) -> float:
        return max(self.pd_floor, min(self.pd_ceiling, float(pd)))

    def pd_to_score(self, pd: float) -> int:
        pd_c  = self.pd_clip(pd)
        odds  = self.pd_to_odds(pd_c)
        score = self.S0 + self._k * math.log(odds / self.O0)
        return int(round(max(self.score_min, min(self.score_max, score))))

    def score_to_pd(self, score: int) -> float:
        s    = max(self.score_min, min(self.score_max, int(score)))
        odds = self.O0 * math.exp((s - self.S0) / self._k)
        return self.pd_clip(self.odds_to_pd(odds))

    def band_of(self, score: int) -> str:
        for band, spec in self._bands_sorted:
            if score >= int(spec["min"]):
                return band
        return "E"

    def score_and_band(self, pd: float) -> Tuple[int, str]:
        s = self.pd_to_score(pd)
        return s, self.band_of(s)
