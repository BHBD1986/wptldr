import httpx

from backend.config import settings

_HEADERS = {"User-Agent": "WP-TLDR/0.1 (personal research)"}


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.WP_API_BASE, headers=_HEADERS, timeout=15)


def fetch_category_map() -> dict[int, str]:
    with _client() as c:
        resp = c.get("/categories", params={"per_page": 100, "_fields": "id,slug"})
        resp.raise_for_status()
        return {cat["id"]: cat["slug"] for cat in resp.json()}


def fetch_posts(start: str, end: str, per_page: int = 100):
    with _client() as c:
        page = 1
        while True:
            params = {
                "after": f"{start}T00:00:00",
                "before": f"{end}T23:59:59",
                "per_page": per_page,
                "page": page,
                "_fields": "id,date,link,slug,title,excerpt,content,categories",
            }
            resp = c.get("/posts", params=params)
            resp.raise_for_status()
            yield from resp.json()
            total_pages = int(resp.headers.get("X-WP-TotalPages", 0))
            if page >= total_pages:
                break
            page += 1
