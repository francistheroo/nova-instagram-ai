# NOVA Instagram AI — Recovery Checkpoint

Updated: 2026-10-29 (verified against GitHub)

## Project
- Repository: https://github.com/francistheroo/nova-instagram-ai
- Render service: https://nova-instagram-ai.onrender.com
- Goal: NOVA Instagram assistant with Manglish Malayalam + English, caption/content ideas, supported Instagram publishing/messaging, Canva integration, and 12-hour DM context.
- Instagram account type: Creator. Canva plan: Free.

## Safety / live operation
- Never paste API keys, passwords, access tokens, or secrets into chat.
- Do not merge PRs, deploy, publish, change Meta settings, or enable live auto-replies without explicit user authorization.
- `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false` by default. Keep it disabled during development.
- Use official supported Meta APIs only. No private endpoints, browser automation, cold DMs, or unsolicited bulk messaging.
- Instagram Notes/music and standard auto-like/follow/follow-back are not supported through the standard public API. DM access depends on permissions and conversation eligibility.
- Never claim live Meta behavior works unless verified.

## Verified repository milestones
- PRs #1–#27: FastAPI starter, CI, OAuth, Canva, guarded publishing, status, AI caption drafts/content ideas, and Content Studio.
- PR #29: webhook ingestion and 12-hour DM memory.
- PR #30: opt-in DM auto-replies within the standard 24-hour messaging window; default off.
- PRs #31/#32: duplicate message-memory protection and tests.
- PR #34: PostgreSQL-backed DM retry-state helper foundation.
- PR #35: integrates retry-state handling into the webhook.
- PR #36: regression coverage for Meta send-failure retry.
- PR #37: stale/out-of-window DM test.
- PR #38: expired processing lease recovery tests.
- PR #40: duplicate webhook delivery test when auto-replies are disabled.
- PR #41: missing stable Meta message ID test; merged.
- PR #42: invalid webhook signature and echo-event safety tests; merged. The associated GitHub Actions run #85 reported success.
- PR #42 merge commit: `52ab33d45f1c3f219b18b9446ae56a243e442726`.

## DM webhook behavior to remember
- Incoming text messages are verified using `X-Hub-Signature-256` and `META_APP_SECRET`.
- Echo messages are ignored.
- Stable Meta `message.mid` is required for automatic replies and safe retry claims. Messages without a stable ID may be stored but must not trigger AI replies.
- Duplicate inbound message IDs are protected by database uniqueness.
- Retry state is tracked separately from conversation memory; transient AI/Meta failures can be retried on a later webhook delivery.
- Replies are opt-in and must remain disabled unless the user explicitly authorizes enabling live behavior and the required Meta permissions/configuration are verified.
- A timeout after Meta accepts a send but before NOVA receives the response can still cause a duplicate on retry; public APIs do not provide a general idempotency key for this send.
- Mocked tests do not prove production PostgreSQL concurrency or live Meta behavior.

## Recommended next engineering work
1. Add safe PostgreSQL-backed tests for retry-state transitions and concurrent claims, using a dedicated test database only.
2. Review webhook error handling for malformed payloads and database outages; add focused regression tests together in one PR.
3. Verify current GitHub Actions results by exact commit SHA before reporting CI as passed.
4. Keep PRs draft until tests and schema are reviewed. Do not merge or deploy without user authorization.

## Workflow
The user often says “Next” to request another incremental step. Make real repository progress, combine closely related changes in one PR, and report exact verified status. Recheck GitHub before relying on this checkpoint in a future chat.
