"""Protected admin settings API for NOVA."""
import hmac
import json
import os
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["NOVA admin"])
PROVIDERS = {"gemini", "groq", "huggingface", "legacy"}


def _db_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is required for persistent admin settings.")
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


def initialize_admin_schema():
    with psycopg.connect(_db_url(), connect_timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nova_admin_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def require_admin(authorization: Optional[str] = Header(default=None)):
    expected_user = os.getenv("NOVA_ADMIN_USERNAME", "")
    expected_password = os.getenv("NOVA_ADMIN_PASSWORD", "")
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="Set NOVA_ADMIN_USERNAME and NOVA_ADMIN_PASSWORD in Render.")
    import base64
    try:
        scheme, encoded = (authorization or "").split(" ", 1)
        username, password = base64.b64decode(encoded).decode().split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="Admin sign-in required.", headers={"WWW-Authenticate": "Basic"}) from None
    if scheme.lower() != "basic" or not (
        hmac.compare_digest(username, expected_user)
        and hmac.compare_digest(password, expected_password)
    ):
        raise HTTPException(status_code=401, detail="Invalid admin credentials.", headers={"WWW-Authenticate": "Basic"})
    return True


def read_settings():
    result = {
        "provider_order": [p.strip() for p in os.getenv("AI_PROVIDER_ORDER", "gemini,groq,huggingface,legacy").split(",") if p.strip()],
        "master_enabled": False,
        "max_posts_per_day": 3,
        "max_stories_per_day": 3,
        "direct_publish_enabled": False,
        "post_times": ["09:00"],
        "story_times": ["13:00"],
    }
    try:
        with psycopg.connect(_db_url(), connect_timeout=10) as conn:
            for key, value in conn.execute("SELECT setting_key, setting_value FROM nova_admin_settings").fetchall():
                result[key] = value
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Admin storage unavailable. Run python -m app.init_oauth_db.") from None
    return result


class SettingsUpdate(BaseModel):
    master_enabled: bool = False
    provider_order: list[str] = Field(min_length=1, max_length=4)
    max_posts_per_day: int = Field(ge=0, le=20)
    max_stories_per_day: int = Field(ge=0, le=20)
    direct_publish_enabled: bool
    post_times: list[str] = Field(default_factory=lambda: ["09:00"], max_length=10)
    story_times: list[str] = Field(default_factory=lambda: ["13:00"], max_length=10)


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(_: bool = Depends(require_admin)):
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA Admin</title>
<style>
body{margin:0;background:#050505;color:#eee;font:15px system-ui}main{max-width:720px;margin:32px auto;padding:18px}.card{background:#111;border:1px solid #292929;border-radius:16px;padding:20px;margin:14px 0}h1{color:#8cffc7}label{display:block;margin:12px 0 5px}input{background:#080808;color:white;border:1px solid #444;border-radius:9px;padding:11px;width:100%;box-sizing:border-box}input[type=checkbox]{width:auto}button{background:#8cffc7;color:#06110a;border:0;border-radius:10px;padding:12px 18px;font-weight:bold;width:100%}.hint,#status{color:#aaa;font-size:13px}
</style></head><body><main><h1>NOVA Admin</h1><p class="hint">Server-side settings. API keys remain in Render and are never displayed.</p>
<div class="card"><h2>Master switch</h2><label><input id="master" type="checkbox"> NOVA AI ON — allow AI features and scheduled publishing</label><p class="hint">OFF disables AI generation and scheduled publishing immediately. Admin settings remain accessible.</p></div>
<div class="card"><h2>AI provider fallback order</h2><label for="providers">Provider order</label><input id="providers" placeholder="gemini,groq,huggingface,legacy"><p class="hint">Supported: gemini, groq, huggingface, legacy</p></div>
<div class="card"><h2>Daily publishing limits</h2><label for="posts">AI photo posts per day</label><input id="posts" type="number" min="0" max="20"><label for="stories">Stories per day</label><input id="stories" type="number" min="0" max="20"></div>
<div class="card"><h2>Automatic schedule</h2><label for="posttimes">Photo post times (24-hour, comma-separated)</label><input id="posttimes" placeholder="09:00,18:00"><label for="storytimes">Story times (24-hour, comma-separated)</label><input id="storytimes" placeholder="13:00"><p class="hint">Times use NOVA_TIMEZONE; default Asia/Kolkata.</p></div>
<div class="card"><h2>Direct publishing</h2><label><input id="direct" type="checkbox"> Enable direct publishing without per-post approval</label><p class="hint">Once enabled and configured, NOVA creates and publishes at the schedule times without a per-post button. Requires NOVA_SCHEDULER_ENABLED and INSTAGRAM_AUTOMATION_ENABLED on the server.</p></div>
<button id="save">Save settings</button><p id="status" role="status"></p></main>
<script>
async function api(method,body){const r=await fetch('/admin/api/settings',{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}
const status=document.getElementById('status');
async function load(){try{const s=await api('GET');document.getElementById('master').checked=s.master_enabled;document.getElementById('providers').value=s.provider_order.join(',');document.getElementById('posts').value=s.max_posts_per_day;document.getElementById('stories').value=s.max_stories_per_day;document.getElementById('direct').checked=s.direct_publish_enabled;document.getElementById('posttimes').value=s.post_times.join(',');document.getElementById('storytimes').value=s.story_times.join(',');status.textContent='Settings loaded.'}catch(e){status.textContent=e.message}}
document.getElementById('save').onclick=async()=>{try{const s=await api('PUT',{master_enabled:document.getElementById('master').checked,provider_order:document.getElementById('providers').value.split(',').map(x=>x.trim().toLowerCase()).filter(Boolean),max_posts_per_day:Number(document.getElementById('posts').value),max_stories_per_day:Number(document.getElementById('stories').value),direct_publish_enabled:document.getElementById('direct').checked,post_times:document.getElementById('posttimes').value.split(',').map(x=>x.trim()).filter(Boolean),story_times:document.getElementById('storytimes').value.split(',').map(x=>x.trim()).filter(Boolean)});status.textContent='Settings saved. Fallback: '+s.provider_order.join(' → ')}catch(e){status.textContent=e.message}};
load();
</script></body></html>""")


@router.get("/admin/api/settings")
async def get_settings(_: bool = Depends(require_admin)):
    return read_settings()


@router.put("/admin/api/settings")
async def put_settings(body: SettingsUpdate, _: bool = Depends(require_admin)):
    import re
    if any(not re.fullmatch(r"\d{2}:\d{2}", slot) or int(slot[:2]) > 23 or int(slot[3:]) > 59 for slot in body.post_times + body.story_times):
        raise HTTPException(status_code=422, detail="Schedule times must use HH:MM in 24-hour format.")
    if len(set(body.provider_order)) != len(body.provider_order) or any(p not in PROVIDERS for p in body.provider_order):
        raise HTTPException(status_code=422, detail="Use unique supported provider names.")
    values = body.model_dump()
    try:
        with psycopg.connect(_db_url(), connect_timeout=10) as conn:
            for key, value in values.items():
                conn.execute(
                    """INSERT INTO nova_admin_settings (setting_key, setting_value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (setting_key) DO UPDATE SET
                    setting_value=EXCLUDED.setting_value, updated_at=NOW()""",
                    (key, json.dumps(value)),
                )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save settings. Check PostgreSQL.") from None
    return values
