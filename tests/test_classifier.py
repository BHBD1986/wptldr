from backend.classifier import classify


def test_livestock_category():
    result = classify(["livestock"], "pigs are healthy")
    topics = [t for t, _ in result]
    assert topics[0] == "livestock"


def test_agtech_keywords_and_category():
    result = classify(["machinery"], "the autonomous drone sprayer uses AI for precision")
    topics = [t for t, _ in result]
    assert topics[0] == "agtech"


def test_politics_keywords_and_category():
    result = classify(
        ["news"], "the minister announced a new tariff legislation in ottawa"
    )
    topics = [t for t, _ in result]
    assert "politics" in topics


def test_markets_keywords_only():
    result = classify([], "canola futures rallied with cash price up 2 dollars per bushel")
    topics = [t for t, _ in result]
    assert "markets" in topics
