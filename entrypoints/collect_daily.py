"""Daily entrypoint: collect → filter → dedup → summarize → report + notify."""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_config
from src.llm_client import LLMClient
from src.collectors.rss import RssCollector
from src.collectors.samr import SamrCollector
from src.collectors.rapex import RapexCollector
from src.collectors.nhtsa import NhtsaCollector
from src.collectors.feeds import (
    GLOBAL_FEEDS, CHINA_FEEDS, EUROPE_FEEDS,
    RUSSIA_FEEDS, MIDDLE_EAST_FEEDS, SEA_FEEDS, EAST_ASIA_FEEDS,
)
from src.filter import filter_and_prioritize
from src.dedup import deduplicate
from src.summarizer import summarize_all
from src.delivery.feishu import send_notify

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("collect_daily")

REPORTS_DIR = Path("reports")
TOP_N = 35

def main() -> int:
    cfg = load_config()
    llm = LLMClient(cfg)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw: list = []
    collectors = [
        RssCollector(feeds=GLOBAL_FEEDS,      region="全球"),
        RssCollector(feeds=CHINA_FEEDS,       region="中国"),
        RssCollector(feeds=EUROPE_FEEDS,      region="欧洲"),
        RssCollector(feeds=RUSSIA_FEEDS,      region="俄罗斯/中亚"),
        RssCollector(feeds=MIDDLE_EAST_FEEDS, region="中东"),
        RssCollector(feeds=SEA_FEEDS,         region="东南亚"),
        RssCollector(feeds=EAST_ASIA_FEEDS,   region="东亚"),
        SamrCollector(),
        RapexCollector(),
        NhtsaCollector(),
    ]
    for c in collectors:
        try:
            raw.extend(c.collect())
        except Exception as ex:
            log.error("collector %s failed: %s", type(c).__name__, ex)
    log.info("total raw items: %d", len(raw))

    relevant = filter_and_prioritize(raw)
    log.info("after filter: %d items", len(relevant))

    fresh = deduplicate(relevant)
    log.info("after dedup: %d fresh items", len(fresh))

    if not fresh:
        log.warning("no fresh items today, skipping report")
        return 0

    top = fresh[:TOP_N]
    summarized = summarize_all(llm, top, max_workers=5)
    log.info("summarized %d items", len(summarized))

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"{today}.md"
    _write_report(summarized, report_path, today)
    log.info("report saved: %s", report_path)

    site_url = os.environ.get("SITE_URL", "https://github.com")
    send_notify(summarized, webhook=cfg.feishu_bot_webhook, date=today, site_url=site_url)
    log.info("feishu notify complete")
    return 0

def _write_report(items, path: Path, date: str) -> None:
    _SECTION_HEADERS = {
        "P0": "🚨 质量预警 & 召回",
        "P1": "⭐ 理想汽车动态",
        "P2": "🇨🇳 中国品牌出海",
        "P3": "🌍 国际品牌动态",
    }
    lines = [f"# 汽车行业日报 {date}\n", f"> {len(items)} 条新闻\n"]
    by_prio: dict[str, list] = {p: [] for p in _SECTION_HEADERS}
    for item in items:
        by_prio.setdefault(item.priority, by_prio["P3"]).append(item)
    for prio, header in _SECTION_HEADERS.items():
        group = by_prio.get(prio, [])
        if not group:
            continue
        lines.append(f"\n## {header}\n")
        for item in group:
            brand = f"**[{item.brand}]** " if item.brand else ""
            lines.append(f"### {brand}{item.title}")
            lines.append(f"> {item.summary}")
            lines.append(f"- 来源: [{item.source_name}]({item.url})")
            lines.append(f"- 地区: {item.region}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    sys.exit(main())
