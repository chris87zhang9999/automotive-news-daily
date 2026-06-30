import logging
import feedparser
from src.collectors.base import BaseCollector
from src.schemas import NewsItem, url_hash

logger = logging.getLogger(__name__)

class RssCollector(BaseCollector):
    name = "rss"

    def __init__(self, feeds: list[str], region: str, source_name: str = ""):
        self._feeds = feeds
        self._region = region
        self._source_name = source_name

    def collect(self) -> list[NewsItem]:
        seen: set[str] = set()
        out: list[NewsItem] = []
        for url in self._feeds:
            try:
                feed = feedparser.parse(url)
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
                        url=link,
                        title=title,
                        source_name=self._source_name or url.split("/")[2],
                        region=self._region,
                        published_at=getattr(e, "published", ""),
                        raw_text=(getattr(e, "summary", "") or "")[:2000],
                    ))
            except Exception as ex:
                logger.warning("rss feed %s failed: %s", url, ex)
        logger.info("rss region=%s collected %d items", self._region, len(out))
        return out
