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
- PR #42: invalid webhook signature and echo-event safety tests; GitHub Actions run #85 succeeded.
- PR #43: refreshed recovery checkpoint.
- PR #44: opt-in PostgreSQL retry-state integration tests; requires `NOVA_TEST_DATABASE_URL` and does not fall back to `DATABASE_URL`.
- PR #45: malformed signed JSON returns HTTP 400 and storage runtime failures return HTTP 503; GitHub Actions run #91 succeeded.
- PR #46: added regression coverage for unsupported webhook payload shapes.
- PR #47: normalized malformed non-list `entry` and `messaging` fields before iteration; GitHub Actions run #95 succeeded.
- PR #48: invalid timestamp regression test; merged as `2df6c19d20a1a05500b28918266f5d855d8a21e4`. GitHub Actions run #97 succeeded for head commit `f62a6c413e138ef4a17cbb62562340dd54cda014`.

## DM webhook behavior to remember
- Incoming text messages are verified using `X-Hub-Signature-256` and `META_APP_SECRET`.
- Invalid JSON is rejected with HTTP 400; storage/runtime failures return HTTP 503.
- Echo messages are ignored. Malformed collection fields are treated as empty lists rather than crashing.
- Stable Meta `message.mid` is required for automatic replies and safe retry claims. Messages without a stable ID must not trigger AI replies.
- Invalid event timestamps are marked ignored; they must not trigger AI generation.
- Duplicate inbound message IDs are protected by database uniqueness.
- Retry state is tracked separately from conversation memory with `processing`, `sent`, `retryable`, and `ignored` outcomes. Expired processing leases can be reclaimed.
- Replies are opt-in and must remain disabled unless the user explicitly authorizes enabling live behavior and the required Meta permissions/configuration are verified.
- A timeout after Meta accepts a send but before NOVA receives the response can still cause a duplicate on retry; public APIs do not provide a general idempotency key for this send.
- Mocked tests do not prove production PostgreSQL concurrency or live Meta behavior. Run PostgreSQL integration tests only with a dedicated `NOVA_TEST_DATABASE_URL`.

## Current work — draft PR #62 (not merged/deployed)
- PR: https://github.com/francistheroo/nova-instagram-ai/pull/62
- Branch: `feature/webhook-dm-retries`
- Current latest commit: `deeaad4f602ea412704bcac6d764c7f10a0b06c4`
- Adds a regression test for retry after a transient AI generation failure and marks an event retryable immediately if inbound memory storage fails after claim.
- The first CI run on commit `7fdf25ed0b153b6f4063d0cde6bc4b45c4f5f102` failed (231 passed, 4 skipped, 2 failed). One failure was the new retry test; the other was a CancelledError in a separate webhook shape test. The retry test's fake HTTP client patched the shared `httpx.AsyncClient`, which could interfere with TestClient internals. Latest commit isolates the mock by replacing only the webhook module's `httpx` reference.
- CI has not yet reported a run for latest commit `deeaad4f602ea412704bcac6d764c7f10a0b06c4`; do not claim it passes until checked.
- PR title: “Release failed DM claims and test AI retry”. Keep draft until latest CI passes and code/tests are reviewed.

## Recommended next engineering work
1. Continue focused regression tests for webhook parsing, timestamp handling, and retry-state edge cases.
2. Run the opt-in PostgreSQL integration suite against a dedicated test database when available.
3. Verify GitHub Actions results by exact commit SHA before reporting CI as passed.
4. Keep new PRs draft until tests and schema are reviewed. Do not merge or deploy without user authorization.

## Workflow
The user often says “Next” or “Fast” to request another incremental step. Make real repository progress, group related changes into one PR, and report exact verified status. Recheck GitHub before relying on this checkpoint in a future chat.

---

## Latest verified checkpoint — 2026-11-01

### CI and PR #121 — merged
- PR: https://github.com/francistheroo/nova-instagram-ai/pull/121
- Title: **Add Canva photo draft review and explicit publish gate**
- Branch: `feature/canva-photo-review-gate`
- Head commit: `4cc01b076c020eac3c70fbbd5dcc142df0c5355c`
- PR state: **closed and merged** on 2026-11-01 at 09:17:13 UTC.
- Merge commit: `c1db27536ff3dd6df9d1c0ac16959e9064cc9e8b`
- Changes: 2 files, 261 additions, 0 deletions.
- GitHub Actions workflow: **NOVA tests**
- Workflow run #318 (run ID `41292245052`): **completed successfully**; conclusion `success`.
- Run URL: https://github.com/francistheroo/nova-instagram-ai/actions/runs/41292245052

### Canva photo draft workflow now in main
- Authenticated user/admin access is required by the Canva review router.
- Draft creation and publication require the NOVA API key and master switch.
- Instagram actions also require `INSTAGRAM_AUTOMATION_ENABLED=true`.
- Creating a Canva photo draft creates a Meta image container only; it does **not** publish.
- Canva export must report `success` before a photo container can be created.
- The status endpoint is read-only and reports whether Meta has returned `FINISHED`.
- Publishing is a separate explicit POST action and is rejected unless Meta reports `FINISHED`.
- Regression tests cover draft creation without publishing, unfinished Canva export rejection, status checking, unfinished Meta container rejection, and explicit publish after `FINISHED`.
- The PR's tests used mocks. A green CI run does not prove that live Canva or Meta credentials, permissions, or production publishing work.

### Current operating configuration checkpoint
- `NOVA_SCHEDULER_ENABLED=true`
- `INSTAGRAM_AUTOMATION_ENABLED=true`
- `NOVA_TIMEZONE=Asia/Kolkata`
- These are the user's intended environment values, not independently verified production environment values.
- Keep secrets out of GitHub files and chat. Never store API keys, passwords, access tokens, or OAuth secrets in this checkpoint.

### Resume instructions
1. Start from the latest `main` branch; PR #121 is already merged.
2. Check open PRs and latest GitHub Actions runs before starting another change.
3. Verify exact head commit and workflow conclusion before reporting CI status.
4. Keep draft creation separate from publication. Do not call live publish endpoints during tests.
5. Do not deploy, enable live auto-replies, change Meta settings, or publish Instagram content without explicit user authorization.
6. Treat this checkpoint as repository progress/configuration notes, not proof of live production integration.
