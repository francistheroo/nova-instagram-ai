# NOVA deployment checklist

- [ ] Deploy the FastAPI app to a Python host and keep the Git repository private.
- [ ] Add AI provider credentials through the host's environment settings; never commit `.env`.
- [ ] Verify `/health` and test `/preview-reply` with Manglish, Malayalam, and English.

## Connect a real Instagram account

- [ ] In Meta for Developers, configure **Instagram API with Instagram Login / Business Login** for the app.
- [ ] Add the exact HTTPS callback URL from `INSTAGRAM_OAUTH_REDIRECT_URI` to Meta's Business Login redirect settings. It must match character-for-character.
- [ ] Copy the Instagram Login product's client ID and app secret into `INSTAGRAM_OAUTH_CLIENT_ID` and `INSTAGRAM_OAUTH_CLIENT_SECRET`. Do not use a different Facebook app ID or expose the secret in the browser.
- [ ] Configure the requested permissions in the Meta app: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, and `instagram_business_manage_messages`. Request only permissions enabled for the app.
- [ ] Set `DATABASE_URL`, a random `OAUTH_STATE_SECRET` of at least 32 characters, and a valid Fernet `TOKEN_ENCRYPTION_KEY` in the host's secret settings. Keep the encryption key stable so existing stored tokens remain decryptable.
- [ ] Set `META_API_VERSION=v26.0` unless the app has been deliberately pinned to another supported version.
- [ ] Run `python -m app.init_oauth_db` once against the production database.
- [ ] Sign in to NOVA as the admin, then open `/oauth/instagram/start` in that same browser and approve the permissions using the intended Instagram **Business or Creator** account.
- [ ] After the redirect, check the admin-protected `/oauth/instagram/status` endpoint. It should report `connected: true` and `verified: true`, along with the expected username. It never returns the access token.
- [ ] Keep automation and scheduled publishing disabled until read-only account verification and the individual supported actions have been tested.

The OAuth callback is intentionally reachable without NOVA Basic Auth because Meta redirects the browser to it. It is protected by the signed state, browser-bound HttpOnly cookie, short expiry, and one-time PostgreSQL nonce. The connect and status routes remain admin-only.

Instagram Login supports professional accounts (Business or Creator), not personal accounts. Accounts outside the app's own roles may require Advanced Access and Meta App Review.

Do not paste passwords, session cookies, access tokens, or API keys into a chat.