import json
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db import get_conn
from backend.llm import chat, model_name
from backend.schemas import ArticleDetail, ArticleOut, TopicCount
from backend.text_utils import truncate
from backend.update_state import get_state as _get_state
from backend.update_state import start_update as _start_update
from backend.digest_state import get_state as _get_digest_state
from backend.digest_state import start_digest as _start_digest
from backend.runtime_paths import frontend_dir

app = FastAPI(title="WP TLDR Explorer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────────────────

def _conn():
    return get_conn()


def _topics_for(article_id: int) -> list[str]:
    rows = _conn().execute(
        "SELECT topic FROM article_topics WHERE article_id=?", (article_id,)
    ).fetchall()
    return [r["topic"] for r in rows]


def _article_out(row, tldr=None, topics=None) -> ArticleOut:
    return ArticleOut(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        section=row["section"],
        published_at=row["published_at"],
        tldr=tldr or None,
        topics=topics or _topics_for(row["id"]),
    )


# ── health ───────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"ok": True}


# ── update pipeline ─────────────────────────────────────────────────

@app.post("/api/update")
def trigger_update(topic: str = Query(None)):
    state = _get_state()
    if state["running"]:
        raise HTTPException(409, detail="Update already running")
    ok = _start_update(topic)
    return {"started": ok}


@app.get("/api/update/status")
def update_status():
    return _get_state()


# ── import data ───────────────────────────────────────────────────────

@app.post("/api/import")
async def import_db(file: UploadFile = File(...)):
    """Replace the app's database with an uploaded WP TLDR .db file.

    The current database is backed up first, then the uploaded file is
    swapped in. The web UI reloads afterwards.
    """
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not file.filename or not file.filename.lower().endswith(".db"):
        raise HTTPException(400, detail="Please upload a .db file")

    fd = None
    tmp_path = None
    try:
        import os
        import sqlite3

        fd, tmp_name = tempfile.mkstemp(suffix=".db")
        with os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(file.file, out)
        tmp_path = Path(tmp_name)

        try:
            conn = sqlite3.connect(str(tmp_path))
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
        except sqlite3.Error:
            tables = set()
        if not {"articles", "summaries"}.issubset(tables):
            raise HTTPException(
                400,
                detail="That file isn't a WP TLDR database (missing articles/summaries tables)",
            )

        if db_path.exists():
            shutil.copy2(db_path, db_path.with_suffix(".db.bak"))

        for sidecar in (".db-wal", ".db-shm"):
            p = Path(str(db_path) + sidecar)
            if p.exists():
                p.unlink()

        shutil.copy2(tmp_path, db_path)

        counts = _conn().execute(
            "SELECT (SELECT COUNT(*) FROM articles), (SELECT COUNT(*) FROM summaries)"
        ).fetchone()
        return {
            "ok": True,
            "articles": counts[0],
            "summarized": counts[1],
        }
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ── digest ────────────────────────────────────────────────────────────

@app.post("/api/digest")
def create_digest(
    topic: str = "agtech",
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
    force: bool = False,
):
    from_ = from_ or settings.DEFAULT_START
    to = to or date.today().isoformat()
    started = _start_digest(topic, from_, to, force=force)
    if not started:
        raise HTTPException(409, detail="Digest already running")
    return {"started": True}


@app.get("/api/digest/status")
def digest_status():
    return _get_digest_state()


@app.get("/api/digest")
def get_digest(
    topic: str = "agtech",
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
):
    from_ = from_ or settings.DEFAULT_START
    to = to or date.today().isoformat()
    conn = _conn()
    row = conn.execute(
        "SELECT content, item_count FROM digests WHERE topic=? AND from_date=? AND to_date=?",
        (topic, from_, to),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, detail="No cached digest for this topic and date range")
    return {"digest": json.loads(row["content"]), "item_count": row["item_count"], "cached": True}


# ── topics + stats ───────────────────────────────────────────────────

@app.get("/api/topics")
def list_topics(from_: str = Query(None, alias="from"), to: str = Query(None)):
    conn = _conn()
    from_ = from_ or settings.DEFAULT_START
    to = to or date.today().isoformat()
    rows = conn.execute(
        """SELECT t.topic, COUNT(*) as cnt
           FROM article_topics t
           JOIN articles a ON a.id = t.article_id
           WHERE a.published_at BETWEEN ? AND ?
           GROUP BY t.topic
           ORDER BY cnt DESC""",
        (from_, to),
    ).fetchall()
    topics_set = {r["topic"] for r in rows}
    result = [TopicCount(topic=r["topic"], count=r["cnt"]) for r in rows]
    for t in settings.TOPICS:
        if t not in topics_set:
            result.append(TopicCount(topic=t, count=0))
    return result


@app.get("/api/stats")
def stats():
    conn = _conn()
    articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    summarized = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
    topic_count = conn.execute("SELECT COUNT(DISTINCT topic) FROM article_topics").fetchone()[0]
    dates = conn.execute(
        "SELECT MIN(published_at), MAX(published_at) FROM articles"
    ).fetchone()
    return {
        "articles": articles,
        "summarized": summarized,
        "topics": topic_count,
        "date_min": dates[0],
        "date_max": dates[1],
    }


# ── article list ─────────────────────────────────────────────────────

@app.get("/api/articles")
def list_articles(
    topic: str = "agtech",
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = _conn()
    from_ = from_ or settings.DEFAULT_START
    to = to or date.today().isoformat()

    base = """FROM articles a
              JOIN article_topics t ON a.id = t.article_id
              LEFT JOIN summaries s ON a.id = s.article_id"""
    where = ["t.topic = ?", "a.published_at BETWEEN ? AND ?"]
    params: list = [topic, from_, to]

    if q:
        where.append("a.title LIKE ?")
        params.append(f"%{q}%")

    where_clause = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) {base} WHERE {where_clause}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"""SELECT a.*, s.tldr {base} WHERE {where_clause}
            ORDER BY a.published_at DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()

    items = []
    for r in rows:
        items.append(_article_out(r, tldr=r["tldr"]))

    return {"items": items, "total": total, "page": page, "pages": max(1, -(-total // page_size))}


# ── article detail ───────────────────────────────────────────────────

@app.get("/api/articles/{article_id}")
def article_detail(article_id: int):
    conn = _conn()
    row = conn.execute(
        """SELECT a.*, s.tldr, s.key_points, s.why_it_matters
           FROM articles a
           LEFT JOIN summaries s ON a.id = s.article_id
           WHERE a.id=?""",
        (article_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Article not found")

    key_points = []
    if row["key_points"]:
        key_points = json.loads(row["key_points"])

    topics = _topics_for(article_id)
    related = []
    if topics:
        related_rows = conn.execute(
            """SELECT DISTINCT a.*, s.tldr
               FROM articles a
               JOIN article_topics t ON a.id = t.article_id
               LEFT JOIN summaries s ON a.id = s.article_id
               WHERE t.topic IN ({})
                 AND a.id != ?
               ORDER BY ABS(julianday(a.published_at) - julianday(?))
               LIMIT 6""".format(",".join("?" * len(topics))),
            topics + [article_id] + [row["published_at"]],
        ).fetchall()
        related = [_article_out(r, tldr=r["tldr"]) for r in related_rows]

    return ArticleDetail(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        section=row["section"],
        published_at=row["published_at"],
        excerpt=row["excerpt"] or "",
        content_text=row["content_text"] or "",
        tldr=row["tldr"] or None,
        topics=topics,
        key_points=key_points,
        why_it_matters=row["why_it_matters"] or None,
        related=related,
    )


# ── expand drill-down ────────────────────────────────────────────────

@app.post("/api/articles/{article_id}/expand")
def expand_article(article_id: int):
    conn = _conn()

    cached = conn.execute(
        "SELECT content FROM expansions WHERE article_id=?", (article_id,)
    ).fetchone()
    if cached:
        return {"content": json.loads(cached["content"]), "cached": True}

    row = conn.execute(
        "SELECT title, content_text FROM articles WHERE id=?", (article_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Article not found")

    try:
        raw = chat(
            user=f"Title: {row['title']}\n\nText:\n{truncate(row['content_text'], 6000)}\n\n"
                 'Return JSON: {{"deeper_context": "background details", '
                 '"key_actors": ["people/organizations"], '
                 '"outlook": "what happens next"}}',
            system="Agriculture analyst. Output ONLY valid JSON.",
        )
        data = json.loads(raw)
    except Exception as e:
        if "license" in str(e).lower():
            raise HTTPException(503, detail=str(e))
        raise HTTPException(503, detail="Summarization backend unreachable")

    conn.execute(
        "INSERT OR REPLACE INTO expansions VALUES (?,?,?,?)",
        (article_id, json.dumps(data), model_name(), datetime.utcnow().isoformat()),
    )
    conn.commit()

    return {"content": data, "cached": False}


# ── static frontend ──────────────────────────────────────────────────

static_dir = frontend_dir()
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
