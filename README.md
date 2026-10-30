# NOVA — Instagram AI starter

NOVA is a FastAPI backend with a Manglish-focused AI reply preview and guarded integration scaffolding.

## Existing and added functionality

### Multi-provider AI text routing

NOVA supports ordered failover across Gemini, Groq, an optional Hugging Face chat route, and the existing custom OpenAI-compatible provider. Set `AI_PROVIDER_ORDER` (default `gemini,groq,huggingface,legacy`) and add the relevant server-side keys: `GEMINI_API_KEY` / `GEMINI_MODEL`, `GROQ_API_KEY` / `GROQ_MODEL`, optional `HF_TOKEN` / `HF_CHAT_MODEL`, or legacy `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL`. Caption generation, content ideas, reply previews, and 12-hour-memory DM drafts use the shared router. NOVA advances to the next configured provider on rate limits, provider errors, timeouts, or malformed responses. Provider quotas are independent and are not increased or bypassed; when all configured providers are unavailable, endpoints return HTTP 503. Keys remain in Render environment variables and are never returned by status endpoints.

The Render web service is the backend/router; no separate support server is required. Keep PostgreSQL for durable state. Render free instances can sleep, so an in-process scheduler on a sleeping free instance cannot guarantee exact-time publishing. Use an always-on service or an external scheduler for dependable schedules.

### AI image generation

`POST /ai/generate-image` remains a separate image-generation integration using `IMAGE_API_BASE_URL`, `IMAGE_API_KEY`, and `IMAGE_MODEL`. Text-only Gemini/Groq chat credentials do not automatically provide image generation. Canva Connect currently handles Canva design listing/export and does not itself grant NOVA a free image-generation model. There is no guaranteed unlimited free hosted image-generation API in this setup: provider quotas and pricing can change, and some image endpoints are paid-only. Do not configure a provider with billing unless you have permission and understand its cost. Generated media still needs a persistent public URL before it can be passed to Instagram or imported into a Canva design.

- `GET /app`: same-origin NOVA Content Studio page for AI captions and content ideas. Requires the normal NOVA account username and password. Requires the normal NOVA account username/password.
- `GET /admin`: protected same-origin admin dashboard for the global AI master switch, AI provider order, daily scheduled photo-post/Story caps, scheduled times, and direct-publishing preference.
- Background scheduler: when `NOVA_SCHEDULER_ENABLED=true`, `INSTAGRAM_AUTOMATION_ENABLED=true`, and the admin direct-publish setting is enabled, NOVA generates original image prompts/captions and publishes photo posts and image Stories at the configured local times. PostgreSQL records each date/type/slot uniquely to avoid duplicate attempts. The scheduler is opt-in and requires a persistent PostgreSQL database, a configured text provider, a compatible image provider returning public HTTPS URLs, an authorized Instagram professional account, and a service that remains awake. Reels/video generation and music attachment are not included in this scheduler.

- `GET /health`: reports code-level implementation flags and whether environment values are present. It does not verify live account connectivity, permissions, or credentials. Manual token refresh and the Instagram webhook receiver are implemented; scheduled token refresh and automatic webhook subscription setup are not.
- `POST /preview-reply`: generates an AI reply preview; it never sends it to Instagram.
- `GET /instagram/verify`: verifies the configured Instagram profile with a live, read-only Meta API request and returns only its profile ID and username. Requires `X-NOVA-API-Key`.
- `GET /instagram/media`: lists accessible professional-account media through Meta's API.
- `GET /instagram/media/{media_id}/comments`: reads comments where permitted.
- `POST /instagram/comments/{comment_id}/reply`: replies to a comment when action endpoints are enabled and the account has permission.
- `POST /instagram/messages/reply`: attempts a supported message reply for an eligible Instagram-scoped recipient ID.
- `POST /instagram/publish-image`: creates and publishes an image container from a publicly reachable image URL.
- `POST /instagram/reels/drafts`: creates a Reel container for review; it does not publish.
- `GET /instagram/reels/drafts/{container_id}`: checks Meta's processing status without publishing.
- `POST /instagram/reels/drafts/{container_id}/publish`: explicitly publishes only after Meta reports `FINISHED`.
- `POST /ai/generate-image`: calls a separately configured OpenAI-compatible image-generation API.
- `POST /ai/generate-caption`: generates a review-only Instagram caption draft in the requested language and tone; it never publishes.
- `POST /ai/content-ideas`: generates original post/Reel/carousel ideas for a niche; ideas are drafts, not verified live trends, and are never scheduled or published.
- `GET /canva/status`: reports Canva integration implementation status without exposing credentials.
- `GET /canva/designs`: lists the connected user's Canva designs (protected by `X-NOVA-API-Key`).
- `GET /canva/designs/{design_id}/export-formats`: lists supported export formats for a design.
- `POST /canva/exports`: starts a Canva export job for a supported format.
- `GET /canva/exports/{job_id}`: checks an asynchronous export job status.
- `POST /canva/instagram-reels/publish`: exports a Canva design as MP4 and publishes it as a Reel after Meta confirms processing is complete.
- `POST /canva/instagram-posts/publish`: exports a Canva design as PNG and publishes it as a photo post.

## Security and setup

1. Configure the official Meta app and authorize the Creator account using the appropriate Instagram Login flow.
2. In Render's private environment settings, set `META_GRAPH_BASE_URL`, `META_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_USER_ID` using values appropriate to that flow. The sample API version may need updating to a currently supported version.
3. Set `NOVA_API_KEY` to a long, random secret. Do not put it in frontend code, public repositories, or chat.
4. Keep `INSTAGRAM_AUTOMATION_ENABLED=false` while testing read-only endpoints. Set it to `true` only after confirming permissions and testing with content you control.
5. Set `NOVA_USER_USERNAME` and `NOVA_USER_PASSWORD` for normal account sign-in to `/app` and AI/publishing routes. Set `NOVA_ADMIN_USERNAME` and `NOVA_ADMIN_PASSWORD` separately for the admin dashboard API. Use unique, strong passwords and store them only in Render private environment variables; never commit them or place them in browser code. The password typed into this chat must not be reused; rotate it if it is used anywhere else.
6. The admin master switch is OFF by default and stored in PostgreSQL. Turn it ON in `/admin` to allow AI generation and scheduled publishing; OFF blocks AI endpoints, automatic DM replies, and direct publishing routes. Admin controls remain accessible so the switch can be turned back on.
7. Add the key as the `X-NOVA-API-Key` header when calling API-key-protected NOVA endpoints. Do not expose this key in a public browser client.
8. Configure `IMAGE_API_BASE_URL`, `IMAGE_API_KEY`, and `IMAGE_MODEL` for an image provider that actually supports the OpenAI-compatible `/images/generations` endpoint. A text-only Groq model is not an image-generation provider.
9. Use a publicly reachable image URL for Instagram publishing. The image-generation endpoint's returned URL may be temporary; reliable publishing usually needs persistent object storage and a public URL.
10. Deploy and check `/health` for code/configuration flags, then use the protected read-only `/instagram/verify` and `/instagram/media` endpoints to verify Meta access before enabling any write action.
9. Run `python -m app.init_oauth_db` to create OAuth, Canva, DM-memory, admin-settings, and scheduler tables.
10. Set `NOVA_SCHEDULER_ENABLED=true` and `INSTAGRAM_AUTOMATION_ENABLED=true` only after validating the connected account, scopes, image-provider output, and schedule. Set `NOVA_TIMEZONE=Asia/Kolkata` for Kerala/India local time. Configure post and Story slots in `/admin`; the scheduler defaults to 09:00 posts and 13:00 Stories.

## OAuth security foundation

The `app/oauth_security.py` module provides signed, time-limited state values and Fernet token-encryption helpers. The `app/oauth_store.py` module adds PostgreSQL helpers for encrypted tokens and one-time OAuth state. The `/oauth/instagram/start` and `/oauth/instagram/callback` routes now implement the Instagram Login redirect, browser-bound state validation, server-side code exchange, long-lived token exchange, and encrypted token storage. A protected manual refresh endpoint is available at `POST /oauth/instagram/refresh` using the `X-NOVA-API-Key` header. A PostgreSQL session-level advisory lock serializes refresh attempts across app workers; concurrent requests receive HTTP 409, and refresh fails closed with HTTP 503 when shared database coordination is unavailable. It refreshes the stored long-lived token when Instagram permits it; expired or provider-rejected tokens return a reconnect-required response, while rate limits return a temporary-unavailable response. Database/decryption errors return a generic service-unavailable response without exposing provider or database details. Token refresh results are stored server-side and never returned to the caller. Automatic scheduled refresh is not implemented. The Instagram webhook receiver includes the subscription-challenge route and signature validation, but the Meta Dashboard subscription must be configured separately and live delivery still needs production verification.

For a deployment using the PostgreSQL store, configure:
- `DATABASE_URL`: private PostgreSQL connection string from the database provider.
- `OAUTH_STATE_SECRET`: a randomly generated secret of at least 32 characters.
- `TOKEN_ENCRYPTION_KEY`: a Fernet key generated with Python's `cryptography` package (keep it outside the database and repository).

Run `python -m app.init_oauth_db` as a deployment/migration step before the app handles OAuth requests. Register the exact `INSTAGRAM_OAUTH_REDIRECT_URI` in the Meta app and keep the client secret server-side. Do not expose decrypted tokens to browser clients or logs. OAuth state must be bound to the initiating browser session in addition to signature/age checks; store and consume its nonce exactly once. Do not enable write actions until the full flow and token renewal are implemented and tested.

To connect: configure the Instagram Login product in the Meta developer dashboard, set `INSTAGRAM_OAUTH_CLIENT_ID`, `INSTAGRAM_OAUTH_CLIENT_SECRET`, `INSTAGRAM_OAUTH_REDIRECT_URI`, `INSTAGRAM_OAUTH_SCOPES`, `OAUTH_STATE_SECRET`, `TOKEN_ENCRYPTION_KEY`, and `DATABASE_URL` in Render; initialize the database schema; then visit `/oauth/instagram/start`. The callback stores the credential server-side and does not return the token to the browser. Use HTTPS and register the exact callback URI.

## Important limitations

- OAuth authorization-code exchange, encrypted token persistence, protected manual token refresh, and the signed Instagram webhook receiver are implemented in code, but have not been verified against live Meta credentials. Automatic scheduled token refresh, automatic webhook subscription setup, and a persistent background job queue are not implemented. Canva design listing and export routes are implemented in code but require a configured Canva app and live verification. The `/health` response reports code-level implementation and environment flags only; it does not establish valid credentials, account connectivity, approved permissions, or live webhook delivery.
- Instagram API permissions and endpoint behavior vary by API version and login flow. App review or access approval may be required.
- Like/unlike automation is not implemented in this starter.
- Instagram Notes creation and attaching music to Notes are not supported by the standard public API. Do not automate them through private endpoints or browser workarounds.
- Reels audio/music publishing requires a separately verified, supported Meta audio workflow and suitable licensing. This starter does not attach music to Reels.
- Message sending is subject to Meta messaging permissions, eligible conversations, and messaging windows. Do not use it for unsolicited bulk messages.
- Canva OAuth uses Authorization Code + PKCE, encrypted PostgreSQL token storage, and a protected manual refresh endpoint at `POST /oauth/canva/refresh` (requires `X-NOVA-API-Key`). Canva refresh tokens rotate and each token is single-use, so the endpoint stores the replacement token bundle immediately. Design listing, export-format lookup, asynchronous export jobs, direct Reel publishing, and direct photo-post publishing are implemented in code. A configured Canva developer app and live verification are still required. Canva Connect API access is subject to Canva's app requirements and review.
- Render free instances may sleep, and local disk may not persist. Use persistent storage and a queue/scheduler for reliable automation.

Never commit API keys, access tokens, or secrets.


## Canva OAuth setup

Configure `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_REDIRECT_URI`, `CANVA_OAUTH_SCOPES`, `DATABASE_URL`, `OAUTH_STATE_SECRET`, and `TOKEN_ENCRYPTION_KEY` in Render. Register the exact HTTPS redirect URI `https://nova-instagram-ai.onrender.com/oauth/canva/callback` in your Canva developer app (or use the exact URI for your own deployment). Run `python -m app.init_oauth_db` to initialize both OAuth state and encrypted token tables, then visit `/oauth/canva/start`. The callback stores tokens server-side and does not return them to the browser. After connecting, the protected `POST /oauth/canva/refresh` endpoint can manually refresh tokens using `X-NOVA-API-Key`. A PostgreSQL session-level advisory lock serializes refresh attempts across application workers; a concurrent attempt receives HTTP 409 instead of consuming the same single-use refresh token. This guard requires a healthy shared `DATABASE_URL`. Canva credentials are stored encrypted and bound to a stable account key (normally the Canva `user_id`). If the token response omits `user_id`, set `CANVA_ACCOUNT_KEY` before connecting to assign a stable key. If more than one Canva account is stored, set `CANVA_ACCOUNT_KEY` to the intended account key; otherwise NOVA refuses to silently select whichever account was most recently updated. Existing single-account installations can leave it unset. A rejected refresh token returns a reconnect-required response; rate limiting is reported separately. Before Canva's single-use refresh token is sent, NOVA durably marks that account's token bundle as rotation-pending. If the request outcome is ambiguous, the provider returns an error other than a confirmed rate limit, or saving the replacement bundle fails, subsequent token reads fail closed instead of reusing the old refresh token. A confirmed HTTP 429 clears the marker because the provider has explicitly rate-limited the request without rotating credentials. Restore database/encryption configuration and reconnect Canva to replace a pending bundle; a successful OAuth token save clears the marker. Existing installations receive the new marker columns automatically when `initialize_canva_schema()` runs. If Canva returns a replacement bundle but the database cannot save it, restore storage first and reconnect Canva if needed rather than retrying with the old refresh token. OAuth, design/export routes, and direct publishing have not yet been verified against a live Canva app and Instagram account. Export download URLs are temporary and should not be treated as permanent storage.


## Canva export to Instagram: manual review gate

The protected `POST /canva/instagram-draft-exports` endpoint starts a Canva PNG export for an Instagram post or an MP4 export (vertical 1080p target) for a Reel. It returns the export job and caption but **does not publish**. Poll `GET /canva/instagram-draft-exports/{job_id}` until the job succeeds; the response then includes temporary preview URLs. Review the actual media and caption yourself before using the existing Instagram publishing endpoint. The Canva URLs expire after 24 hours and should not be stored as permanent assets.

Both routes require `X-NOVA-API-Key` and a connected Canva account. Reel export quality is only a target resolution; Canva preserves the design's aspect ratio, so check the actual dimensions before publishing. Instagram publishing remains a separate explicit action and still requires valid Meta permissions and `INSTAGRAM_AUTOMATION_ENABLED=true`.


## Canva export format validation

Before starting an Instagram draft export, NOVA now calls Canva's design export-formats endpoint and checks that the requested PNG or MP4 format is available for that design. If Canva doesn't report the format, NOVA returns a validation error and does not create an export job. This avoids guessing based only on the design's category. The result still requires a manual review; no Instagram content is published by this workflow.


## Instagram Reels: review before publishing

The protected Reel workflow uses Meta's official container process. First call `POST /instagram/reels/drafts` with an HTTPS, publicly reachable `video_url`, caption, and `share_to_feed`. This creates a container but does not publish it. Then call `GET /instagram/reels/drafts/{container_id}` and wait until Meta reports `status_code=FINISHED`. After you have reviewed the media and caption, publication requires a separate explicit call to `POST /instagram/reels/drafts/{container_id}/publish`. The publish route rechecks the status and refuses containers that are not ready. These action routes require `X-NOVA-API-Key` and `INSTAGRAM_AUTOMATION_ENABLED=true`, plus valid Meta authorization and content-publishing permissions. The video URL must remain publicly accessible while Meta fetches it. No music is attached by this workflow.


## Canva MP4 export to Instagram Reel draft

After creating an export with `POST /canva/instagram-draft-exports` using `target: "reel"`, poll its export job until `status=success`. Then call `POST /canva/instagram-reel-drafts/{job_id}` with the caption and `share_to_feed`. NOVA fetches the completed export job from the connected Canva account and creates a Meta Reel container; it does not publish. Check `GET /instagram/reels/drafts/{container_id}` and review the media/caption before using the separate explicit publish endpoint. This bridge requires `X-NOVA-API-Key`, connected Canva and Instagram accounts, and `INSTAGRAM_AUTOMATION_ENABLED=true`. Canva URLs expire after 24 hours, so Meta must fetch the export before it expires. Use this endpoint only with a successful MP4 export created for a Reel.


## Direct Canva-to-Instagram Reel publishing

For an explicitly requested direct publish, call `POST /canva/instagram-reels/publish` with `{"design_id":"YOUR_CANVA_DESIGN_ID","caption":"Your caption","share_to_feed":true}` and the `X-NOVA-API-Key` header. NOVA verifies MP4 support, starts a Canva MP4 export, waits for Canva to finish, creates an Instagram Reel container, waits for Meta to report `FINISHED`, then publishes. It is protected by `INSTAGRAM_AUTOMATION_ENABLED=true`; publishing remains disabled by default. If either platform is still processing after the bounded wait, NOVA returns a job/container ID and does not claim it was published. Canva export URLs expire after 24 hours. Live credentials, account permissions, and Render deployment still need real-world verification. This workflow does not attach music.


## Direct Canva-to-Instagram photo publishing

Call `POST /canva/instagram-posts/publish` with `{"design_id":"YOUR_CANVA_DESIGN_ID","caption":"Your caption"}` and the `X-NOVA-API-Key` header. NOVA checks PNG export support, waits for Canva's export to finish, creates the Instagram image container, and calls the official publish endpoint. This is a direct publish workflow, not a draft. It requires `INSTAGRAM_AUTOMATION_ENABLED=true`, connected Canva and Instagram accounts, and valid Meta permissions; the action flag stays disabled by default. Canva export URLs expire after 24 hours. Live account and Render verification are still required.


## Direct publishing safety and verification status

The direct Canva publishing routes are write actions: `POST /canva/instagram-reels/publish` and `POST /canva/instagram-posts/publish`. Both require the `X-NOVA-API-Key` header, a connected Canva account, valid Instagram authorization and permissions, and `INSTAGRAM_AUTOMATION_ENABLED=true`. Publishing is disabled by default. These endpoints can publish immediately once enabled, so use them only when you intentionally want that exact design and caption posted. Do not test with a real account until you have reviewed the design/caption and confirmed account permissions. Automated tests do not establish that live Canva, Meta, or Render integration works; live verification remains outstanding.


## Instagram DM conversation memory (12-hour retention)

NOVA includes a protected PostgreSQL store for short-lived DM context. Each stored message expires 12 hours after it was added; expired rows are excluded from reads and cleaned up during memory reads/writes. The store keeps at most the latest 30 unexpired messages per recipient in each context response. Use:
- `POST /instagram/dm-memory/messages` with `recipient_id`, `role` (`user` or `assistant`), and `message`.
- `GET /instagram/dm-memory/{recipient_id}` to retrieve the recent context.
- `DELETE /instagram/dm-memory/{recipient_id}` to clear a conversation immediately.

All three endpoints require `X-NOVA-API-Key`. Configure `DATABASE_URL` and run `python -m app.init_oauth_db` to create the memory table. Do not put the API key in browser code or logs.

**Important:** this adds the 12-hour storage/retrieval layer only. Automatic ingestion from real Instagram DMs and using this context when NOVA generates/sends replies still require an approved Meta messaging webhook/event flow and integration work. The current implementation does not fetch DMs by itself or send messages. Expiry is enforced when records are accessed or written; a database scheduler can be added later for physical deletion at the exact expiry time.


### Incoming Instagram DM webhook

The protected 12-hour memory store now has a webhook receiver:
- `GET /webhooks/instagram` handles Meta's subscription challenge.
- `POST /webhooks/instagram` validates `X-Hub-Signature-256` with `META_APP_SECRET` and stores supported incoming text messages as user turns.
- Echo messages and non-text attachments are ignored. Incoming Meta message IDs (`message.mid`) are stored under a partial unique index so repeated webhook deliveries are skipped before AI generation or sending; run `python -m app.init_oauth_db` to apply the schema update. Events without a message ID can still be ingested but cannot receive ID-based deduplication. If `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=true`, it can generate and send a context-aware reply to an eligible incoming text DM using Meta's official messaging endpoint. Replies are skipped unless the incoming event timestamp is within the standard 24-hour messaging window; the 12-hour memory duration does not extend that window.

Set `META_APP_SECRET` and a long random `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` in the server environment, configure the HTTPS webhook URL in Meta, and subscribe to the required Instagram messaging events only after the app/account has the required access. Keep `DATABASE_URL` configured and run `python -m app.init_oauth_db`.

Automatic replies are disabled by default. Before enabling them, verify Meta app review/permissions, the webhook subscription, the Instagram messaging scope, token validity, and a test conversation. This code and automated tests do not prove live Meta delivery or permission approval. The webhook never initiates cold DMs and does not use the Human Agent exception.


### Memory-aware DM reply drafts

`POST /instagram/dm-memory/preview-reply` is a protected, draft-only endpoint. Send `recipient_id`, the latest `message`, and optional `language_hint` with `X-NOVA-API-Key`. It loads the last 12 hours of stored messages (up to 30) and uses the configured AI text provider to produce a reply preview. The response explicitly reports `sent_to_instagram: false`; it does not send or save the generated draft as a conversation turn. Real incoming text is added to memory only by the verified webhook, so webhook delivery and permissions must be configured for full behavior.


### Actual automatic DM replies

Set `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=true` only after a test conversation confirms the official messaging API works and the account has the required approved messaging permission. Keep it `false` otherwise. The webhook uses the recent 12-hour memory to generate replies and stores the assistant response only after Meta accepts the send. It skips replies when the event timestamp is missing/outside the standard 24-hour window, AI configuration is missing, or credentials are unavailable. NOVA does not run a background retry queue. Retryable AI or Meta send failures mark the event retryable and return HTTP 503 so Meta can redeliver the webhook. Database-backed claims prevent concurrent workers from replying to the same message, and an accepted reply is marked sent before its assistant-history turn is saved. A timeout after Meta accepts a send but before NOVA can confirm that acceptance remains an unavoidable uncertain-outcome risk. The `/instagram/dm-memory/preview-reply` endpoint remains available for manual review, but the webhook path can send actual replies when explicitly enabled.
