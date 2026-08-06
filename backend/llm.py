import datetime as _dt

import httpx
from openai import OpenAI

from backend.config import settings

_LICENSE_MSG = (
    "Your WP TLDR license has expired. "
    "The AI summaries and topic briefs are no longer available — "
    "please contact your instructor for a renewal."
)


def license_expired() -> bool:
    try:
        expiry = _dt.date.fromisoformat(settings.LICENSE_EXPIRY)
    except (ValueError, TypeError):
        return False
    return _dt.date.today() > expiry


def chat(user: str, system: str = "", json_mode: bool = True) -> str:
    if license_expired():
        raise RuntimeError(_LICENSE_MSG)

    client = OpenAI(
        base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY, timeout=120
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs = {"model": settings.LLM_MODEL, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def model_name() -> str:
    return settings.LLM_MODEL


if __name__ == "__main__":
    import sys

    if "--check" in sys.argv:
        if not settings.LLM_API_KEY:
            print("No LLM_API_KEY configured (set it in .env or add api_key.txt)")
            sys.exit(1)
        try:
            r = httpx.get(
                f"{settings.LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            models = (
                data.get("data", data) if isinstance(data, dict) else data
            )
            print(f"Connected — {len(models)} models available")
        except Exception as e:
            print(f"LLM check failed: {e}")
            sys.exit(1)
