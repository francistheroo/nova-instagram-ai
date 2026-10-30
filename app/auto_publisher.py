"""Durable, schedule-driven AI photo and Story publisher.

Runs only when both NOVA_SCHEDULER_ENABLED and INSTAGRAM_AUTOMATION_ENABLED
are true and the protected admin setting direct_publish_enabled is enabled.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import psycopg

from app.ai_router import AIProviderUnavailable, chat_completion


def _db_url():
    value = os.getenv("DATABASE_URL", "").strip()
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://"):]
    return value


def initialize_scheduler_schema():
    url = _db_url()
    if not url:
        return
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nova_auto_publish_runs (
                id BIGSERIAL PRIMARY KEY,
                local_date DATE NOT NULL,
                content_type TEXT NOT NULL CHECK (content_type IN ('post','story')),
                slot TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('processing','published','failed')),
                media_id TEXT,
                error_code TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (local_date, content_type, slot)
            )
        """)


def _settings():
    with psycopg.connect(_db_url(), connect_timeout=10) as conn:
        rows = conn.execute("SELECT setting_key, setting_value FROM nova_admin_settings").fetchall()
    result = {}
    for key, value in rows:
        result[key] = value
    return result


def _claim_slot(local_date, kind, slot, daily_limit):
    with psycopg.connect(_db_url(), connect_timeout=10) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM nova_auto_publish_runs WHERE local_date=%s AND content_type=%s AND status='published'",
            (local_date, kind),
        ).fetchone()[0]
        if count >= daily_limit:
            return False
        row = conn.execute(
            """INSERT INTO nova_auto_publish_runs (local_date,content_type,slot,status)
               VALUES (%s,%s,%s,'processing')
               ON CONFLICT (local_date,content_type,slot) DO NOTHING
               RETURNING id""",
            (local_date, kind, slot),
        ).fetchone()
        return row[0] if row else False


def _finish(run_id, status, media_id=None, error_code=None):
    with psycopg.connect(_db_url(), connect_timeout=10) as conn:
        conn.execute(
            """UPDATE nova_auto_publish_runs SET status=%s,media_id=%s,error_code=%s,
               updated_at=NOW() WHERE id=%s""",
            (status, media_id, error_code, run_id),
        )


async def _generate_and_publish(kind, meta_request, instagram_config):
    from app.personality import NOVA_SYSTEM_PROMPT

    prompt_request = (
        "Create an original, safe, family-friendly Instagram visual concept and caption. "
        "Return JSON only with keys image_prompt and caption. image_prompt must describe "
        "one coherent square or portrait image. Caption must be concise, original, and "
        "not claim unverified facts. Content type: " + kind
    )
    raw, _, _ = await chat_completion(
        [{"role": "system", "content": NOVA_SYSTEM_PROMPT},
         {"role": "user", "content": prompt_request}],
        temperature=0.8,
    )
    try:
        brief = json.loads(raw)
        image_prompt = brief["image_prompt"]
        caption = brief["caption"]
        if not isinstance(image_prompt, str) or not isinstance(caption, str):
            raise ValueError("invalid content fields")
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("ai_content_format_invalid") from None

    base = os.getenv("IMAGE_API_BASE_URL", "").rstrip("/")
    key = os.getenv("IMAGE_API_KEY", "")
    model = os.getenv("IMAGE_MODEL", "")
    if not (base and key and model):
        raise RuntimeError("image_provider_not_configured")
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{base}/images/generations",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "prompt": image_prompt, "size": "1024x1024", "n": 1},
        )
    if response.is_error:
        raise RuntimeError("image_provider_error")
    payload = response.json()
    items = payload.get("data", [])
    image_url = items[0].get("url") if items and isinstance(items[0], dict) else None
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise RuntimeError("image_provider_returned_no_public_url")

    _, user_id, _ = instagram_config()
    media_data = {"image_url": image_url, "caption": caption}
    if kind == "story":
        media_data["media_type"] = "STORIES"
    else:
        media_data["media_type"] = "IMAGE"
    container = await meta_request("POST", f"{user_id}/media", data=media_data)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError("meta_container_creation_failed")
    published = await meta_request(
        "POST", f"{user_id}/media_publish", data={"creation_id": creation_id}
    )
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError("meta_publish_not_confirmed")
    return str(media_id)


async def scheduler_loop(meta_request, instagram_config, stop_event: asyncio.Event):
    """Poll configured local-time slots; DB uniqueness prevents duplicate runs."""
    while not stop_event.is_set():
        try:
            enabled = (
                os.getenv("NOVA_SCHEDULER_ENABLED", "false").lower() == "true"
                and os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() == "true"
            )
            if enabled and _db_url():
                settings = await asyncio.to_thread(_settings)
                if settings.get("direct_publish_enabled") is True:
                    zone = ZoneInfo(os.getenv("NOVA_TIMEZONE", "Asia/Kolkata"))
                    now = datetime.now(zone)
                    slot = now.strftime("%H:%M")
                    schedules = (
                        ("post", settings.get("post_times", ["09:00"]), int(settings.get("max_posts_per_day", 3))),
                        ("story", settings.get("story_times", ["13:00"]), int(settings.get("max_stories_per_day", 3))),
                    )
                    for kind, times, cap in schedules:
                        if slot not in times or cap <= 0:
                            continue
                        run_id = await asyncio.to_thread(_claim_slot, now.date(), kind, slot, cap)
                        if not run_id:
                            continue
                        try:
                            media_id = await _generate_and_publish(kind, meta_request, instagram_config)
                            await asyncio.to_thread(_finish, run_id, "published", media_id, None)
                        except AIProviderUnavailable:
                            await asyncio.to_thread(_finish, run_id, "failed", None, "ai_provider_unavailable")
                        except Exception as exc:
                            code = str(exc)[:80] if isinstance(exc, RuntimeError) else "publish_failed"
                            await asyncio.to_thread(_finish, run_id, "failed", None, code)
        except Exception:
            # A transient database/config error must not crash the FastAPI server.
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass
