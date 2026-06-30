"""SAMR (中国市场监管总局) 缺陷产品召回公告采集。"""
import logging
import httpx
from xml.etree import ElementTree as ET
from src.collectors.base import BaseCollector
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SAMR_URL = "https://www.samr.gov.cn/cpgls/index.xml"

class SamrCollector(BaseCollector):
    name = "samr"

    def collect(self) -> list[NewsItem]:
        try:
            resp = httpx.get(_SAMR_URL, timeout=20, follow_redirects=True)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except Exception as ex:
            logger.warning("samr fetch failed: %s", ex)
            return []

        out: list[NewsItem] = []
        for recall in root.findall(".//recall") + root.findall(".//item"):
            title = (recall.findtext("title") or "").strip()
            url = (recall.findtext("url") or recall.findtext("link") or "").strip()
            pub = (recall.findtext("pubDate") or recall.findtext("date") or "").strip()
            desc = (recall.findtext("description") or "").strip()
            if not title or not url:
                continue
            out.append(NewsItem(
                url=url, title=title, source_name="samr.gov.cn",
                region="中国", published_at=pub, raw_text=desc,
            ))
        logger.info("samr collected %d recalls", len(out))
        return out
