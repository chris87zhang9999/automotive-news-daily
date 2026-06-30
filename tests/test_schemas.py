from src.schemas import NewsItem, url_hash

def test_url_hash_stable():
    assert url_hash("https://example.com/a") == url_hash("https://example.com/a")

def test_url_hash_different():
    assert url_hash("https://a.com") != url_hash("https://b.com")

def test_news_item_hash_id():
    item = NewsItem(url="https://x.com/1", title="T", source_name="s",
                    region="西欧", published_at="", raw_text="")
    assert len(item.hash_id) == 16

def test_news_item_defaults():
    item = NewsItem(url="u", title="t", source_name="s",
                    region="中国", published_at="", raw_text="")
    assert item.priority == "P3"
    assert item.brand == ""
    assert item.summary == ""

def test_news_item_has_score_and_note():
    item = NewsItem(url="https://x.com", title="t", source_name="s",
                    region="r", published_at="", raw_text="")
    assert item.score == -1        # -1 = not yet evaluated
    assert item.note == ""
    assert item.market == ""
