import hashlib
from dataclasses import dataclass
from typing import List

@dataclass
class MockKwMetric:
    keyword: str
    avg_monthly_searches: int
    cpc_micros: int
    competition_level: str

def _seed_int(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)

def overview(keyword: str) -> MockKwMetric:
    n = _seed_int("ov:" + keyword.lower())
    avg = 50 + (n % 5000)
    cpc = (100_000 + (n % 3_000_000))  # micros
    comp = ["LOW", "MEDIUM", "HIGH"][n % 3]
    return MockKwMetric(keyword=keyword, avg_monthly_searches=avg, cpc_micros=cpc, competition_level=comp)

def ideas(seed: str, limit: int = 50) -> List[MockKwMetric]:
    base = _seed_int("id:" + seed.lower())
    out: List[MockKwMetric] = []
    for i in range(limit):
        kw = f"{seed} idea {i+1}"
        n = _seed_int(f"{base}:{i}:{kw}")
        avg = 10 + (n % 8000)
        cpc = (50_000 + (n % 2_500_000))
        comp = ["LOW", "MEDIUM", "HIGH"][n % 3]
        out.append(MockKwMetric(keyword=kw, avg_monthly_searches=avg, cpc_micros=cpc, competition_level=comp))
    return out
