"""NHTSA recalls — uses feedparser on the RSS endpoint."""
import logging
import feedparser
from src.collectors.base import BaseCollector
from src.schemas import NewsItem, url_hash

logger = logging.getLogger(__name__)

_NHTSA_FEED = "https://www.nhtsa.gov/rss-feeds/recalls-rss.xml"

class NhtsaCollector(BaseCollector):
    name = "nhtsa"

    def collect(self) -> list[NewsItem]:
        try:
            feed = feedparser.parse(_NHTSA_FEED)
        except Exception as ex:
            logger.warning("nhtsa feed failed: %s", ex)
            return []

        seen: set[str] = set()
        out: list[NewsItem] = []
        for e in feed.entries:
            link = getattr(e, "link", "") or ""
            title = getattr(e, "title", "").strip()
            if not link or not title:
                continue
            h = url_hash(link)
            if h in seen:
                continue
            seen.add(h)
            out.append(NewsItem(
                url=link, title=title, source_name="NHTSA",
                region="北美",
                published_at=getattr(e, "published", ""),
                raw_text=(getattr(e, "summary", "") or "")[:2000],
            ))
        logger.info("nhtsa collected %d recalls", len(out))
        return out
