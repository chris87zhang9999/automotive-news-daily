"""Parse daily Markdown reports and render into a single-page static site."""
import json
import logging
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def parse_report_md(path: Path) -> dict:
    """Parse a daily report markdown into {date, brief, articles: [...]}."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    date = path.stem  # filename without extension = YYYY-MM-DD
    brief = ""
    articles = []

    current_article: dict | None = None
    current_score = 1
    in_brief = False

    for line in lines:
        # Section headers determine score context
        if line.startswith("## 🚨"):
            current_score = 3
            in_brief = False
            if current_article:
                articles.append(current_article)
                current_article = None
        elif line.startswith("## ⚠️"):
            current_score = 2
            in_brief = False
            if current_article:
                articles.append(current_article)
                current_article = None
        elif line.startswith("## 📊"):
            current_score = 1
            in_brief = False
            if current_article:
                articles.append(current_article)
                current_article = None
        elif line.startswith("## 今日质量简报"):
            in_brief = True
            if current_article:
                articles.append(current_article)
                current_article = None
        elif line.startswith("## "):
            in_brief = False
            if current_article:
                articles.append(current_article)
                current_article = None
        # Article title lines
        elif line.startswith("### **["):
            if current_article:
                articles.append(current_article)
            # Parse: ### **[Brand]** Title
            m = re.match(r"### \*\*\[(.+?)\]\*\* (.+)", line)
            if m:
                current_article = {
                    "brand": m.group(1),
                    "title": m.group(2),
                    "summary": "",
                    "note": "",
                    "source_name": "",
                    "url": "",
                    "market": "",
                    "score": current_score,
                }
        # Summary and note lines (blockquotes)
        elif line.startswith("> **质量含义：**") and current_article:
            current_article["note"] = line[len("> **质量含义：** "):].strip()
        elif line.startswith("> ") and current_article and not current_article["summary"]:
            current_article["summary"] = line[2:].strip()
        # Source line
        elif line.startswith("- 来源:") and current_article:
            m = re.match(r"- 来源: \[(.+?)\]\((.+?)\)", line)
            if m:
                current_article["source_name"] = m.group(1)
                current_article["url"] = m.group(2)
        # Market line
        elif line.startswith("- 市场:") and current_article:
            current_article["market"] = line[len("- 市场:"):].strip()
        # Brief text (lines after ## 今日质量简报, skip empty)
        elif in_brief and line.strip() and not line.startswith("#"):
            brief = (brief + " " + line.strip()).strip()

    if current_article:
        articles.append(current_article)

    return {"date": date, "brief": brief, "articles": articles}


def build_site(reports_dir: Path, site_dir: Path) -> None:
    """Read all reports/*.md, render site/index.html."""
    site_dir.mkdir(parents=True, exist_ok=True)

    # articles_by_date: date -> list of article dicts (with date field added)
    articles_by_date: dict[str, list[dict]] = {}
    briefs_by_date: dict[str, str] = {}
    dates: list[str] = []

    for md_file in sorted(reports_dir.glob("*.md"), reverse=True):
        result = parse_report_md(md_file)
        date = result["date"]
        articles = result["articles"]
        brief = result["brief"]
        if articles:
            # Attach date to each article for search/filter
            for a in articles:
                a["date"] = date
            articles_by_date[date] = articles
            briefs_by_date[date] = brief
            dates.append(date)

    # Flatten for Fuse.js search
    all_articles = [a for date in dates for a in articles_by_date[date]]

    articles_json = json.dumps(all_articles, ensure_ascii=False)
    dates_json = json.dumps(dates, ensure_ascii=False)
    briefs_json = json.dumps(briefs_by_date, ensure_ascii=False)

    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(
        articles_json=articles_json,
        dates_json=dates_json,
        briefs_json=briefs_json,
        total=len(all_articles),
        date_count=len(dates),
    )

    (site_dir / "index.html").write_text(html, encoding="utf-8")
    logger.info("site built: %d articles across %d days → %s",
                len(all_articles), len(dates), site_dir / "index.html")
