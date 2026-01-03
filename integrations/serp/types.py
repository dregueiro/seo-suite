from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

Device = Literal["desktop", "mobile"]

@dataclass(frozen=True)
class SerpRequest:
    query: str
    country_code: str
    language_code: str
    device: Device = "desktop"
    num_results: int = 10
    location_name: str = ""  # opcional, por ejemplo "New York,New York,United States"

    def normalized_query(self) -> str:
        return (self.query or "").strip()

@dataclass
class SerpResultItem:
    position: int
    title: str
    url: str
    domain: str
    snippet: str = ""
    displayed_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SerpFeatureItem:
    name: str
    position: int = 0
    url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SerpParsed:
    provider: str
    results: List[SerpResultItem]
    features: List[SerpFeatureItem]
    raw: Dict[str, Any] = field(default_factory=dict)
