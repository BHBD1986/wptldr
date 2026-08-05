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


def test_run_assigns_unclassified_to_unmatched(monkeypatch, tmp_path):
    from backend.config import settings
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    from backend.db import init_db, get_conn
    init_db()

    conn = get_conn()
    conn.execute(
        "INSERT INTO articles (id, wp_id, title, url, section, published_at, categories, content_text, excerpt, word_count, ingested_at) "
        "VALUES (1, 1, 'Road trip notes', 'http://x.com/1', 'farm-family', '2026-07-01T00:00:00', "
        "'[\"farm-family\"]', 'a drive through the countryside', 'exc', 10, 'now')"
    )
    conn.commit()
    conn.close()

    from backend import classify as classify_module
    classify_module.run()

    conn = get_conn()
    rows = conn.execute("SELECT topic FROM article_topics WHERE article_id=1").fetchall()
    conn.close()
    assert [r["topic"] for r in rows] == ["unclassified"]
