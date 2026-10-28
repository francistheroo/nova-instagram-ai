# NOVA — Instagram AI starter

NOVA is a starter backend for a transparent AI character that chats in Manglish, Malayalam script, and English.

## What this starter does
- Provides a FastAPI health check and a `/preview-reply` endpoint.
- Includes NOVA's personality and language instructions.
- Supports an optional OpenAI-compatible AI endpoint configured through environment variables.
- Keeps Instagram integration disabled until you create a Meta developer app and authorize your own eligible account.

## Important limitations
This is a starter project, not a deployed or connected Instagram account. It does not automatically publish, send messages, create Notes with music, or follow accounts yet. Meta's official APIs do not expose every Instagram-app feature; general follow/unfollow automation is not supported by the official API.

## Run locally
1. Install Python 3.11 or newer.
2. Copy `.env.example` to `.env` and optionally configure an AI provider.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Open `http://127.0.0.1:8000/health`.

## AI provider setup
Set `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` for a compatible API provider. Use only a provider's official endpoint and follow its free-tier limits. If these are blank, `/preview-reply` returns a safe fallback showing the configured personality prompt.

Never put API keys or Meta access tokens in source code or share them in chat.

## Online deployment
Deploy this folder to a Python host that supports FastAPI. Add environment variables in the host's private environment settings. Free hosts may sleep when idle, and their local disk may not persist. Use a persistent database and an external scheduler for reliable autonomous operation.

## Next steps for official Instagram connection
1. Confirm the Instagram account is Creator or Business, if required by the selected API route.
2. Create an app in Meta for Developers.
3. Configure Instagram Login and request only the permissions needed.
4. Complete any required app review and business verification.
5. Store tokens securely in environment secrets or a secret manager.
6. Implement only supported publishing, comment, messaging, and insights endpoints.
7. Test with drafts and a test account before enabling autonomous publishing.
