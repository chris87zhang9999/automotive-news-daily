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

    @property
    def hash_id(self) -> str:
        return url_hash(self.url)
