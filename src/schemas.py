import hashlib
from dataclasses import dataclass
from typing import Literal

Priority = Literal["P0", "P1", "P2", "P3"]

def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]

@dataclass
class NewsItem:
    url: str
    title: str
    source_name: str
    region: str
    published_at: str
    raw_text: str
    priority: Priority = "P3"
    brand: str = ""
    summary: str = ""
    score: int = -1       # -1 = not evaluated; 0-3 = quality-director relevance
    note: str = ""        # ≤30-word business implication (score≥2 only)
    market: str = ""      # LLM-determined market (overrides collector region for display)

    @property
    def hash_id(self) -> str:
        return url_hash(self.url)
