# Automotive News Daily — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Daily collector of 35+ global automotive news articles with Zhipu GLM-4-flash 100-word English summaries, pushed to Feishu group bot as interactive cards every morning at 09:00 Beijing time.

**Architecture:** Pure RSS + regulatory API (Method A). feedparser pulls ~65 RSS feeds; httpx fetches SAMR/RAPEX/KBA regulatory data; GLM-4-flash generates summaries concurrently; feishu.py posts interactive card to webhook. GitHub Actions cron runs daily, stores daily reports as Markdown files in git.

**Tech Stack:** Python 3.12, uv, feedparser, httpx, openai (OpenAI-compatible, points to 智谱), tenacity, python-dotenv, pytest, ruff. Mirrors humanoid-tech-ops structure exactly.

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py`, `src/collectors/__init__.py`, `src/delivery/__init__.py`
- Create: `entrypoints/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/.gitkeep`
- Create: `reports/.gitkeep`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "automotive-news-daily"
version = "0.1.0"
description = "每日全球汽车行业新闻采集 + 智谱摘要 + 飞书推送"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.40.0",
    "feedparser>=6.0.11",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.1",
    "tenacity>=8.5.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3.0", "ruff>=0.6.0"]

[tool.ruff]
line-length = 100
```

**Step 2: Create .env.example**

```
LLM_API_KEY=
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=glm-4-flash
FEISHU_BOT_WEBHOOK=
```

**Step 3: Create .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
data/seen.json
```

**Step 4: Create all `__init__.py` files and placeholder directories**

```bash
mkdir -p src/collectors src/delivery entrypoints tests data reports
touch src/__init__.py src/collectors/__init__.py src/delivery/__init__.py
touch entrypoints/__init__.py tests/__init__.py
touch data/.gitkeep reports/.gitkeep
```

**Step 5: Install dependencies**

```bash
ept uv sync --extra dev
```

Expected: resolves and installs all packages without error.

**Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/ entrypoints/ tests/ data/ reports/
git commit -m "chore: project scaffold"
```

---

### Task 2: schemas.py + config.py

**Files:**
- Create: `src/schemas.py`
- Create: `src/config.py`
- Create: `tests/test_schemas.py`

**Step 1: Write failing tests**

```python
# tests/test_schemas.py
from src.schemas import NewsItem, url_hash

def test_url_hash_stable():
    assert url_hash("https://example.com/a") == url_hash("https://example.com/a")

def test_url_hash_different():
    assert url_hash("https://a.com") != url_hash("https://b.com")

def test_news_item_hash_id():
    item = NewsItem(url="https://x.com/1", title="T", source_name="s",
                    region="欧洲", published_at="", raw_text="")
    assert len(item.hash_id) == 16

def test_news_item_defaults():
    item = NewsItem(url="u", title="t", source_name="s",
                    region="中国", published_at="", raw_text="")
    assert item.priority == "P3"
    assert item.brand == ""
    assert item.summary == ""
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.schemas'`

**Step 3: Write src/schemas.py**

```python
import hashlib
from dataclasses import dataclass, field
from typing import Literal

Priority = Literal["P0", "P1", "P2", "P3"]

def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]

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

    @property
    def hash_id(self) -> str:
        return url_hash(self.url)
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_schemas.py -v
```

Expected: 4 passed.

**Step 5: Write src/config.py**

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

_REQUIRED = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "FEISHU_BOT_WEBHOOK"]

@dataclass(frozen=True)
class Config:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    feishu_bot_webhook: str

def load_config() -> Config:
    load_dotenv()
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise ValueError(f"missing env vars: {missing}")
    return Config(
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_model=os.environ["LLM_MODEL"],
        feishu_bot_webhook=os.environ["FEISHU_BOT_WEBHOOK"],
    )
```

**Step 6: Commit**

```bash
git add src/schemas.py src/config.py tests/test_schemas.py
git commit -m "feat: schemas and config"
```

---

### Task 3: LLM Client

**Files:**
- Create: `src/llm_client.py`
- Create: `tests/test_llm_client.py`

**Step 1: Write failing test (uses monkeypatch — no real API call)**

```python
# tests/test_llm_client.py
from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient
from src.config import Config

def _cfg():
    return Config(llm_api_key="k", llm_base_url="https://x.com/v4/",
                  llm_model="glm-4-flash", feishu_bot_webhook="https://w")

def test_chat_returns_content(monkeypatch):
    client = LLMClient(_cfg())
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "hello"
    monkeypatch.setattr(client._client.chat.completions, "create",
                        lambda **_: mock_resp)
    result = client.chat(system="sys", user="usr")
    assert result == "hello"
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_llm_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.llm_client'`

**Step 3: Write src/llm_client.py**

```python
"""Multi-provider LLM client (OpenAI-compatible). Retries 3x then circuit-breaks."""
import logging
from openai import OpenAI, BadRequestError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from src.config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)

    # 400 BadRequest = content filter / bad params, never retry (智谱 1301)
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_not_exception_type(BadRequestError), reraise=True)
    def chat(self, *, system: str, user: str, max_tokens: int = 300,
             temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_llm_client.py -v
```

Expected: 1 passed.

**Step 5: Commit**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat: llm client with retry circuit breaker"
```

---

### Task 4: RSS Collector + Feed List

**Files:**
- Create: `src/collectors/feeds.py`
- Create: `src/collectors/base.py`
- Create: `src/collectors/rss.py`
- Create: `tests/test_rss_collector.py`

**Step 1: Write failing tests**

```python
# tests/test_rss_collector.py
from unittest.mock import patch, MagicMock
from src.collectors.rss import RssCollector
from src.schemas import NewsItem

_FAKE_ENTRY = {
    "link": "https://example.com/news/1",
    "title": "BYD announces new EV model",
    "published": "2026-06-29T08:00:00Z",
    "summary": "BYD has unveiled its new electric sedan.",
}

def test_rss_collector_returns_news_items():
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[MagicMock(**_FAKE_ENTRY)])
        collector = RssCollector(feeds=["https://example.com/rss"], region="中国")
        items = collector.collect()
    assert len(items) == 1
    assert isinstance(items[0], NewsItem)
    assert items[0].url == "https://example.com/news/1"
    assert items[0].region == "中国"

def test_rss_collector_skips_failed_feed():
    with patch("feedparser.parse", side_effect=Exception("timeout")):
        collector = RssCollector(feeds=["https://bad.example.com/rss"], region="全球")
        items = collector.collect()
    assert items == []

def test_rss_collector_deduplicates_within_batch():
    entry = MagicMock(**_FAKE_ENTRY)
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[entry, entry])
        collector = RssCollector(feeds=["https://a.com/rss", "https://b.com/rss"], region="全球")
        items = collector.collect()
    assert len(items) == 1
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_rss_collector.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Write src/collectors/base.py**

```python
import logging
from abc import ABC, abstractmethod
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    name: str = "base"

    @abstractmethod
    def collect(self) -> list[NewsItem]:
        ...
```

**Step 4: Write src/collectors/rss.py**

```python
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
```

**Step 5: Write src/collectors/feeds.py**

```python
"""All RSS feed URLs grouped by region. Verify each URL on first run."""

# ── Global / Multilingual ──────────────────────────────────────────────────
GLOBAL_FEEDS = [
    "https://www.motor1.com/rss/news/all/",
    "https://insideevs.com/feed/",
    "https://electrek.co/feed/",
    "https://www.caranddriver.com/rss/all.xml/",
    "https://www.theverge.com/rss/transportation/index.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.wardsauto.com/rss.xml",
    # carnewschina.com — best English coverage of Chinese brands globally
    "https://carnewschina.com/feed/",
    # Gasgoo — Chinese auto industry in English
    "https://auto.gasgoo.com/RSS/automotive_news.xml",
]

# ── China / Chinese Brands ─────────────────────────────────────────────────
CHINA_FEEDS = [
    "https://auto.sina.com.cn/rss.xml",         # 新浪汽车 (verify)
    "https://www.autohome.com.cn/rss/news.xml",  # 汽车之家 (verify)
    "https://36kr.com/feed",                     # 36kr general (filter by keyword)
    "https://www.gasgoo.com/RSS/automotive_news.xml",
    # 理想汽车 IR newsroom — check if RSS exists, else use press page
    # TODO: verify https://ir.lixiang.com/rss or newsroom RSS
]

# ── Europe ─────────────────────────────────────────────────────────────────
EUROPE_FEEDS = [
    "https://www.auto-motor-und-sport.de/rss/",   # Germany
    "https://www.autobild.de/rss/",               # Germany
    "https://www.heise.de/autos/rss/",            # Germany
    "https://de.motor1.com/rss/",                 # Germany (Motor1 DE)
    "https://www.autocar.co.uk/rss",              # UK
    "https://www.autoexpress.co.uk/feed",         # UK
    "https://www.motor1.com/rss/news/all/",       # UK (Motor1 global, EN)
    "https://www.drivingelectric.com/feed",       # UK EV
    "https://www.turbo.fr/feed/",                 # France (verify)
    "https://it.motor1.com/rss/",                 # Italy
]

# ── Russia / CIS ──────────────────────────────────────────────────────────
# These sites don't natively provide RSS — use RSS.app to convert:
#   1. Go to https://rss.app  2. Enter site URL  3. Get generated feed URL
#   Replace placeholder URLs below after generating in RSS.app
RUSSIA_FEEDS = [
    "https://www.drom.ru/news/?rss=1",           # Drom.ru (may work directly)
    "https://www.kolesa.ru/rss.xml",             # Kolesa.ru (verify)
    "https://www.kolesa.kz/rss.xml",             # Kazakhstan (verify)
    # TODO: replace with RSS.app URLs if above don't work:
    # "https://rss.app/feeds/<id>.xml",           # Drom.ru via RSS.app
    # "https://rss.app/feeds/<id>.xml",           # Kolesa.kz via RSS.app
]

# ── Middle East ───────────────────────────────────────────────────────────
# Most Middle East auto sites lack native RSS — generate via https://rss.app
MIDDLE_EAST_FEEDS = [
    # TODO: generate RSS.app feeds for these sites:
    # "https://rss.app/feeds/<id>.xml",  # Drive Arabia (drivearabia.com)
    # "https://rss.app/feeds/<id>.xml",  # ArabWheels (arabwheels.ae)
    # "https://rss.app/feeds/<id>.xml",  # Gulf News Motors
    # "https://rss.app/feeds/<id>.xml",  # Motory.sa
]

# ── Southeast Asia ────────────────────────────────────────────────────────
SEA_FEEDS = [
    "https://paultan.org/feed/",                  # Malaysia — most authoritative in SEA
    "https://www.wapcar.my/sitemap/rss.xml",      # Malaysia (verify)
    "https://www.headlightmag.com/feed/",         # Thailand
    "https://www.bangkokpost.com/rss/data/motoring.xml",  # Thailand (verify)
    "https://www.sgcarmart.com/rss/latest_news.xml",      # Singapore
    "https://www.torque.com.sg/feed/",            # Singapore (verify)
]

# ── East Asia ─────────────────────────────────────────────────────────────
EAST_ASIA_FEEDS = [
    "https://response.jp/rss/",                   # Japan — largest auto media
    "https://car.watch.impress.co.jp/rss/",       # Japan Car Watch (verify)
    "https://thekoreancarblog.com/feed/",         # Korea (English)
    # Hong Kong: (verify RSS availability)
    # "https://www.goauto.hk/rss.xml",
]

# ── Quality / Regulatory ──────────────────────────────────────────────────
# Note: these are handled by dedicated collectors (samr.py, rapex.py, kba.py)
# NHTSA RSS kept here for reference
QUALITY_FEEDS = [
    # NHTSA recalls — use API endpoint, not RSS
    # Transport Canada — use API endpoint
]
```

**Step 6: Run tests to verify PASS**

```bash
ept uv run pytest tests/test_rss_collector.py -v
```

Expected: 3 passed.

**Step 7: Commit**

```bash
git add src/collectors/ tests/test_rss_collector.py
git commit -m "feat: rss collector + 65-feed list"
```

---

### Task 5: Regulatory Collectors (SAMR, RAPEX, NHTSA)

**Files:**
- Create: `src/collectors/samr.py`
- Create: `src/collectors/rapex.py`
- Create: `src/collectors/nhtsa.py`
- Create: `tests/test_regulatory.py`

**Step 1: Write failing tests**

```python
# tests/test_regulatory.py
from unittest.mock import patch, MagicMock
from src.collectors.samr import SamrCollector
from src.collectors.rapex import RapexCollector
from src.collectors.nhtsa import NhtsaCollector
from src.schemas import NewsItem

_SAMR_XML = """<?xml version="1.0"?>
<recalls>
  <recall>
    <title>理想汽车召回部分 L9 车辆</title>
    <url>https://www.samr.gov.cn/cpgls/12345</url>
    <pubDate>2026-06-29</pubDate>
    <description>因悬架问题召回 1200 辆</description>
  </recall>
</recalls>"""

def test_samr_returns_news_items():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=_SAMR_XML, status_code=200)
        items = SamrCollector().collect()
    assert len(items) == 1
    assert items[0].region == "中国"
    assert items[0].priority == "P3"  # filter.py assigns priority later

def test_samr_handles_http_error():
    with patch("httpx.get", side_effect=Exception("connection reset")):
        items = SamrCollector().collect()
    assert items == []

def test_nhtsa_returns_news_items():
    _xml = """<rss><channel>
      <item>
        <title>NHTSA Recall: Li Auto L7 investigation</title>
        <link>https://www.nhtsa.gov/recall/123</link>
        <pubDate>Mon, 29 Jun 2026 00:00:00 GMT</pubDate>
        <description>Investigation opened.</description>
      </item>
    </channel></rss>"""
    with patch("feedparser.parse") as mock:
        entry = MagicMock()
        entry.title = "NHTSA Recall: Li Auto L7 investigation"
        entry.link = "https://www.nhtsa.gov/recall/123"
        entry.published = "Mon, 29 Jun 2026 00:00:00 GMT"
        entry.summary = "Investigation opened."
        mock.return_value = MagicMock(entries=[entry])
        items = NhtsaCollector().collect()
    assert len(items) == 1
    assert items[0].region == "北美"
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_regulatory.py -v
```

**Step 3: Write src/collectors/samr.py**

```python
"""SAMR (中国市场监管总局) 缺陷产品召回公告采集。"""
import logging
import httpx
from xml.etree import ElementTree as ET
from src.collectors.base import BaseCollector
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

# SAMR 缺陷产品召回公开数据入口（需验证当前有效 URL）
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
```

**Step 4: Write src/collectors/rapex.py**

```python
"""EU Safety Gate (RAPEX) 周报 XML 下载。每周更新，每日 collector 也调——幂等。"""
import logging
import httpx
from xml.etree import ElementTree as ET
from src.collectors.base import BaseCollector
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

# EU Safety Gate 周报 XML（官方 URL，需定期验证）
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
        # RAPEX XML schema: <RAPEX_WEEKLY><ALERT category="...">...</ALERT>
        for alert in root.findall(".//ALERT"):
            category = alert.get("category", "")
            if "vehicle" not in category.lower() and "motor" not in category.lower():
                continue  # only keep vehicle-related alerts
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
```

**Step 5: Write src/collectors/nhtsa.py**

```python
"""NHTSA recalls — uses feedparser on the RSS endpoint."""
import logging
import feedparser
from src.collectors.base import BaseCollector
from src.schemas import NewsItem, url_hash

logger = logging.getLogger(__name__)

_NHTSA_FEED = "https://www.nhtsa.gov/rss-feeds/recalls-rss.xml"

class NhtsaCollector(BaseCollector):
    name = "nhtsa"

    def collect(self) -> list[NewsItem]:
        try:
            feed = feedparser.parse(_NHTSA_FEED)
        except Exception as ex:
            logger.warning("nhtsa feed failed: %s", ex)
            return []

        seen: set[str] = set()
        out: list[NewsItem] = []
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
                url=link, title=title, source_name="NHTSA",
                region="北美",
                published_at=getattr(e, "published", ""),
                raw_text=(getattr(e, "summary", "") or "")[:2000],
            ))
        logger.info("nhtsa collected %d recalls", len(out))
        return out
```

**Step 6: Run tests to verify PASS**

```bash
ept uv run pytest tests/test_regulatory.py -v
```

Expected: 3 passed.

**Step 7: Commit**

```bash
git add src/collectors/samr.py src/collectors/rapex.py src/collectors/nhtsa.py tests/test_regulatory.py
git commit -m "feat: regulatory collectors (SAMR, RAPEX, NHTSA)"
```

---

### Task 6: Filter Module (Multilingual Keywords + Priority)

**Files:**
- Create: `src/filter.py`
- Create: `tests/test_filter.py`

**Step 1: Write failing tests**

```python
# tests/test_filter.py
from src.schemas import NewsItem
from src.filter import is_automotive, assign_priority, filter_and_prioritize

def _item(title: str, raw_text: str = "") -> NewsItem:
    return NewsItem(url="https://x.com", title=title, source_name="s",
                    region="r", published_at="", raw_text=raw_text)

# ── is_automotive ───────────────────────────────────────────────────────────
def test_is_automotive_english():
    assert is_automotive(_item("BYD launches new electric vehicle in Germany"))

def test_is_automotive_chinese():
    assert is_automotive(_item("比亚迪发布新款电动车"))

def test_is_automotive_russian():
    assert is_automotive(_item("BYD открывает завод в России", "новый автомобиль"))

def test_is_automotive_rejects_unrelated():
    assert not is_automotive(_item("Apple launches new iPhone 17"))

# ── assign_priority ─────────────────────────────────────────────────────────
def test_p0_li_auto_recall():
    item = assign_priority(_item("理想汽车召回 L9 车辆 因刹车缺陷"))
    assert item.priority == "P0"
    assert item.brand == "Li Auto"

def test_p0_li_auto_recall_english():
    item = assign_priority(_item("Li Auto recalls 1200 units in Kazakhstan"))
    assert item.priority == "P0"

def test_p1_li_auto_non_recall():
    item = assign_priority(_item("理想汽车 Q2 欧洲销量增长 43%"))
    assert item.priority == "P1"

def test_p2_other_cn_brand():
    item = assign_priority(_item("BYD opens new factory in Hungary"))
    assert item.priority == "P2"
    assert item.brand == "BYD"

def test_p3_global_brand():
    item = assign_priority(_item("Toyota announces new hybrid lineup"))
    assert item.priority == "P3"

# ── filter_and_prioritize ───────────────────────────────────────────────────
def test_filter_removes_non_automotive():
    items = [
        _item("Tesla model Y price cut"),
        _item("Taylor Swift new album"),
        _item("AITO M9 sales record"),
    ]
    result = filter_and_prioritize(items)
    assert len(result) == 2

def test_filter_preserves_order_by_priority():
    items = [
        _item("Toyota new model"),        # P3
        _item("Li Auto recall notice"),   # P0
        _item("BYD enters Europe"),       # P2
    ]
    result = filter_and_prioritize(items)
    assert result[0].priority == "P0"
    assert result[1].priority == "P2"
    assert result[2].priority == "P3"
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_filter.py -v
```

**Step 3: Write src/filter.py**

```python
"""Automotive keyword filter + multi-language priority scoring."""
import re
from src.schemas import NewsItem, Priority

# ── Keyword dictionaries ─────────────────────────────────────────────────────

LI_AUTO_VARIANTS = [
    "理想汽车", "理想", "aito", "li auto", "lixiang",
    "лисян", "ли сян", "리샹", "リシャン", "ليكسيانغ",
]

CN_BRANDS = [
    "比亚迪", "byd", "蔚来", "nio", "小鹏", "xpeng",
    "吉利", "geely", "问界", "华为汽车", "长城", "哈弗",
    "奇瑞", "chery", "长安", "mg", "上汽", "saic",
    "零跑", "leapmotor", "岚图", "voyah", "极氪", "zeekr",
    "深蓝", "仰望", "方程豹", "smart", "坦克", "tank",
]

QUALITY_VARIANTS = [
    "召回", "recall", "rückruf", "rappel", "отзыв",
    "استدعاء", "缺陷", "安全隐患", "故障", "投诉",
    "quality issue", "defect", "safety alert", "investigation",
    "probe", "nhtsa", "samr", "rapex", "tsrc",
]

AUTO_GENERIC = [
    "汽车", "electric vehicle", " ev ", "car", " auto ", "vehicle",
    "sedan", "suv", "pickup", "truck", "hybrid", "battery",
    "charging", "range", "motor", "fahrzeug", "voiture",
    "автомобиль", "سيارة", "รถยนต์", "xe hơi",
    "tesla", "volkswagen", "toyota", "bmw", "mercedes", "ford",
    "gm ", "general motors", "honda", "hyundai", "kia",
]

def _text(item: NewsItem) -> str:
    return (item.title + " " + item.raw_text).lower()

def _matches_any(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)

def is_automotive(item: NewsItem) -> bool:
    text = _text(item)
    all_kw = LI_AUTO_VARIANTS + CN_BRANDS + QUALITY_VARIANTS + AUTO_GENERIC
    return _matches_any(text, all_kw)

def assign_priority(item: NewsItem) -> NewsItem:
    text = _text(item)
    is_quality = _matches_any(text, QUALITY_VARIANTS)
    is_li_auto = _matches_any(text, LI_AUTO_VARIANTS)
    is_cn = _matches_any(text, CN_BRANDS)

    if is_li_auto and is_quality:
        item.priority = "P0"
        item.brand = "Li Auto"
    elif is_li_auto:
        item.priority = "P1"
        item.brand = "Li Auto"
    elif is_cn:
        item.priority = "P2"
        for brand_kw in CN_BRANDS:
            if brand_kw in text:
                item.brand = brand_kw
                break
    else:
        item.priority = "P3"
    return item

_PRIORITY_ORDER: dict[Priority, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

def filter_and_prioritize(items: list[NewsItem]) -> list[NewsItem]:
    filtered = [assign_priority(item) for item in items if is_automotive(item)]
    return sorted(filtered, key=lambda x: _PRIORITY_ORDER[x.priority])
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_filter.py -v
```

Expected: 10 passed.

**Step 5: Commit**

```bash
git add src/filter.py tests/test_filter.py
git commit -m "feat: multilingual keyword filter + priority scoring"
```

---

### Task 7: Dedup Module

**Files:**
- Create: `src/dedup.py`
- Create: `tests/test_dedup.py`

**Step 1: Write failing tests**

```python
# tests/test_dedup.py
import json, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from src.schemas import NewsItem
from src.dedup import deduplicate

def _item(url: str) -> NewsItem:
    return NewsItem(url=url, title="t", source_name="s",
                    region="r", published_at="", raw_text="")

def test_new_items_pass_through(tmp_path):
    items = [_item("https://a.com"), _item("https://b.com")]
    with patch("src.dedup.SEEN_FILE", tmp_path / "seen.json"):
        result = deduplicate(items)
    assert len(result) == 2

def test_already_seen_items_filtered(tmp_path):
    item = _item("https://a.com")
    seen_file = tmp_path / "seen.json"
    now = datetime.now(timezone.utc).isoformat()
    seen_file.write_text(json.dumps({item.hash_id: now}))
    with patch("src.dedup.SEEN_FILE", seen_file):
        result = deduplicate([item])
    assert result == []

def test_old_entries_evicted(tmp_path):
    item = _item("https://a.com")
    seen_file = tmp_path / "seen.json"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    seen_file.write_text(json.dumps({item.hash_id: old_ts}))
    with patch("src.dedup.SEEN_FILE", seen_file):
        result = deduplicate([item])
    assert len(result) == 1

def test_seen_file_updated_after_dedup(tmp_path):
    item = _item("https://new.com")
    seen_file = tmp_path / "seen.json"
    with patch("src.dedup.SEEN_FILE", seen_file):
        deduplicate([item])
    saved = json.loads(seen_file.read_text())
    assert item.hash_id in saved
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_dedup.py -v
```

**Step 3: Write src/dedup.py**

```python
"""URL-hash deduplication with a 3-day sliding window stored in data/seen.json."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.schemas import NewsItem

SEEN_FILE = Path("data/seen.json")
_WINDOW_DAYS = 3

def _load() -> dict[str, str]:
    if not SEEN_FILE.exists():
        return {}
    return json.loads(SEEN_FILE.read_text())

def _save(seen: dict[str, str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))

def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    seen = _load()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)).isoformat()
    seen = {h: ts for h, ts in seen.items() if ts >= cutoff}

    now = datetime.now(timezone.utc).isoformat()
    out: list[NewsItem] = []
    for item in items:
        h = item.hash_id
        if h not in seen:
            seen[h] = now
            out.append(item)
    _save(seen)
    return out
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_dedup.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/dedup.py tests/test_dedup.py
git commit -m "feat: url-hash dedup with 3-day sliding window"
```

---

### Task 8: Summarizer Module

**Files:**
- Create: `src/summarizer.py`
- Create: `tests/test_summarizer.py`

**Step 1: Write failing tests**

```python
# tests/test_summarizer.py
from unittest.mock import MagicMock
from src.schemas import NewsItem
from src.summarizer import summarize_item, summarize_all

def _item(url: str, title: str) -> NewsItem:
    return NewsItem(url=url, title=title, source_name="s",
                    region="r", published_at="", raw_text="some content")

def test_summarize_item_fills_summary():
    llm = MagicMock()
    llm.chat.return_value = "Li Auto recalled 1200 units in Kazakhstan."
    item = _item("https://a.com", "Li Auto recall")
    result = summarize_item(llm, item)
    assert result.summary == "Li Auto recalled 1200 units in Kazakhstan."
    assert llm.chat.called

def test_summarize_item_fallback_on_error():
    llm = MagicMock()
    llm.chat.side_effect = Exception("API error")
    item = _item("https://b.com", "Fallback title")
    result = summarize_item(llm, item)
    assert result.summary == "Fallback title"

def test_summarize_all_preserves_order():
    llm = MagicMock()
    llm.chat.side_effect = lambda **_: "summary"
    items = [_item(f"https://x.com/{i}", f"title {i}") for i in range(5)]
    results = summarize_all(llm, items, max_workers=2)
    assert [r.url for r in results] == [i.url for i in items]

def test_summarize_all_returns_all_even_with_errors():
    llm = MagicMock()
    llm.chat.side_effect = [Exception("err"), "good summary", Exception("err")]
    items = [_item(f"https://x.com/{i}", f"t{i}") for i in range(3)]
    results = summarize_all(llm, items, max_workers=3)
    assert len(results) == 3
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_summarizer.py -v
```

**Step 3: Write src/summarizer.py**

```python
"""Concurrent GLM-4-flash summarizer: 100-word English summary per NewsItem."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an automotive industry analyst. Summarize the following news item "
    "in exactly 100 English words. Cover: what happened, which brand/model, "
    "which market/region, and why it matters to the industry. "
    "Do not invent facts not present in the source."
)

def summarize_item(llm: LLMClient, item: NewsItem) -> NewsItem:
    try:
        item.summary = llm.chat(
            system=_SYSTEM,
            user=f"Title: {item.title}\n\nContent: {item.raw_text[:1500]}",
            max_tokens=250,
            temperature=0.2,
        )
    except Exception as ex:
        logger.warning("summarize failed for %s: %s", item.url, ex)
        item.summary = item.title
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

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_summarizer.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/summarizer.py tests/test_summarizer.py
git commit -m "feat: concurrent glm-4-flash summarizer"
```

---

### Task 9: Feishu Delivery

**Files:**
- Create: `src/delivery/feishu.py`
- Create: `tests/test_feishu.py`

**Step 1: Write failing tests**

```python
# tests/test_feishu.py
from unittest.mock import patch, MagicMock
from src.schemas import NewsItem
from src.delivery.feishu import build_card, send_card

def _item(title: str, priority: str, brand: str = "", region: str = "全球") -> NewsItem:
    item = NewsItem(url="https://x.com", title=title, source_name="s",
                    region=region, published_at="2026-06-29", raw_text="")
    item.priority = priority
    item.brand = brand
    item.summary = "This is a 100-word English summary of the news item."
    return item

def test_build_card_returns_dict():
    items = [_item("Li Auto recall", "P0", "Li Auto", "中亚")]
    card = build_card(items, date="2026-06-29")
    assert isinstance(card, dict)
    assert card["msg_type"] == "interactive"
    assert "card" in card

def test_build_card_includes_all_sections():
    items = [
        _item("Li Auto recall", "P0", "Li Auto"),
        _item("Li Auto sales", "P1", "Li Auto"),
        _item("BYD in Europe", "P2", "BYD"),
        _item("Toyota new hybrid", "P3"),
    ]
    card = build_card(items, date="2026-06-29")
    content = str(card)
    assert "🚨" in content  # P0 section
    assert "⭐" in content  # P1 section
    assert "🇨🇳" in content  # P2 section
    assert "🌍" in content  # P3 section

def test_send_card_posts_to_webhook():
    items = [_item("BYD news", "P2", "BYD")]
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_card(items, webhook="https://webhook.example.com", date="2026-06-29")
    assert mock_post.called
    call_url = mock_post.call_args[0][0]
    assert call_url == "https://webhook.example.com"

def test_send_card_splits_on_large_batch():
    items = [_item(f"News {i}", "P3") for i in range(25)]
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_card(items, webhook="https://wh.example.com", date="2026-06-29")
    # 25 items > 20 threshold → should call post twice
    assert mock_post.call_count == 2
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_feishu.py -v
```

**Step 3: Write src/delivery/feishu.py**

```python
"""Build Feishu interactive card + send to group bot webhook."""
import logging
import httpx
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SECTION_HEADERS = {
    "P0": "🚨 质量预警 & 召回",
    "P1": "⭐ 理想汽车动态",
    "P2": "🇨🇳 中国品牌出海",
    "P3": "🌍 国际品牌动态",
}

_MAX_PER_CARD = 20  # split into multiple cards if exceeded

def _format_item(item: NewsItem) -> str:
    brand_tag = f"**[{item.brand}]** " if item.brand else ""
    summary = item.summary or item.title
    return (
        f"{brand_tag}{item.title}\n"
        f"{summary}\n"
        f"🔗 {item.url}  📍 {item.region}"
    )

def _build_elements(items: list[NewsItem]) -> list[dict]:
    by_priority: dict[str, list[NewsItem]] = {"P0": [], "P1": [], "P2": [], "P3": []}
    for item in items:
        by_priority.setdefault(item.priority, by_priority["P3"]).append(item)

    elements: list[dict] = []
    for prio, header in _SECTION_HEADERS.items():
        group = by_priority.get(prio, [])
        if not group:
            continue
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{header}  ({len(group)}条)**"}
        })
        elements.append({"tag": "hr"})
        for item in group:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": _format_item(item)}
            })
            elements.append({"tag": "hr"})
    return elements

def build_card(items: list[NewsItem], date: str) -> dict:
    elements = _build_elements(items)
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚗 汽车行业日报  {date}  |  {len(items)} 条新闻",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }

def send_card(items: list[NewsItem], webhook: str, date: str) -> None:
    chunks = [items[i:i + _MAX_PER_CARD] for i in range(0, len(items), _MAX_PER_CARD)]
    for idx, chunk in enumerate(chunks, 1):
        label = f"({idx}/{len(chunks)})" if len(chunks) > 1 else ""
        card = build_card(chunk, date=f"{date} {label}".strip())
        try:
            resp = httpx.post(webhook, json=card, timeout=15)
            resp.raise_for_status()
            logger.info("feishu card %d/%d sent (%d items)", idx, len(chunks), len(chunk))
        except Exception as ex:
            logger.error("feishu send failed chunk %d: %s", idx, ex)
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_feishu.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/delivery/feishu.py tests/test_feishu.py
git commit -m "feat: feishu interactive card builder + webhook sender"
```

---

### Task 10: Main Entrypoint

**Files:**
- Create: `entrypoints/collect_daily.py`
- Create: `tests/test_collect_daily.py`

**Step 1: Write failing test (integration-level smoke)**

```python
# tests/test_collect_daily.py
from unittest.mock import patch, MagicMock
from src.schemas import NewsItem

def _fake_item(url: str, title: str, priority: str = "P3") -> NewsItem:
    item = NewsItem(url=url, title=title, source_name="s",
                    region="全球", published_at="", raw_text="content")
    item.priority = priority
    item.summary = "100-word English summary."
    return item

def test_main_runs_without_error(tmp_path):
    fake_items = [_fake_item(f"https://x.com/{i}", f"Car News {i}") for i in range(5)]
    with (
        patch("entrypoints.collect_daily.RssCollector") as MockRss,
        patch("entrypoints.collect_daily.SamrCollector") as MockSamr,
        patch("entrypoints.collect_daily.RapexCollector") as MockRapex,
        patch("entrypoints.collect_daily.NhtsaCollector") as MockNhtsa,
        patch("entrypoints.collect_daily.filter_and_prioritize", return_value=fake_items),
        patch("entrypoints.collect_daily.deduplicate", return_value=fake_items),
        patch("entrypoints.collect_daily.summarize_all", return_value=fake_items),
        patch("entrypoints.collect_daily.send_card"),
        patch("entrypoints.collect_daily.load_config",
              return_value=MagicMock(llm_api_key="k", llm_base_url="u",
                                     llm_model="m", feishu_bot_webhook="w")),
        patch("entrypoints.collect_daily.REPORTS_DIR", tmp_path),
    ):
        for Mock in [MockRss, MockSamr, MockRapex, MockNhtsa]:
            Mock.return_value.collect.return_value = fake_items
        from entrypoints.collect_daily import main
        exit_code = main()
    assert exit_code == 0

def test_main_exits_zero_when_no_items(tmp_path):
    with (
        patch("entrypoints.collect_daily.RssCollector") as MockRss,
        patch("entrypoints.collect_daily.SamrCollector") as MockSamr,
        patch("entrypoints.collect_daily.RapexCollector") as MockRapex,
        patch("entrypoints.collect_daily.NhtsaCollector") as MockNhtsa,
        patch("entrypoints.collect_daily.filter_and_prioritize", return_value=[]),
        patch("entrypoints.collect_daily.deduplicate", return_value=[]),
        patch("entrypoints.collect_daily.load_config",
              return_value=MagicMock(llm_api_key="k", llm_base_url="u",
                                     llm_model="m", feishu_bot_webhook="w")),
        patch("entrypoints.collect_daily.REPORTS_DIR", tmp_path),
    ):
        for Mock in [MockRss, MockSamr, MockRapex, MockNhtsa]:
            Mock.return_value.collect.return_value = []
        from entrypoints.collect_daily import main
        exit_code = main()
    assert exit_code == 0
```

**Step 2: Run to verify FAIL**

```bash
ept uv run pytest tests/test_collect_daily.py -v
```

**Step 3: Write entrypoints/collect_daily.py**

```python
"""Daily entrypoint: collect → filter → dedup → summarize → report + push."""
import logging
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
from src.delivery.feishu import send_card

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("collect_daily")

REPORTS_DIR = Path("reports")
TOP_N = 35

def main() -> int:
    cfg = load_config()
    llm = LLMClient(cfg)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Collect from all sources
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

    # 2. Filter + priority
    relevant = filter_and_prioritize(raw)
    log.info("after filter: %d items", len(relevant))

    # 3. Dedup (3-day window)
    fresh = deduplicate(relevant)
    log.info("after dedup: %d fresh items", len(fresh))

    if not fresh:
        log.warning("no fresh items today, skipping report")
        return 0

    # 4. Take top N by priority (already sorted P0→P3)
    top = fresh[:TOP_N]

    # 5. Summarize concurrently
    summarized = summarize_all(llm, top, max_workers=5)
    log.info("summarized %d items", len(summarized))

    # 6. Save Markdown report
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"{today}.md"
    _write_report(summarized, report_path, today)
    log.info("report saved: %s", report_path)

    # 7. Push to Feishu
    send_card(summarized, webhook=cfg.feishu_bot_webhook, date=today)
    log.info("feishu push complete")
    return 0

def _write_report(items, path: Path, date: str) -> None:
    from src.delivery.feishu import _SECTION_HEADERS
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
```

**Step 4: Run to verify PASS**

```bash
ept uv run pytest tests/test_collect_daily.py -v
```

Expected: 2 passed.

**Step 5: Run full test suite**

```bash
ept uv run pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add entrypoints/collect_daily.py tests/test_collect_daily.py
git commit -m "feat: main collect_daily entrypoint"
```

---

### Task 11: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/collect-daily.yml`

**Step 1: Write .github/workflows/collect-daily.yml**

```yaml
name: collect-daily

on:
  schedule:
    - cron: '0 1 * * *'     # 01:00 UTC = 09:00 Beijing
  workflow_dispatch:          # allow manual trigger for testing

permissions:
  contents: write             # needed to git push reports/ + data/seen.json

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      UV_INDEX_URL: https://pypi.org/simple

    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync

      - name: Run collect_daily
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_BASE_URL: https://open.bigmodel.cn/api/paas/v4/
          LLM_MODEL: glm-4-flash
          FEISHU_BOT_WEBHOOK: ${{ secrets.FEISHU_BOT_WEBHOOK }}
        run: uv run python -m entrypoints.collect_daily

      - name: Commit reports and seen.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add reports/ data/seen.json
          git diff --cached --quiet || git commit -m "chore: daily report $(date -u +%Y-%m-%d)"
          git push
```

**Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/collect-daily.yml
git commit -m "ci: github actions daily collect cron"
```

---

### Task 12: GitHub Setup + Smoke Test

**Step 1: Create public GitHub repo**

```bash
# Install gh if needed: ept tool enable gh
gh repo create automotive-news-daily --public --source=. --remote=origin --push
```

Expected: repo created at `https://github.com/<your-username>/automotive-news-daily`

**Step 2: Set GitHub Secrets**

```bash
# Copy LLM_API_KEY from humanoid-tech-ops .env
gh secret set LLM_API_KEY --body "$(grep LLM_API_KEY /Users/zhangrui1/humanoid-tech-ops/.env | cut -d= -f2-)"

# Copy FEISHU_BOT_WEBHOOK from humanoid-tech-ops .env
gh secret set FEISHU_BOT_WEBHOOK --body "$(grep FEISHU_BOT_WEBHOOK /Users/zhangrui1/humanoid-tech-ops/.env | cut -d= -f2-)"
```

**Step 3: Local smoke test with real .env**

Copy the relevant values into `.env`:
```bash
cp /Users/zhangrui1/humanoid-tech-ops/.env .env
# Edit .env to remove Bitable-specific vars, keep LLM_ and FEISHU_BOT_WEBHOOK
```

Run locally (no Feishu push — dry run):
```bash
FEISHU_BOT_WEBHOOK=https://httpbin.org/post ept uv run python -m entrypoints.collect_daily
```

Expected output (check logs):
```
INFO collect_daily: total raw items: 200+
INFO collect_daily: after filter: 60+
INFO collect_daily: after dedup: 40+
INFO collect_daily: summarized 35 items
INFO collect_daily: report saved: reports/2026-06-29.md
INFO collect_daily: feishu push complete
```

**Step 4: Verify report file**

```bash
cat reports/2026-06-29.md | head -40
```

Expected: Markdown with sections (🚨 / ⭐ / 🇨🇳 / 🌍), real news titles, 100-word summaries.

**Step 5: Manual trigger on GitHub Actions**

```bash
gh workflow run collect-daily.yml
gh run watch   # watch live log
```

Expected: job completes in ~5 min, report committed to repo, Feishu card received in group.

**Step 6: Verify RSS.app setup for Russia/Middle East feeds (post-MVP)**

After smoke test passes, create RSS.app feeds for:
- `drivearabia.com` → update `MIDDLE_EAST_FEEDS` in `feeds.py`
- `drom.ru/news` → update `RUSSIA_FEEDS` in `feeds.py`
- `arabwheels.ae` → update `MIDDLE_EAST_FEEDS`

Then commit updated `feeds.py`.

**Step 7: Final full test + lint**

```bash
ept uv run pytest -v
ept uv run ruff check src/ entrypoints/ tests/
```

Expected: all pass, no lint errors.

**Step 8: Final commit**

```bash
git add -A
git commit -m "feat: automotive-news-daily MVP complete"
git push
```

---

## Environment Variables Reference

| Variable | Source | Description |
|----------|--------|-------------|
| `LLM_API_KEY` | Copy from humanoid-tech-ops | 智谱 GLM API key |
| `LLM_BASE_URL` | Hardcoded in workflow | `https://open.bigmodel.cn/api/paas/v4/` |
| `LLM_MODEL` | Hardcoded in workflow | `glm-4-flash` |
| `FEISHU_BOT_WEBHOOK` | Copy from humanoid-tech-ops | Group bot webhook URL |

## Feed Verification Checklist

After running the first smoke test, check logs for any feeds that returned 0 items or errors. Common issues:

| Feed | Likely issue | Fix |
|------|-------------|-----|
| SAMR | XML schema mismatch | Update `samr.py` element tags |
| EU RAPEX | URL changed | Check `ec.europa.eu/safety-gate` for new URL |
| Chinese sites (新浪汽车) | RSS not available | Remove or replace with RSS.app |
| Russia/Middle East | No native RSS | Create RSS.app feeds, update `feeds.py` |
| NHTSA | RSS URL changed | Check `nhtsa.gov/rss-feeds` for new URL |
