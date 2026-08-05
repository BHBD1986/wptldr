from pydantic import BaseModel


class TopicCount(BaseModel):
    topic: str
    count: int


class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    section: str
    published_at: str
    tldr: str | None = None
    topics: list[str]


class ArticleDetail(ArticleOut):
    excerpt: str = ""
    content_text: str = ""
    key_points: list[str] = []
    why_it_matters: str | None = None
    related: list[ArticleOut] = []
