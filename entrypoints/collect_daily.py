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
    NORTH_AMERICA_FEEDS, INTERNATIONAL_FEEDS, CHINA_FEEDS, EUROPE_FEEDS,
    RUSSIA_FEEDS, MIDDLE_EAST_FEEDS, SEA_FEEDS, EAST_ASIA_FEEDS,
    QUALITY_RECALL_FEEDS,
)
from src.filter import filter_and_prioritize
from src.dedup import deduplicate
from src.summarizer import summarize_all
from src.brief import generate_brief
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
        RssCollector(feeds=NORTH_AMERICA_FEEDS,   region="北美"),
        RssCollector(feeds=INTERNATIONAL_FEEDS,   region="国际"),
        RssCollector(feeds=CHINA_FEEDS,           region="中国"),
        RssCollector(feeds=EUROPE_FEEDS,          region="西欧"),
        RssCollector(feeds=RUSSIA_FEEDS,          region="俄罗斯/中亚"),
        RssCollector(feeds=MIDDLE_EAST_FEEDS,     region="中东"),
        RssCollector(feeds=SEA_FEEDS,             region="东南亚"),
        RssCollector(feeds=EAST_ASIA_FEEDS,       region="东亚"),
        RssCollector(feeds=QUALITY_RECALL_FEEDS,  region="质量召回"),
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

    summarized = summarize_all(llm, fresh[:TOP_N * 3], max_workers=5)
    log.info("summarized %d items", len(summarized))

    brief = generate_brief(llm, summarized)

    # Drop score=0 noise before applying TOP_N cap
    relevant_scored = [it for it in summarized if it.score > 0]
    top = sorted(
        relevant_scored,
        key=lambda x: (-x.score, {"P0": 0, "P1": 1, "P2": 2, "P3": 3}[x.priority])
    )[:TOP_N]

    report_path = _write_report(top, today, brief, REPORTS_DIR)
    log.info("report saved: %s", report_path)

    site_url = os.environ.get("SITE_URL", "https://github.com")
    send_notify(cfg=cfg, date=today, items=top, brief=brief, site_url=site_url)
    log.info("feishu notify complete")
    return 0


def _write_report(items: list, today: str, brief: str, reports_dir: Path) -> Path:
    score3 = [it for it in items if it.score == 3]
    score2 = [it for it in items if it.score == 2]
    score1 = [it for it in items if it.score == 1]
    total = len(score3) + len(score2) + len(score1)

    lines = [
        f"# 汽车质量情报日报 {today}",
        f"> 今日收录 {total} 条 | 紧急 {len(score3)} · 重要 {len(score2)} · 背景 {len(score1)}",
        "",
        "## 今日质量简报",
        "",
        brief,
        "",
    ]

    def _section(emoji: str, title: str, section_items: list) -> list:
        if not section_items:
            return []
        out = [f"## {emoji} {title}", ""]
        for it in section_items:
            display_market = it.market or it.region
            brand_label = it.brand or "General"
            out.append(f"### **[{brand_label}]** {it.title}")
            out.append(f"> {it.summary}")
            if it.note:
                out.append(f"> **质量含义：** {it.note}")
            out.append(f"- 来源: [{it.source_name}]({it.url})")
            out.append(f"- 市场: {display_market}")
            out.append("")
        return out

    lines += _section("🚨", "紧急关注", score3)
    lines += _section("⚠️", "竞品与监管动态", score2)
    lines += _section("📊", "市场背景", score1)

    path = reports_dir / f"{today}.md"
    reports_dir.mkdir(exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
