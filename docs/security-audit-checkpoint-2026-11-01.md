# NOVA security and integration audit checkpoint — 2026-11-01

Repository: `francistheroo/nova-instagram-ai`
Working branch: `security/audit-live-dm-gate`
Base: `main`

## Instagram Creator-account OAuth and permissions

- NOVA uses Instagram Login at `graph.instagram.com`, which supports Instagram professional accounts (Business and Creator).
- The configured default scopes are `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, and `instagram_business_manage_messages`. These cover the current profile/media, publishing, comment, and messaging features; Meta app review/Advanced Access may still be required for accounts outside app roles.
- OAuth state is signed, short-lived, browser-bound, and consumed once. Authorization-code exchange and long-lived token exchange happen server-side. The returned account ID is compared with the profile ID resolved by the long-lived token before encrypted storage.
- OAuth start/status require the NOVA admin login. Refresh requires admin login and `X-NOVA-API-Key`. The public callback is intentionally unauthenticated because Meta redirects the browser to it; it is protected by the one-time state and matching secure browser cookie.
- Code-level verification is implemented; a real Creator account, granted scopes, app-review access, token, and webhook delivery have not been verified by repository tests. Do not treat `/health` or configuration presence as proof of live access.

## Admin authentication and master switch

- `require_user` accepts only `NOVA_ADMIN_USERNAME` and `NOVA_ADMIN_PASSWORD`; there is no ordinary-user credential path in this shared dependency.
- Sensitive API operations additionally require `NOVA_API_KEY` where implemented.
- The NOVA master switch is read from PostgreSQL and fails closed when the database is missing or unavailable.
- Public health/integration status routes expose configuration booleans and implementation status only; they do not return secrets or prove account authorization.

## DM conversation memory

- PostgreSQL stores per-recipient messages with a 12-hour expiry; reads filter to `expires_at > now`, expired rows are cleaned during reads/writes, and context is capped at 30 messages.
- DM-memory APIs require the NOVA API key and admin authentication. Reply preview additionally requires the master switch and is explicitly draft-only.
- Expired rows are logically unavailable after 12 hours, but physical deletion is lazy (on subsequent memory reads/writes), not guaranteed at the exact expiry instant.
- The webhook verifies Meta's request signature, validates inbound text, deduplicates stable message IDs, and respects the standard 24-hour messaging window independently of the 12-hour memory TTL.

## Development safety finding and fix

- Audit found the webhook auto-reply path previously checked `INSTAGRAM_AUTO_DM_REPLIES_ENABLED` and the NOVA master switch, but did not also require the global `INSTAGRAM_AUTOMATION_ENABLED` kill switch. This could allow a webhook reply if the DM-specific flag and master switch were enabled while the global Instagram automation flag was off.
- Working-branch fix: automatic DM replies now require all three gates: `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=true`, `INSTAGRAM_AUTOMATION_ENABLED=true`, and the NOVA master switch ON.
- The webhook Graph API default was aligned from v25.0 to the repository's configured v26.0 default.
- Added a regression test proving the global automation OFF state prevents claiming an event or generating/sending a reply even when the DM-specific flag and master switch are ON.
- README guidance now says to keep both live-action environment flags false throughout development.

## Required development settings

```dotenv
INSTAGRAM_AUTOMATION_ENABLED=false
INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false
NOVA_SCHEDULER_ENABLED=false
INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED=false
```

The first three settings keep publishing, automatic DMs, and scheduled publishing off. Token refresh is maintenance-only, but remains opt-in until the OAuth connection is verified.

## Validation boundary

- Tests use mocked providers; no live Instagram messages or content are sent by this change.
- Production Render environment values cannot be verified from repository source. Confirm the three live-action flags are false in deployment settings before any development deployment.
- Run CI on this branch and preserve this checkpoint with the resulting workflow status before merge.
