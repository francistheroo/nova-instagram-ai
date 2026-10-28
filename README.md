# NOVA — Instagram AI starter

NOVA is a FastAPI backend with a Manglish-focused AI reply preview and guarded integration scaffolding.

## Existing and added functionality

- `GET /health`: reports whether provider credentials are configured (not whether they have been verified) and explicitly reports which OAuth, token-refresh, and webhook pieces are not implemented.
- `POST /preview-reply`: generates an AI reply preview; it never sends it to Instagram.
- `GET /instagram/media`: lists accessible professional-account media through Meta's API.
- `GET /instagram/media/{media_id}/comments`: reads comments where permitted.
- `POST /instagram/comments/{comment_id}/reply`: replies to a comment when action endpoints are enabled and the account has permission.
- `POST /instagram/messages/reply`: attempts a supported message reply for an eligible Instagram-scoped recipient ID.
- `POST /instagram/publish-image`: creates and publishes an image container from a publicly reachable image URL.
- `POST /ai/generate-image`: calls a separately configured OpenAI-compatible image-generation API.
- `GET /canva/status`: reports Canva integration implementation status without exposing credentials.
- `GET /canva/designs`: lists the connected user's Canva designs (protected by `X-NOVA-API-Key`).
- `GET /canva/designs/{design_id}/export-formats`: lists supported export formats for a design.
- `POST /canva/exports`: starts a Canva export job for a supported format.
- `GET /canva/exports/{job_id}`: checks an asynchronous export job status.

## Security and setup

1. Configure the official Meta app and authorize the Creator account using the appropriate Instagram Login flow.
2. In Render's private environment settings, set `META_GRAPH_BASE_URL`, `META_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_USER_ID` using values appropriate to that flow. The sample API version may need updating to a currently supported version.
3. Set `NOVA_API_KEY` to a long, random secret. Do not put it in frontend code, public repositories, or chat.
4. Keep `INSTAGRAM_AUTOMATION_ENABLED=false` while testing read-only endpoints. Set it to `true` only after confirming permissions and testing with content you control.
5. Add the key as the `X-NOVA-API-Key` header when calling protected NOVA endpoints. Do not expose this key in a public browser client.
6. Configure `IMAGE_API_BASE_URL`, `IMAGE_API_KEY`, and `IMAGE_MODEL` for an image provider that actually supports the OpenAI-compatible `/images/generations` endpoint. A text-only Groq model is not an image-generation provider.
7. Use a publicly reachable image URL for Instagram publishing. The image-generation endpoint's returned URL may be temporary; reliable publishing usually needs persistent object storage and a public URL.
8. Deploy and check `/health`, then test read-only `/instagram/media` before enabling any write action.

## OAuth security foundation

The `app/oauth_security.py` module provides signed, time-limited state values and Fernet token-encryption helpers. The `app/oauth_store.py` module adds PostgreSQL helpers for encrypted tokens and one-time OAuth state. The `/oauth/instagram/start` and `/oauth/instagram/callback` routes now implement the Instagram Login redirect, browser-bound state validation, server-side code exchange, long-lived token exchange, and encrypted token storage. A protected manual refresh endpoint is available at `POST /oauth/instagram/refresh` using the `X-NOVA-API-Key` header. It refreshes the stored long-lived token when Instagram permits it; expired tokens still require reconnecting. Automatic scheduled refresh, webhook subscription, and production end-to-end verification are still not implemented.

For a deployment using the PostgreSQL store, configure:
- `DATABASE_URL`: private PostgreSQL connection string from the database provider.
- `OAUTH_STATE_SECRET`: a randomly generated secret of at least 32 characters.
- `TOKEN_ENCRYPTION_KEY`: a Fernet key generated with Python's `cryptography` package (keep it outside the database and repository).

Run `python -m app.init_oauth_db` as a deployment/migration step before the app handles OAuth requests. Register the exact `INSTAGRAM_OAUTH_REDIRECT_URI` in the Meta app and keep the client secret server-side. Do not expose decrypted tokens to browser clients or logs. OAuth state must be bound to the initiating browser session in addition to signature/age checks; store and consume its nonce exactly once. Do not enable write actions until the full flow and token renewal are implemented and tested.

To connect: configure the Instagram Login product in the Meta developer dashboard, set `INSTAGRAM_OAUTH_CLIENT_ID`, `INSTAGRAM_OAUTH_CLIENT_SECRET`, `INSTAGRAM_OAUTH_REDIRECT_URI`, `INSTAGRAM_OAUTH_SCOPES`, `OAUTH_STATE_SECRET`, `TOKEN_ENCRYPTION_KEY`, and `DATABASE_URL` in Render; initialize the database schema; then visit `/oauth/instagram/start`. The callback stores the credential server-side and does not return the token to the browser. Use HTTPS and register the exact callback URI.

## Important limitations

- OAuth authorization-code exchange, encrypted token persistence, and a protected manual token refresh route are implemented in code but have not been verified against a real Meta app. Automatic scheduled token refresh, webhook subscription/verification, persistent job queue, Canva design listing/export, and automatic event processing are not implemented. The `/health` response explicitly reports these implementation gaps; a credential being configured does not mean an integration is connected or verified.
- Instagram API permissions and endpoint behavior vary by API version and login flow. App review or access approval may be required.
- Like/unlike automation is not implemented in this starter.
- Instagram Notes creation and attaching music to Notes are not supported by the standard public API. Do not automate them through private endpoints or browser workarounds.
- Reels audio/music publishing requires a separately verified, supported Meta audio workflow and suitable licensing. This starter does not attach music to Reels.
- Message sending is subject to Meta messaging permissions, eligible conversations, and messaging windows. Do not use it for unsolicited bulk messages.
- Canva OAuth uses Authorization Code + PKCE, encrypted PostgreSQL token storage, and a protected manual refresh endpoint at `POST /oauth/canva/refresh` (requires `X-NOVA-API-Key`). Canva refresh tokens rotate and each token is single-use, so the endpoint stores the replacement token bundle immediately. Design listing, export-format lookup, and asynchronous export job routes are implemented in code. A configured Canva developer app and live verification are still required. Canva Connect API access is subject to Canva's app requirements and review.
- Render free instances may sleep, and local disk may not persist. Use persistent storage and a queue/scheduler for reliable automation.

Never commit API keys, access tokens, or secrets.


## Canva OAuth setup

Configure `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_REDIRECT_URI`, `CANVA_OAUTH_SCOPES`, `DATABASE_URL`, `OAUTH_STATE_SECRET`, and `TOKEN_ENCRYPTION_KEY` in Render. Register the exact HTTPS redirect URI `https://nova-instagram-ai.onrender.com/oauth/canva/callback` in your Canva developer app (or use the exact URI for your own deployment). Run `python -m app.init_oauth_db` to initialize both OAuth state and encrypted token tables, then visit `/oauth/canva/start`. The callback stores tokens server-side and does not return them to the browser. After connecting, the protected `POST /oauth/canva/refresh` endpoint can manually refresh tokens using `X-NOVA-API-Key`; do not call it concurrently because each refresh token can be used only once. OAuth and design/export routes have not yet been verified against a live Canva app. Export download URLs are temporary and should not be treated as permanent storage.
