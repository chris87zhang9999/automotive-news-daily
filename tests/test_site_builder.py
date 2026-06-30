import json
import tempfile
from pathlib import Path
from src.site_builder import parse_report_md, build_site

_SAMPLE_MD = """# 汽车质量情报日报 2026-06-30
> 今日收录 3 条 | 紧急 1 · 重要 1 · 背景 1

## 今日质量简报

Today's brief text here.

## 🚨 紧急关注

### **[Li Auto]** Some urgent article title
> This is the summary.
> **质量含义：** This is the business note.
- 来源: [source.com](https://source.com/article)
- 市场: 中东

## ⚠️ 竞品与监管动态

### **[NIO]** Important article
> Summary here.
> **质量含义：** Note here.
- 来源: [nio-news.com](https://nio-news.com)
- 市场: 东南亚

## 📊 市场背景

### **[BYD]** Background article
> Background summary.
- 来源: [byd-news.com](https://byd-news.com)
- 市场: 西欧
"""


def test_parse_report_md_extracts_articles(tmp_path):
    md_file = tmp_path / "2026-06-30.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    result = parse_report_md(md_file)
    articles = result["articles"]
    assert len(articles) == 3
    assert articles[0]["score"] == 3
    assert articles[0]["brand"] == "Li Auto"
    assert articles[0]["market"] == "中东"
    assert "This is the summary" in articles[0]["summary"]


def test_parse_report_md_note_field(tmp_path):
    md_file = tmp_path / "2026-06-30.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    result = parse_report_md(md_file)
    articles = result["articles"]
    assert articles[0]["note"] == "This is the business note."
    assert articles[1]["note"] == "Note here."
    # Background article has no note
    assert articles[2]["note"] == ""


def test_parse_report_md_brief(tmp_path):
    md_file = tmp_path / "2026-06-30.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    result = parse_report_md(md_file)
    assert result["brief"] == "Today's brief text here."


def test_parse_report_md_scores(tmp_path):
    md_file = tmp_path / "2026-06-30.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    result = parse_report_md(md_file)
    articles = result["articles"]
    assert articles[0]["score"] == 3  # 🚨
    assert articles[1]["score"] == 2  # ⚠️
    assert articles[2]["score"] == 1  # 📊


def test_parse_report_md_market_field(tmp_path):
    md_file = tmp_path / "2026-06-30.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    result = parse_report_md(md_file)
    articles = result["articles"]
    assert articles[0]["market"] == "中东"
    assert articles[1]["market"] == "东南亚"
    assert articles[2]["market"] == "西欧"


def test_build_site_generates_html(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "2026-06-30.md").write_text(_SAMPLE_MD, encoding="utf-8")
    site_dir = tmp_path / "site"
    build_site(reports_dir=reports_dir, site_dir=site_dir)
    index = site_dir / "index.html"
    assert index.exists()
    content = index.read_text(encoding="utf-8")
    assert "2026-06-30" in content
    assert "Fuse" in content or "fuse" in content
    assert "Some urgent article title" in content


def test_build_site_embeds_brief(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "2026-06-30.md").write_text(_SAMPLE_MD, encoding="utf-8")
    site_dir = tmp_path / "site"
    build_site(reports_dir=reports_dir, site_dir=site_dir)
    content = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "Today's brief text here." in content


def test_build_site_articles_have_url_not_source_url(tmp_path):
    """Articles use 'url' field (not old 'source_url') after format update."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "2026-06-30.md").write_text(_SAMPLE_MD, encoding="utf-8")
    site_dir = tmp_path / "site"
    build_site(reports_dir=reports_dir, site_dir=site_dir)
    content = (site_dir / "index.html").read_text(encoding="utf-8")
    # The JSON in the page should have "url" key
    assert '"url"' in content
    assert "source.com/article" in content


def test_parse_report_md_multiline_brief():
    content = """# 汽车质量情报日报 2026-06-30
> 今日收录 1 条 | 紧急 0 · 重要 1 · 背景 0

## 今日质量简报

First sentence of the brief.
Second sentence continues here.

## ⚠️ 竞品与监管动态

### **[NIO]** NIO recall in Thailand
> Summary text.
> **质量含义：** Monitor supplier.
- 来源: [source.com](https://source.com)
- 市场: 东南亚
"""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        result = parse_report_md(Path(f.name))
    assert "First sentence" in result["brief"]
    assert "Second sentence" in result["brief"]
