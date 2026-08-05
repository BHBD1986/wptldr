import httpx
from openai import OpenAI

from backend.config import settings


def chat(user: str, system: str = "", json_mode: bool = True) -> str:
    if not settings.LLM_API_KEY:
        from backend.local_llm import generate

        return generate(user, system=system, json_mode=json_mode)

    client = OpenAI(
        base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY, timeout=60
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
    if settings.LLM_API_KEY:
        return settings.LLM_MODEL
    from backend.local_llm import model_name as _local_name

    return _local_name()


if __name__ == "__main__":
    import sys

    if "--check" in sys.argv:
        if not settings.LLM_API_KEY:
            from backend.local_llm import model_available, model_name

            print(f"LLM_API_KEY not set — using local model: {model_name()}")
            if not model_available():
                print("Model file missing — will download on first use")
            sys.exit(0)
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
