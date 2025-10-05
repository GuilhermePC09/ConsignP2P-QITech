# qitech_mock/rng.py
import hashlib, random, uuid, math
from datetime import datetime, timedelta

def _seed_from(*parts: str) -> int:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    # 256-bit → int
    return int.from_bytes(h.digest(), "big")

class DRand:
    """
    Deterministic RNG. Seed composed from:
      - user_uuid (from header X-User-UUID, body field, or fallback)
      - endpoint namespace (e.g., "laas.debt_simulation")
      - optional extra (e.g., "borrower_cpf", account_key, debt_key)
    """
    def __init__(self, *seed_parts: str):
        self._rand = random.Random(_seed_from(*seed_parts))

    def choice(self, seq):
        return self._rand.choice(seq)

    def uniform(self, a: float, b: float) -> float:
        return self._rand.uniform(a, b)

    def randint(self, a: int, b: int) -> int:
        return self._rand.randint(a, b)

    def sample(self, population, k: int):
        return self._rand.sample(population, k)

    def uuid4_like(self) -> str:
        # Create a UUID deterministically from next 128 bits
        hi = self._rand.getrandbits(128)
        return str(uuid.UUID(int=hi))

    def money(self, low: float, high: float, ndigits: int = 2) -> float:
        return round(self.uniform(low, high), ndigits)

    def date_from_today(self, min_days: int, max_days: int) -> str:
        d = datetime.utcnow() + timedelta(days=self.randint(min_days, max_days))
        return d.date().isoformat()

    def datetime_iso(self, min_days=-5, max_days=0) -> str:
        d = datetime.utcnow() + timedelta(days=self.randint(min_days, max_days),
                                          seconds=self.randint(0, 24*3600))
        return d.replace(microsecond=0).isoformat() + "Z"

def derive_user_uuid(header_val: str|None, *fallbacks: str) -> str:
    """
    Prefer X-User-UUID header (a UUID string).
    Otherwise hash together known identifiers (e.g., document_number, requester_identifier_key)
    to produce a *stable* pseudo-uuid string.
    """
    if header_val:
        try:
            return str(uuid.UUID(header_val))
        except Exception:
            pass
    seed = _seed_from(*[f or "" for f in fallbacks])
    return str(uuid.UUID(int=seed % (1<<128)))
