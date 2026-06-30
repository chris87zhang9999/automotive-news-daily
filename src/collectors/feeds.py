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
    "https://carnewschina.com/feed/",
    "https://auto.gasgoo.com/RSS/automotive_news.xml",
]

# ── China / Chinese Brands ─────────────────────────────────────────────────
CHINA_FEEDS = [
    "https://auto.sina.com.cn/rss.xml",
    "https://www.autohome.com.cn/rss/news.xml",
    "https://36kr.com/feed",
    "https://www.gasgoo.com/RSS/automotive_news.xml",
]

# ── Europe ─────────────────────────────────────────────────────────────────
EUROPE_FEEDS = [
    "https://www.auto-motor-und-sport.de/rss/",
    "https://www.autobild.de/rss/",
    "https://www.heise.de/autos/rss/",
    "https://de.motor1.com/rss/",
    "https://www.autocar.co.uk/rss",
    "https://www.autoexpress.co.uk/feed",
    "https://www.drivingelectric.com/feed",
    "https://www.turbo.fr/feed/",
    "https://it.motor1.com/rss/",
]

# ── Russia / CIS ──────────────────────────────────────────────────────────
# These sites don't natively provide RSS — use RSS.app to convert:
#   1. Go to https://rss.app  2. Enter site URL  3. Get generated feed URL
#   Replace placeholder URLs below after generating in RSS.app
RUSSIA_FEEDS = [
    "https://www.drom.ru/news/?rss=1",
    "https://www.kolesa.ru/rss.xml",
    "https://www.kolesa.kz/rss.xml",
    # TODO: replace with RSS.app URLs if above don't work:
    # "https://rss.app/feeds/<id>.xml",  # Drom.ru via RSS.app
    # "https://rss.app/feeds/<id>.xml",  # Kolesa.kz via RSS.app
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
    "https://paultan.org/feed/",
    "https://www.wapcar.my/sitemap/rss.xml",
    "https://www.headlightmag.com/feed/",
    "https://www.bangkokpost.com/rss/data/motoring.xml",
    "https://www.sgcarmart.com/rss/latest_news.xml",
    "https://www.torque.com.sg/feed/",
]

# ── East Asia ─────────────────────────────────────────────────────────────
EAST_ASIA_FEEDS = [
    "https://response.jp/rss/",
    "https://car.watch.impress.co.jp/rss/",
    "https://thekoreancarblog.com/feed/",
]

# ── Quality / Regulatory ──────────────────────────────────────────────────
# Handled by dedicated collectors (samr.py, rapex.py, nhtsa.py)
QUALITY_FEEDS: list[str] = []

ALL_REGIONAL_FEEDS: dict[str, list[str]] = {
    "全球": GLOBAL_FEEDS,
    "中国": CHINA_FEEDS,
    "欧洲": EUROPE_FEEDS,
    "俄罗斯/中亚": RUSSIA_FEEDS,
    "中东": MIDDLE_EAST_FEEDS,
    "东南亚": SEA_FEEDS,
    "东亚": EAST_ASIA_FEEDS,
}
