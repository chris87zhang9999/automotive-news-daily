from src.schemas import NewsItem
from src.filter import is_automotive, assign_priority, filter_and_prioritize

def _item(title: str, raw_text: str = "") -> NewsItem:
    return NewsItem(url="https://x.com", title=title, source_name="s",
                    region="r", published_at="", raw_text=raw_text)

def test_is_automotive_english():
    assert is_automotive(_item("BYD launches new electric vehicle in Germany"))

def test_is_automotive_chinese():
    assert is_automotive(_item("比亚迪发布新款电动车"))

def test_is_automotive_russian():
    assert is_automotive(_item("BYD открывает завод в России", "новый автомобиль"))

def test_is_automotive_rejects_unrelated():
    assert not is_automotive(_item("Apple launches new iPhone 17"))

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

def test_filter_removes_non_automotive():
    items = [
        _item("Tesla model Y price cut"),
        _item("Taylor Swift new album"),
        _item("AITO M9 sales record"),
    ]
    result = filter_and_prioritize(items)
    assert len(result) == 2

def test_smart_car_generic_phrase_not_branded_smart():
    # "smart car" as generic phrase must not assign Smart brand
    item = assign_priority(_item(
        "How to Buy or Lease a New Car",
        "A smart car buyer always compares prices before signing."
    ))
    assert item.brand != "Smart"

def test_smart_automobile_matches():
    item = assign_priority(_item("Smart Automobile unveils new model"))
    assert item.brand == "Smart"

def test_mg_img_tag_false_positive():
    # <img> in raw HTML must not trigger MG brand match
    assert not is_automotive(_item(
        "Apple launches new iPhone",
        '<img src="photo.jpg"> A great smartphone.'
    ))

def test_filter_preserves_order_by_priority():
    items = [
        _item("Toyota new model"),
        _item("Li Auto recall notice"),
        _item("BYD enters Europe"),
    ]
    result = filter_and_prioritize(items)
    assert result[0].priority == "P0"
    assert result[1].priority == "P2"
    assert result[2].priority == "P3"
