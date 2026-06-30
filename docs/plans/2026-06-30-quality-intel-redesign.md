# Quality Intelligence Redesign

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the daily news collector from a neutral aggregator into an active intelligence briefing system, evaluated through the lens of a Li Auto overseas quality director.

**Architecture:** Replace the neutral LLM summarizer prompt with a quality-director persona that scores each article (0–3), extracts a market tag, and writes a business implication note. Add a second LLM call that synthesizes a daily brief from high-score articles. Expand and re-label RSS sources for better market precision.

**Tech Stack:** Python 3.12, feedparser, GLM-4-flash (JSON mode), Jinja2, GitHub Actions

---

### Task 1: Expand and re-label RSS feed sources

**Files:**
- Modify: `src/collectors/feeds.py`

**Context:** Current `GLOBAL_FEEDS` is 60% US EV media but labelled "全球". Middle East is empty. Russia/CIS thin. No quality-recall-specific feeds beyond the broken SAMR.

**Step 1: Replace `GLOBAL_FEEDS` with two groups**

```python
# North America — US/Canada automotive media
NORTH_AMERICA_FEEDS = [
    "https://insideevs.com/feed/",
    "https://electrek.co/feed/",
    "https://www.caranddriver.com/rss/all.xml/",
    "https://www.theverge.com/rss/transportation/index.xml",
    "https://www.wardsauto.com/rss.xml",
]

# International — genuinely multi-region outlets
INTERNATIONAL_FEEDS = [
    "https://www.motor1.com/rss/news/all/",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://carnewschina.com/feed/",
    "https://auto.gasgoo.com/RSS/automotive_news.xml",
]
```

**Step 2: Add Middle East feeds**

```python
MIDDLE_EAST_FEEDS = [
    "https://gulfnews.com/rss/automobiles",
    "https://www.driving.co.uk/car-news/feed/",   # Arab Motor World via proxy
    "https://www.arabianbusiness.com/rss",
]
```

**Step 3: Add quality/recall-specific feeds**

```python
QUALITY_RECALL_FEEDS = [
    # UK: DVSA vehicle recalls
    "https://www.gov.uk/government/organisations/driver-and-vehicle-standards-agency.atom",
    # Australia: ACCC product safety
    "https://www.productsafety.gov.au/recalls/search.atom?words=vehicle",
    # carnewschina recall tag (proxy for SAMR since SAMR blocks GH Actions IPs)
    "https://carnewschina.com/category/recall/feed/",
]
```

**Step 4: Add Southeast Asia and Russia feeds**

```python
# Add to SEA_FEEDS
"https://autodeal.com.ph/articles/feed",

# Add to RUSSIA_FEEDS  
"https://www.za-rulem.ru/rss.xml",
```

**Step 5: Update `ALL_REGIONAL_FEEDS` dict**

```python
ALL_REGIONAL_FEEDS: dict[str, list[str]] = {
    "北美":       NORTH_AMERICA_FEEDS,
    "国际":       INTERNATIONAL_FEEDS,
    "中国":       CHINA_FEEDS,
    "西欧":       EUROPE_FEEDS,
    "俄罗斯/中亚": RUSSIA_FEEDS,
    "中东":       MIDDLE_EAST_FEEDS,
    "东南亚":     SEA_FEEDS,
    "东亚":       EAST_ASIA_FEEDS,
    "质量召回":   QUALITY_RECALL_FEEDS,
}
```

**Step 6: Update `collect_daily.py` imports and collectors list**

Replace `GLOBAL_FEEDS` with `NORTH_AMERICA_FEEDS, INTERNATIONAL_FEEDS` in the import and add `QUALITY_RECALL_FEEDS`. Add two new `RssCollector` entries:
```python
RssCollector(feeds=NORTH_AMERICA_FEEDS,   region="北美"),
RssCollector(feeds=INTERNATIONAL_FEEDS,   region="国际"),
RssCollector(feeds=QUALITY_RECALL_FEEDS,  region="质量召回"),
```
Remove the old `RssCollector(feeds=GLOBAL_FEEDS, region="全球")`.

**Step 7: Run collector smoke test**

```bash
ept uv run python -c "
from src.collectors.feeds import ALL_REGIONAL_FEEDS
for region, feeds in ALL_REGIONAL_FEEDS.items():
    print(f'{region}: {len(feeds)} feeds')
"
```
Expected: each region prints a non-zero count.

**Step 8: Commit**

```bash
git add src/collectors/feeds.py entrypoints/collect_daily.py
git commit -m "feat: expand RSS sources; split global into 北美/国际; add quality-recall feeds"
```

---

### Task 2: Add `score`, `note`, `market` fields to `NewsItem`

**Files:**
- Modify: `src/schemas.py`
- Modify: `tests/test_schemas.py`

**Step 1: Write failing test**

```python
def test_news_item_has_score_and_note():
    item = NewsItem(url="https://x.com", title="t", source_name="s",
                    region="r", published_at="", raw_text="")
    assert item.score == -1        # -1 = not yet evaluated
    assert item.note == ""
    assert item.market == ""
```

**Step 2: Run to confirm failure**

```bash
ept uv run pytest tests/test_schemas.py::test_news_item_has_score_and_note -v
```
Expected: `AttributeError` — fields don't exist yet.

**Step 3: Add fields to `NewsItem`**

```python
@dataclass
class NewsItem:
    url: str
    title: str
    source_name: str
    region: str
    published_at: str
    raw_text: str
    priority: Priority = "P3"
    brand: str = ""
    summary: str = ""
    score: int = -1       # -1 = not evaluated; 0-3 = quality-director relevance
    note: str = ""        # ≤30-word business implication (score≥2 only)
    market: str = ""      # LLM-determined market (overrides collector region for display)
```

**Step 4: Run test to confirm pass**

```bash
ept uv run pytest tests/test_schemas.py -v
```
Expected: all pass.

**Step 5: Commit**

```bash
git add src/schemas.py tests/test_schemas.py
git commit -m "feat: add score/note/market fields to NewsItem"
```

---

### Task 3: Redesign LLM summarizer to quality-director persona with JSON output

**Files:**
- Modify: `src/summarizer.py`
- Modify: `tests/test_summarizer.py`

**Context:** Currently `summarize_item` calls LLM with a neutral analyst prompt and stores plain text in `item.summary`. We need to change the system prompt to quality-director persona and parse a JSON response that populates `summary`, `score`, `note`, and `market`.

**Step 1: Write failing tests**

```python
import json
from unittest.mock import MagicMock, patch
from src.schemas import NewsItem
from src.summarizer import summarize_item, _parse_llm_json

def _item(title="Test article about NIO recall in Thailand"):
    return NewsItem(url="https://x.com", title=title, source_name="s",
                    region="东南亚", published_at="", raw_text="NIO recalls 500 units in Thailand due to brake defect.")

def test_parse_llm_json_valid():
    raw = '{"summary": "NIO recalled units.", "score": 2, "note": "Monitor brake supplier", "market": "东南亚"}'
    result = _parse_llm_json(raw)
    assert result["score"] == 2
    assert result["market"] == "东南亚"

def test_parse_llm_json_fallback_on_invalid():
    result = _parse_llm_json("not json at all")
    assert result["score"] == 1   # fallback to background
    assert result["summary"] != ""

def test_summarize_item_populates_all_fields():
    llm = MagicMock()
    llm.chat.return_value = '{"summary": "NIO recalled 500 units.", "score": 2, "note": "Monitor brake supplier overlap.", "market": "东南亚"}'
    item = summarize_item(llm, _item())
    assert item.score == 2
    assert item.note == "Monitor brake supplier overlap."
    assert item.market == "东南亚"
    assert "NIO" in item.summary
```

**Step 2: Run to confirm failure**

```bash
ept uv run pytest tests/test_summarizer.py::test_parse_llm_json_valid -v
```
Expected: `ImportError` — `_parse_llm_json` doesn't exist.

**Step 3: Implement new `summarizer.py`**

```python
"""Concurrent GLM-4-flash quality-intel evaluator: score + summary + note + market per NewsItem."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SYSTEM = """You are an intelligence analyst for Li Auto's overseas quality operations team.
Li Auto exports to: Middle East, Central Asia, Russia, Southeast Asia, South Korea, and Europe.

Analyze the automotive news article and return ONLY valid JSON with these exact keys:
- "summary": factual summary in ≤80 English words covering what happened, which brand/model, which market, and impact
- "score": integer 0-3 using this rubric:
    3 = Urgent: Li Auto product recall/safety investigation/regulatory mandate in export market
    2 = Important: competitor Chinese brand quality incident in export market; regulatory change affecting Li Auto markets; supplier safety issue
    1 = Background: market trends, competitive dynamics, indirect reference value
    0 = Noise: pure sales/financial news, new model launches with no quality angle, unrelated to Li Auto export markets
- "note": ≤30-word business implication in Chinese for Li Auto quality ops (required when score≥2, empty string otherwise)
- "market": the specific primary market this article concerns — use one of: 北美/西欧/中欧东欧/中东/俄罗斯/中亚/东南亚/韩国/日本/澳大利亚/中国/全球 (only use 全球 when genuinely multi-region)

Return only the JSON object, no markdown, no explanation."""

_FALLBACK_MARKET_MAP = {
    "北美": "北美", "欧洲": "西欧", "西欧": "西欧",
    "中东": "中东", "俄罗斯/中亚": "俄罗斯", "东南亚": "东南亚",
    "东亚": "韩国", "中国": "中国", "质量召回": "全球",
    "国际": "全球",
}

def _parse_llm_json(raw: str, fallback_region: str = "") -> dict:
    """Parse LLM JSON response; return safe fallback dict on any parse error."""
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        # Validate required keys and types
        score = int(data.get("score", 1))
        if score not in (0, 1, 2, 3):
            score = 1
        return {
            "summary": str(data.get("summary", "")),
            "score": score,
            "note": str(data.get("note", "")),
            "market": str(data.get("market", _FALLBACK_MARKET_MAP.get(fallback_region, "全球"))),
        }
    except Exception:
        return {
            "summary": "",
            "score": 1,
            "note": "",
            "market": _FALLBACK_MARKET_MAP.get(fallback_region, "全球"),
        }


def summarize_item(llm: LLMClient, item: NewsItem) -> NewsItem:
    try:
        raw = llm.chat(
            system=_SYSTEM,
            user=f"Title: {item.title}\n\nContent: {item.raw_text[:1500]}",
            max_tokens=350,
            temperature=0.1,
        )
        parsed = _parse_llm_json(raw, fallback_region=item.region)
        item.summary = parsed["summary"] or item.title
        item.score = parsed["score"]
        item.note = parsed["note"]
        item.market = parsed["market"] or item.region
    except Exception as ex:
        logger.warning("summarize failed for %s: %s", item.url, ex)
        item.summary = item.title
        item.score = 1
        item.market = item.region
    return item


def summarize_all(llm: LLMClient, items: list[NewsItem], max_workers: int = 5) -> list[NewsItem]:
    index = {item.hash_id: i for i, item in enumerate(items)}
    results: list[NewsItem] = [None] * len(items)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(summarize_item, llm, item): item for item in items}
        for future in as_completed(futures):
            item = future.result()
            results[index[item.hash_id]] = item

    return results
```

**Step 4: Run all summarizer tests**

```bash
ept uv run pytest tests/test_summarizer.py -v
```
Expected: all pass including 3 new tests.

**Step 5: Commit**

```bash
git add src/summarizer.py tests/test_summarizer.py
git commit -m "feat: redesign summarizer to quality-director persona with JSON score/note/market"
```

---

### Task 4: Add daily brief generator

**Files:**
- Create: `src/brief.py`
- Create: `tests/test_brief.py`

**Context:** After all articles are scored, generate one short daily brief (≤200 Chinese words) from the quality director's perspective, synthesizing score≥2 articles.

**Step 1: Write failing test**

```python
from unittest.mock import MagicMock
from src.schemas import NewsItem
from src.brief import generate_brief

def _scored_item(title, score, note="", market="东南亚"):
    item = NewsItem(url=f"https://x.com/{title}", title=title, source_name="s",
                    region="r", published_at="", raw_text="")
    item.score = score
    item.note = note
    item.market = market
    item.summary = f"Summary of {title}"
    return item

def test_generate_brief_calls_llm_with_high_score_articles():
    llm = MagicMock()
    llm.chat.return_value = "今日重点：东南亚出现两起电池安全事件。"
    items = [
        _scored_item("NIO recall Thailand", score=2, note="Monitor supplier"),
        _scored_item("BYD sales record", score=0),
        _scored_item("Li Auto safety probe", score=3, note="Urgent"),
    ]
    brief = generate_brief(llm, items)
    assert "今日" in brief
    # Only score≥2 articles should be fed to LLM
    call_args = llm.chat.call_args
    assert "NIO recall Thailand" in call_args.kwargs["user"]
    assert "Li Auto safety probe" in call_args.kwargs["user"]
    assert "BYD sales record" not in call_args.kwargs["user"]

def test_generate_brief_returns_placeholder_when_no_high_score():
    llm = MagicMock()
    items = [_scored_item("BYD sales", score=0), _scored_item("Toyota launch", score=1)]
    brief = generate_brief(llm, items)
    assert brief != ""   # placeholder text, no LLM call
    llm.chat.assert_not_called()
```

**Step 2: Run to confirm failure**

```bash
ept uv run pytest tests/test_brief.py -v
```
Expected: `ModuleNotFoundError`.

**Step 3: Implement `src/brief.py`**

```python
"""Generate a quality-director daily brief from high-score articles."""
import logging
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_BRIEF_SYSTEM = """你是理想汽车海外质量业务的情报主管。
根据今日筛选出的重要情报，用≤200字中文写一段质量总监视角的每日简报。
要求：指出关键风险点、竞品动态启示、需要跟进的行动建议。
语气专业简练，不要重复罗列新闻标题，要做业务判断和推论。"""

_NO_INTEL_PLACEHOLDER = "今日无 score≥2 的重要质量情报，市场整体平稳。"

def generate_brief(llm: LLMClient, items: list[NewsItem]) -> str:
    high_value = [it for it in items if it.score >= 2]
    if not high_value:
        return _NO_INTEL_PLACEHOLDER

    bullets = "\n".join(
        f"- [{it.market}] {it.title} (score={it.score}): {it.summary} | 含义: {it.note}"
        for it in high_value
    )
    try:
        return llm.chat(
            system=_BRIEF_SYSTEM,
            user=f"今日重要情报列表：\n{bullets}",
            max_tokens=400,
            temperature=0.3,
        )
    except Exception as ex:
        logger.warning("brief generation failed: %s", ex)
        return _NO_INTEL_PLACEHOLDER
```

**Step 4: Run tests**

```bash
ept uv run pytest tests/test_brief.py -v
```
Expected: all pass.

**Step 5: Commit**

```bash
git add src/brief.py tests/test_brief.py
git commit -m "feat: add daily brief generator from high-score articles"
```

---

### Task 5: Rewrite report format and update `collect_daily.py`

**Files:**
- Modify: `entrypoints/collect_daily.py`

**Context:** The report must be restructured as: brief → 🚨 score=3 → ⚠️ score=2 → 📊 score=1. score=0 articles are dropped. The `market` field replaces `region` in display. TOP_N now applies after scoring (drop score=0 first).

**Step 1: Import `generate_brief` and update pipeline**

In `collect_daily.py`, add:
```python
from src.brief import generate_brief
```

After `summarize_all`, add brief generation:
```python
brief = generate_brief(llm, summarized)
```

**Step 2: Replace `_write_report` with score-based sections**

```python
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
        brief,
        "",
    ]

    def _section(emoji, title, section_items):
        if not section_items:
            return []
        out = [f"## {emoji} {title}", ""]
        for it in section_items:
            display_market = it.market or it.region
            out.append(f"### **[{it.brand or 'General'}]** {it.title}")
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
```

**Step 3: Update TOP_N filtering to drop score=0 first**

After `summarize_all`, filter before applying TOP_N:
```python
# Drop noise articles before applying TOP_N cap
relevant_scored = [it for it in summarized if it.score > 0]
top = sorted(relevant_scored, key=lambda x: (-x.score, {"P0":0,"P1":1,"P2":2,"P3":3}[x.priority]))[:TOP_N]
```

**Step 4: Update the `send_notify` call to pass brief and score counts**

```python
send_notify(
    cfg=cfg,
    date=today,
    items=top,
    brief=brief,
    site_url=site_url,
)
```

**Step 5: Run smoke test locally (no LLM)**

```bash
ept uv run python -c "
from entrypoints.collect_daily import _write_report
from src.schemas import NewsItem
from pathlib import Path
items = []
for i, (score, brand) in enumerate([(3,'Li Auto'),(2,'NIO'),(1,'BYD'),(0,'Tesla')]):
    it = NewsItem(url=f'https://x.com/{i}', title=f'Test article {i}', source_name='test', region='东南亚', published_at='', raw_text='')
    it.score = score; it.brand = brand; it.summary = 'Test summary.'; it.market = '东南亚'
    it.note = 'Test note.' if score >= 2 else ''
    items.append(it)
path = _write_report(items, '2026-06-30', 'Test brief.', Path('/tmp/reports'))
print(open(path).read())
"
```
Expected: report with all 3 sections, score=0 (Tesla) absent.

**Step 6: Commit**

```bash
git add entrypoints/collect_daily.py
git commit -m "feat: restructure report by business score; drop score=0 articles"
```

---

### Task 6: Update Feishu notification card

**Files:**
- Modify: `src/delivery/feishu.py`
- Modify: `tests/test_feishu.py`

**Context:** The card must show score counts and the first 100 characters of the brief instead of priority counts.

**Step 1: Write failing test**

```python
def test_build_notify_card_shows_score_counts():
    from src.schemas import NewsItem
    items = []
    for score in [3, 2, 2, 1, 1, 1]:
        it = NewsItem(url="https://x.com", title="t", source_name="s", region="r", published_at="", raw_text="")
        it.score = score
        items.append(it)
    card = build_notify_card(date="2026-06-30", items=items,
                             brief="今日重点：东南亚出现电池事件。", site_url="https://example.com")
    import json; body = json.dumps(card)
    assert "🚨" in body
    assert "1" in body   # 1 urgent
    assert "2" in body   # 2 important
```

**Step 2: Update `build_notify_card` in `feishu.py`**

```python
def build_notify_card(*, date: str, items: list, brief: str = "", site_url: str) -> dict:
    score3 = sum(1 for it in items if it.score == 3)
    score2 = sum(1 for it in items if it.score == 2)
    score1 = sum(1 for it in items if it.score == 1)
    brief_preview = (brief[:100] + "…") if len(brief) > 100 else brief

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"汽车质量情报 {date}"},
                "template": "red" if score3 > 0 else "orange" if score2 > 0 else "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md",
                             "content": f"🚨 紧急 **{score3}** 条  ⚠️ 重要 **{score2}** 条  📊 背景 **{score1}** 条"},
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": brief_preview},
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📖 查看完整情报"},
                        "type": "primary",
                        "url": f"{site_url}?date={date}",
                    }],
                },
            ],
        },
    }
```

Also update `send_notify` signature to accept `brief`:
```python
def send_notify(*, cfg, date: str, items: list, brief: str = "", site_url: str) -> None:
    card = build_notify_card(date=date, items=items, brief=brief, site_url=site_url)
    ...
```

**Step 3: Run tests**

```bash
ept uv run pytest tests/test_feishu.py -v
```
Expected: all pass.

**Step 4: Commit**

```bash
git add src/delivery/feishu.py tests/test_feishu.py
git commit -m "feat: update Feishu card with score counts and brief preview"
```

---

### Task 7: Update site builder and Jinja2 template

**Files:**
- Modify: `src/site_builder.py`
- Modify: `src/templates/index.html.j2`

**Context:** The static site template currently groups by brand section (中国品牌出海 / 国际品牌动态). It must be updated to render the new score-based sections and show `market` instead of `region`.

**Step 1: Update `parse_report_md` to parse new fields**

The markdown parser in `site_builder.py` reads `- 市场:` (was `- 地区:`). Update the regex:

```python
# old: r"- 地区:\s*(.+)"
# new: r"- 市场:\s*(.+)"
```

Also parse the `## 今日质量简报` section and `**质量含义：**` notes.

**Step 2: Update the Jinja2 template**

Add a "今日质量简报" box at the top of each date's content. Change section labels from brand-groups to score-groups (🚨 / ⚠️ / 📊). Show `market` badge instead of `region`. Show `note` under summary when present.

**Step 3: Run existing site builder tests**

```bash
ept uv run pytest tests/test_site_builder.py -v
```
Fix any broken assertions (field name `市场` vs `地区`).

**Step 4: Build site locally and verify**

```bash
ept uv run python -m entrypoints.build_site
open site/index.html
```

**Step 5: Commit**

```bash
git add src/site_builder.py src/templates/index.html.j2 tests/test_site_builder.py
git commit -m "feat: update site template for score-based sections and market labels"
```

---

### Task 8: End-to-end smoke test and final cleanup

**Files:**
- All modified files

**Step 1: Run full test suite**

```bash
ept uv run pytest tests/ -v
```
Expected: all tests pass.

**Step 2: Run local dry-run of full pipeline (mocked LLM)**

```bash
ept uv run python -c "
import os
os.environ['LLM_API_KEY'] = 'dummy'
os.environ['LLM_BASE_URL'] = 'https://open.bigmodel.cn/api/paas/v4/'
os.environ['LLM_MODEL'] = 'glm-4-flash'
os.environ['FEISHU_BOT_WEBHOOK'] = 'https://dummy'
# Verify collectors load without error
from src.collectors.feeds import ALL_REGIONAL_FEEDS
print('Regions:', list(ALL_REGIONAL_FEEDS.keys()))
"
```

**Step 3: Push and trigger workflow**

```bash
git push
gh workflow run collect-daily
```
Monitor with:
```bash
gh run list --workflow=collect-daily --limit=3
```

**Step 4: Verify output**

Check that:
- Report at `reports/YYYY-MM-DD.md` has 今日质量简报 section
- score=0 articles absent from report
- `市场:` labels show specific regions (not "全球" for US articles)
- Feishu card shows score counts

