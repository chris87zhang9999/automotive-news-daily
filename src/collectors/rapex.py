"""EU Safety Gate (RAPEX) 周报 XML 下载。每周更新，每日 collector 也调——幂等。"""
import logging
import httpx
from xml.etree import ElementTree as ET
from src.collectors.base import BaseCollector
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_RAPEX_URL = (
    "https://ec.europa.eu/consumers/consumers_safety/safety_products/"
    "rapex/alerts/repository/content/pages/rapex/reports/docs/rapex_weekly.xml"
)

class RapexCollector(BaseCollector):
    name = "rapex"

    def collect(self) -> list[NewsItem]:
        try:
            resp = httpx.get(_RAPEX_URL, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as ex:
            logger.warning("rapex fetch failed: %s", ex)
            return []

        out: list[NewsItem] = []
        for alert in root.findall(".//ALERT"):
            category = alert.get("category", "")
            if "vehicle" not in category.lower() and "motor" not in category.lower():
                continue
            title = (alert.findtext("PRODUCT_NAME") or
                     alert.findtext("SUBJECT") or "").strip()
            url = (alert.findtext("URL") or alert.findtext("LINK") or "").strip()
            desc = (alert.findtext("DESCRIPTION") or "").strip()
            brand = (alert.findtext("BRAND") or "").strip()
            pub = (alert.findtext("DATE") or "").strip()
            if not title:
                continue
            out.append(NewsItem(
                url=url or _RAPEX_URL,
                title=f"[EU RAPEX] {brand} — {title}" if brand else f"[EU RAPEX] {title}",
                source_name="EU Safety Gate",
                region="欧盟",
                published_at=pub,
                raw_text=desc,
            ))
        logger.info("rapex collected %d vehicle alerts", len(out))
        return out
