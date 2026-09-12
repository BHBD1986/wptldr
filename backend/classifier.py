import re

CATEGORY_RULES: dict[str, set[str]] = {
    "livestock": {
        "livestock", "beef-cattle", "dairy", "hog-hub", "finishing",
        "genetics", "sows-and-farrowing", "transportation", "weaners",
        "cattle-call",
    },
    "crops": {
        "crops", "canola", "cereals", "forage-and-crops",
        "herbicides-weeds", "seed-science", "weed-resistance",
        "biologicals", "in-season", "pre-season", "production",
        "sustainability", "weather",
    },
    "markets": {
        "markets", "grain-markets", "am-market-reports", "ag-finance",
        "markets-matters", "strategies",
    },
    "agtech": {"technology", "machinery", "equipment", "farm-it-manitoba"},
}

POLITICS_CATEGORIES: set[str] = {
    "tariffs", "nafta", "news", "current-affairs", "national-news",
    "international-news", "advocacy", "reuters",
}

KEYWORD_RULES: dict[str, str] = {
    "agtech": (
        r"precision|autonomous|drone|sensor|robot|"
        r"artificial intelligence|\bAI\b|machine learning|"
        r"satellite|variable rate|agtech|automation|telemetry|"
        r"\bgps\b|software|digital|connectivity|broadband|"
        r"autosteer|yield monitor|\bndvi\b|\biot\b|algorithm|"
        r"data-driven|smart farm|remote sensing"
    ),
    "politics": (
        r"tariff|minister|parliament|ottawa|senate|legislat|regulat|"
        r"election|trade (?:deal|agreement|war)|cusma|wto|cfia|"
        r"proclamation|subsidy|carbon tax|supply management|sanction|"
        r"premier|federal government|provincial government|lobby|"
        r"policy|bill c-\d"
    ),
    "markets": (
        r"futures|cash price|basis|bushel|per tonne|export sales|"
        r"contract high|loonie|selloff|rally|commodity|hedge|"
        r"per bushel|per pound|market price"
    ),
    "crops": (
        r"yield|seeding|harvest|germination|herbicide|fungicide|agronom|"
        r"drought|frost|fusarium|canola|wheat|barley|pulse|soybean|"
        r"flax|oats?\b|lentil|aphid|grasshopper|topsoil|"
        r"crop rotation|nitrogen|fertilizer|spray|moisture|rainfall"
    ),
    "livestock": (
        r"cattle|hog|swine|piglet|dairy|beef|feedlot|veterinar|herd|"
        r"bovine|poultry|antibiotic|\bfeed\b|ration|manure|calving|"
        r"weaning|\bbull\b|\bcow\b|\bcalf\b|flock|\beggs?\b"
    ),
}


def classify(categories: list[str], text: str) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    lower_text = text.lower()

    for topic, cat_set in CATEGORY_RULES.items():
        match_count = sum(1 for c in categories if c in cat_set)
        if match_count:
            scores[topic] = scores.get(topic, 0) + match_count * 3

    politics_cat_count = sum(1 for c in categories if c in POLITICS_CATEGORIES)
    if politics_cat_count:
        scores["politics"] = scores.get("politics", 0) + politics_cat_count

    for topic, pattern in KEYWORD_RULES.items():
        hits = len(re.findall(pattern, lower_text))
        if hits:
            scores[topic] = scores.get(topic, 0) + min(hits, 4)

    result = [(t, s) for t, s in scores.items() if s >= 2]
    result.sort(key=lambda x: -x[1])
    return result
