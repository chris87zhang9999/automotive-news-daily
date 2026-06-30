import json
from pathlib import Path
from src.site_builder import parse_report_md, build_site

_SAMPLE_MD = """# 汽车行业日报 2026-06-29

> 3 条新闻

## 🚨 质量预警 & 召回

### **[Li Auto]** 理想汽车召回 L9
> Li Auto has initiated a recall of 1200 units.
- 来源: [samr.gov.cn](https://samr.gov.cn/1)
- 地区: 中亚

## 🌍 国际品牌动态

### Toyota new hybrid lineup
> Toyota announced new hybrid models.
- 来源: [reuters.com](https://reuters.com/2)
- 地区: 全球
"""

def test_parse_report_md_extracts_articles(tmp_path):
    md_file = tmp_path / "2026-06-29.md"
    md_file.write_text(_SAMPLE_MD, encoding="utf-8")
    articles = parse_report_md(md_file)
    assert len(articles) == 2
    assert articles[0]["priority"] == "P0"
    assert articles[0]["brand"] == "Li Auto"
    assert articles[0]["region"] == "中亚"
    assert "1200 units" in articles[0]["summary"]

def test_parse_report_md_sets_correct_priority():
    from pathlib import Path
    import tempfile
    md = "# 汽车行业日报 2026-06-28\n\n## ⭐ 理想汽车动态\n\n### 理想 Q2 增长\n> Li Auto grew.\n- 来源: [x](https://x.com)\n- 地区: 欧洲\n"
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write(md)
        path = Path(f.name)
    articles = parse_report_md(path)
    assert articles[0]["priority"] == "P1"

def test_build_site_generates_html(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "2026-06-29.md").write_text(_SAMPLE_MD, encoding="utf-8")
    site_dir = tmp_path / "site"
    build_site(reports_dir=reports_dir, site_dir=site_dir)
    index = site_dir / "index.html"
    assert index.exists()
    content = index.read_text(encoding="utf-8")
    assert "2026-06-29" in content
    assert "Fuse" in content or "fuse" in content
    assert "理想汽车召回" in content
