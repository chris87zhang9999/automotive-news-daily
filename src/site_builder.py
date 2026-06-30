"""Parse daily Markdown reports and render into a single-page static site."""
import json
import logging
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_SECTION_PRIORITY = {
    "🚨 质量预警 & 召回": "P0",
    "⭐ 理想汽车动态": "P1",
    "🇨🇳 中国品牌出海": "P2",
    "🌍 国际品牌动态": "P3",
}

def parse_report_md(path: Path) -> list[dict]:
    """Parse a daily report Markdown into a list of article dicts."""
    text = path.read_text(encoding="utf-8")
    date = path.stem

    articles: list[dict] = []
    current_priority = "P3"

    for line in text.splitlines():
        for section, prio in _SECTION_PRIORITY.items():
            if line.startswith("## ") and section in line:
                current_priority = prio
                break
        m = re.match(r"^### (?:\*\*\[(.+?)\]\*\* )?(.+)$", line)
        if m:
            brand = m.group(1) or ""
            title = m.group(2).strip()
            articles.append({
                "date": date,
                "priority": current_priority,
                "brand": brand,
                "title": title,
                "summary": "",
                "source_name": "",
                "source_url": "",
                "region": "",
            })
            continue
        if line.startswith("> ") and articles:
            articles[-1]["summary"] = line[2:].strip()
            continue
        m2 = re.match(r"^- 来源: \[(.+?)\]\((.+?)\)$", line)
        if m2 and articles:
            articles[-1]["source_name"] = m2.group(1)
            articles[-1]["source_url"] = m2.group(2)
            continue
        m3 = re.match(r"^- 地区: (.+)$", line)
        if m3 and articles:
            articles[-1]["region"] = m3.group(1).strip()

    return articles

def build_site(reports_dir: Path, site_dir: Path) -> None:
    """Read all reports/*.md, render site/index.html."""
    site_dir.mkdir(parents=True, exist_ok=True)

    all_articles: list[dict] = []
    dates: list[str] = []

    for md_file in sorted(reports_dir.glob("*.md"), reverse=True):
        articles = parse_report_md(md_file)
        if articles:
            all_articles.extend(articles)
            dates.append(md_file.stem)

    articles_json = json.dumps(all_articles, ensure_ascii=False)
    dates_json = json.dumps(dates, ensure_ascii=False)

    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(articles_json=articles_json, dates_json=dates_json,
                       total=len(all_articles), date_count=len(dates))

    (site_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("site built: %d articles across %d days → %s",
                len(all_articles), len(dates), site_dir / "index.html")
