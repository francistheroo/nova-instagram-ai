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


---

## Latest NOVA integration diagnostic — 2026-11-01

### Render service status reported by the deployed health/status endpoint

The user supplied this status response from the NOVA service:

- Service status: `ok`
- Service name: `NOVA Instagram AI`
- `instagram_configured=false`
- `instagram_manual_credentials_present=false`
- `instagram_live_connection_verified=false`
- `instagram_oauth_implemented=true`
- `instagram_token_refresh_implemented=true`
- `instagram_manual_token_refresh_implemented=true`
- `instagram_automatic_token_refresh_implemented=true`
- `instagram_automatic_token_refresh_enabled=true`
- `instagram_automatic_token_refresh_running=true`
- `instagram_automatic_token_refresh_error="UndefinedTable"`

### Interpretation

- The web service reports healthy, and OAuth/token-refresh code paths are present.
- Instagram is **not configured** and no real Instagram connection has been verified.
- Automatic token refresh is reported as enabled/running, but its latest reported error is `UndefinedTable`. This indicates a database table expected by the refresh process is missing in the connected database, or the deployed schema is not up to date.
- Do not treat the refresh worker's `running=true` flag as proof that refresh is functioning correctly.
- Do not claim Instagram OAuth, token persistence, or live publishing has been tested successfully.

### Next steps

1. Inspect the deployed migration/schema history and identify the exact table referenced by the token-refresh error. Do not guess a table name from this checkpoint.
2. Confirm the Render service is connected to the intended PostgreSQL database without exposing the database URL or credentials.
3. Apply the repository's existing migration/init procedure for the missing table; avoid creating a duplicate or ad-hoc schema.
4. Check service logs and the status endpoint again. The refresh error should be absent before considering token refresh healthy.
5. Configure the Meta OAuth credentials privately in Render and verify the exact redirect URI in the Meta developer dashboard.
6. Complete OAuth with an eligible Instagram professional account, then confirm the admin-only status endpoint reports the expected connected account without exposing tokens.
7. Keep live publishing and auto-replies disabled until the account connection and each intended action are separately verified and explicitly authorized.

### Security reminders

- Never commit `DATABASE_URL`, Meta client secrets, OAuth state secrets, token-encryption keys, access tokens, or admin passwords.
- Do not paste secret values into chat or checkpoint files.
- Mocked GitHub tests and a healthy HTTP status do not prove a live Instagram connection.


---

## Part 3 audit checkpoint — 2026-11-01

### Repository and CI position at audit start
- Repository: `francistheroo/nova-instagram-ai`; work is based on `main`.
- Latest repository commit observed before this checkpoint update: `bacf936edb06b536bff8c0a721eb2153676fd612`.
- Canva photo review-gate edge-case PR #122 is merged as `6edf84e96b58e70a8523359fa5972363018a8cfd`.
- PR #122 CI run `41293583471` completed successfully: **502 passed, 6 skipped, 40 warnings, 0 failed**. The three added tests cover disabled actions, rejection of non-HTTPS Canva export URLs, and refusal to publish unless Meta reports `FINISHED`.
- This is PR-head CI evidence. A separate post-merge `main` workflow run was not verified during this audit.

### Canva connection and review-before-publish audit
- Canva OAuth/PKCE, encrypted PostgreSQL token storage, manual token refresh, design listing, export-format lookup, and asynchronous export routes are implemented in the repository.
- `.env.example` leaves Canva client credentials empty. The code reports `canva_live_connection_verified=false`; no live Canva account connection or permission check was performed. Do not treat implementation flags as proof of connection.
- Review workflow:
  1. `POST /canva/instagram-draft-exports` checks that PNG/MP4 is supported and starts an export. It returns `review_required=true` and `published=false`.
  2. `GET /canva/instagram-draft-exports/{job_id}` polls Canva and exposes temporary preview URLs only after export success. Canva export URLs expire after 24 hours.
  3. The photo/Reel draft routes create a Meta media container but do not publish.
  4. The photo status route reports publish readiness without publishing. The separate photo/Reel publish action must be explicitly called and the Meta container must report `FINISHED`.
- The review routes require admin authentication; write/action routes also retain NOVA API-key, master-switch, and Instagram-automation gates as applicable. Tests use mocked Canva/Meta calls and do not establish live platform behavior.
- **Important bypass to keep disabled in development:** `POST /canva/instagram-posts/publish` and `POST /canva/instagram-reels/publish` are separate direct-publish routes. They can publish immediately after export and do not require the per-item review workflow. Keep `INSTAGRAM_AUTOMATION_ENABLED=false` and the admin master/direct-publish settings OFF while developing. Do not use these direct routes for review-flow testing.

### Scheduler and Asia/Kolkata audit
- Safe sample defaults in `.env.example`: `NOVA_SCHEDULER_ENABLED=false`, `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_TIMEZONE=Asia/Kolkata`.
- Admin defaults are fail-closed: `master_enabled=false`, `direct_publish_enabled=false`; default schedule slots are 09:00 photo posts and 13:00 Stories, with daily caps of 3 each.
- The scheduler starts only when `NOVA_SCHEDULER_ENABLED=true` and a database URL is present. Actual scheduled publishing additionally requires `INSTAGRAM_AUTOMATION_ENABLED=true`, the admin master switch ON, and `direct_publish_enabled=true`.
- The scheduler uses `ZoneInfo(NOVA_TIMEZONE)`; its default is `Asia/Kolkata`. Local slot dates are persisted, duplicate slots are blocked, and ambiguous/stale processing outcomes become `uncertain` rather than being retried.
- Schedule slots accept strict 24-hour `HH:MM` values and duplicate valid slots are removed. Invalid/malformed slot collections disable that schedule.
- **Audit finding — daily-cap validation mismatch:** the admin API/UI accepts caps up to 50, while the scheduler's `_daily_limit` accepts only 0–20 and silently converts values above 20 to 0 (schedule disabled). Align these limits before anyone configures caps above 20.
- **Audit finding — timezone readiness:** an invalid `NOVA_TIMEZONE` makes `ZoneInfo` raise inside the scheduler loop; the broad loop exception handler suppresses it, so scheduling can stop without a clear health diagnostic. Validate the timezone at startup and expose a safe readiness/error flag before enabling scheduling.
- The earlier checkpoint's `NOVA_SCHEDULER_ENABLED=true` and `INSTAGRAM_AUTOMATION_ENABLED=true` values are historical intended environment values, not verified current Render settings. For the current development phase, the safe required posture is both flags OFF, DM auto-replies OFF, and admin master/direct publishing OFF. Keep `NOVA_TIMEZONE=Asia/Kolkata`.

### Render health and deployment readiness
- The live NOVA Render endpoints `/health` and `/integrations/status` could not be fetched from this audit session, so current live service health and current deployment commit are **NOT VERIFIED** here.
- The most recent health payload previously supplied by the user and recorded above reported service `status=ok`, but also `instagram_configured=false`, `instagram_live_connection_verified=false`, and `instagram_automatic_token_refresh_error="UndefinedTable"`.
- The recorded `UndefinedTable` error is a deployment/database-readiness blocker for the token-refresh worker until the exact missing schema/table is identified and the existing initializer/migration is applied. Use the repository's existing `python -m app.init_oauth_db` procedure only after confirming the intended Render PostgreSQL database; do not create an ad-hoc duplicate table.
- `/health` and `/integrations/status` expose implementation/configuration flags, not proof of valid credentials, approved permissions, or a live Canva/Meta connection.
- No Render environment values were changed, no deployment was triggered, and no live Canva/Meta publish or messaging request was made.

### Part 3 resume instructions
1. Keep development safety flags OFF: `NOVA_SCHEDULER_ENABLED=false`, `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`; admin `master_enabled=false` and `direct_publish_enabled=false`.
2. Preserve `NOVA_TIMEZONE=Asia/Kolkata`.
3. Resolve the scheduler cap mismatch and timezone validation/health gap in a focused code-and-test PR before enabling scheduling.
4. Verify the Render database schema and remove the recorded token-refresh `UndefinedTable` error; then re-fetch live `/health` and `/integrations/status` without exposing secrets.
5. Verify Canva OAuth with a real authorized account only when explicitly approved. Keep direct-publish routes disabled; use draft → inspect → Meta `FINISHED` → explicit approval/publish.
6. Do not deploy, enable live publishing/DM automation, change Meta settings, or publish content without explicit user authorization.


---

## Part 3 deployment and environment audit — 2026-11-01 (expanded)

### Repository state and verification correction
- Audit base: `main` at `2270b2cecaa0ce89431652bfa2d4f114dab5dfa7`.
- The earlier note above saying a post-merge `main` workflow was not verified is superseded: GitHub Actions run #333 (run ID `41295206264`) ran on descendant commit `48bbe70670dcbeaf2fd22ec2afa6e723d3bdb7f2`, which includes the PR #124 merge. The run completed successfully; its test job passed with **503 passed, 6 skipped, 40 warnings, 0 failures**. It was not a workflow triggered directly on the PR #124 merge SHA.
- `requirements.txt` declares FastAPI, Uvicorn, HTTPX, python-dotenv, cryptography, psycopg[binary], and pytest. A root `render.yaml` and root `Dockerfile` were not found during this audit; verify the Render service's build/start commands in its private dashboard rather than assuming a Blueprint or Docker deployment.
- Live `/health` and `/integrations/status` could not be retrieved in this audit session. The previous user-supplied `status=ok` payload and `UndefinedTable` refresh error remain historical evidence only, not a current live health check. Current Render deploy commit, environment values, database binding, and service plan are not independently visible from GitHub.

### Environment variable inventory (names only; never store values here)
**Core service and security**
- `DATABASE_URL`: PostgreSQL connection string; required for durable OAuth/token, Canva, DM-memory, admin, and scheduler state.
- `NOVA_API_KEY`: protects action/API-key routes.
- `NOVA_ADMIN_USERNAME`, `NOVA_ADMIN_PASSWORD`: admin login for `/app` and `/admin`.
- `OAUTH_STATE_SECRET`: random state-signing secret (README specifies at least 32 characters).
- `TOKEN_ENCRYPTION_KEY`: Fernet key used to encrypt stored OAuth token bundles.
- Run `python -m app.init_oauth_db` against the intended Render PostgreSQL database before OAuth/Canva/DM-memory/scheduler operations. Confirm the database target and backup/restore plan before running schema initialization.

**Instagram / Meta**
- OAuth path: `INSTAGRAM_OAUTH_CLIENT_ID`, `INSTAGRAM_OAUTH_CLIENT_SECRET`, `INSTAGRAM_OAUTH_REDIRECT_URI`, `INSTAGRAM_OAUTH_SCOPES`.
- API configuration/manual-token path: `META_GRAPH_BASE_URL`, `META_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`. Use the current supported API version and credentials appropriate to the configured login flow; do not assume sample values or an old token are valid.
- Webhooks: `META_APP_SECRET`, `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`; the HTTPS callback and required event fields must also be configured in Meta's dashboard.
- Safety flags: `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false` during development.

**Canva**
- `CANVA_CLIENT_ID`, `CANVA_CLIENT_SECRET`, `CANVA_REDIRECT_URI`, `CANVA_OAUTH_SCOPES`.
- Optional account-selection setting: `CANVA_ACCOUNT_KEY` (needed when a stable account key is absent from the token response or multiple accounts are stored).
- Register the exact HTTPS callback URI in the Canva developer app. OAuth tokens require the shared PostgreSQL store and encryption settings above.

**AI and image providers**
- Text provider: `AI_PROVIDER_ORDER` plus the credentials/model pair for at least one selected provider: `GEMINI_API_KEY`/`GEMINI_MODEL`, `GROQ_API_KEY`/`GROQ_MODEL`, optional `HF_TOKEN`/`HF_CHAT_MODEL`, or legacy `AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL`.
- Image generation is separate and optional for draft-only usage: `IMAGE_API_BASE_URL`, `IMAGE_API_KEY`, `IMAGE_MODEL`. Scheduled image publishing requires a compatible provider that returns publicly reachable HTTPS media URLs and suitable persistent media hosting where temporary URLs are insufficient.

**Scheduler and timezone**
- `NOVA_SCHEDULER_ENABLED=false` and `NOVA_TIMEZONE=Asia/Kolkata` are the development-safe settings.
- The scheduler also needs `DATABASE_URL`, a configured text provider, a working image provider/public media URL, an authorized professional Instagram account, the relevant approved permissions, and an always-on service or external scheduler. Render free instances may sleep and cannot guarantee exact-time execution.
- `INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED` is documented in README as an opt-in setting but is absent from `.env.example`; decide and document an explicit safe default before enabling it. `CANVA_ACCOUNT_KEY` is also an optional README-documented variable absent from the sample.
- `.env.example` and README describe different default `AI_PROVIDER_ORDER` values; reconcile documentation before treating either as the authoritative runtime default.
- Do not infer which variables are currently set in Render from `.env.example`. The actual private environment has not been inspected.

### Deployment readiness checklist
1. Confirm the Render service's build command, start command, Python runtime, health-check path, and current deployed commit in the Render dashboard.
2. Attach the intended persistent PostgreSQL database; verify connectivity without printing the connection string.
3. Set required secrets only in Render's private environment settings. Never commit them or paste them into chat.
4. Run the existing `python -m app.init_oauth_db` initialization against the confirmed database, then inspect logs/status for schema errors including the historical `UndefinedTable`.
5. Register exact HTTPS redirect/callback URLs and approved scopes in the Meta and Canva developer dashboards.
6. Verify read-only Instagram account access and Canva OAuth separately before considering write actions.
7. Keep all automation, scheduler, DM auto-reply, admin master, and direct-publish controls OFF until each dependency is verified and the user explicitly authorizes live operation.
8. Re-fetch `/health` and `/integrations/status` after deployment. Treat them as configuration/implementation diagnostics, not proof of provider permissions or successful publishing.

### Outstanding blockers / engineering follow-up
- Scheduler daily caps are now aligned at 0–20 in both admin validation and publisher logic (merged PR #126); this item is resolved.
- Validate `NOVA_TIMEZONE` at startup and expose scheduler readiness/error rather than silently suppressing invalid-zone failures.
- Add/document `INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED` with a safe default and reconcile the README/`.env.example` provider-order default.
- Identify and resolve the exact PostgreSQL table behind the previously reported token-refresh `UndefinedTable` before declaring refresh healthy.
- Live Render health, current deployment commit, current environment values, live Canva OAuth, and live Meta connection remain unverified. No deployment, environment mutation, live publish, or DM send was performed for this audit.


---

## Part 1 coordination update — 2026-11-01

- Shared coordination hub: [docs/THREE_CHAT_COORDINATION.md](THREE_CHAT_COORDINATION.md). Part 1 handoff is recorded there; Parts 2 and 3 should read the handoff notes before continuing.
- Latest inspected `main`: `9b8c331eb80a04a577d0fe5ed75f3d20999364ca`. Latest open-PR search returned **zero open PRs**.
- Latest verified application-code CI remains PR #126 head run [#41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475): **507 passed, 6 skipped, 40 warnings, 0 failed**. PR #126 merged as `d2e445be791ba36170946c2fc5d1f66bdfaad3f1`. This is PR-head CI evidence; a separate workflow on the merge commit/current main head was not independently returned. Current-main CI is therefore **NOT VERIFIED**. Historical main run #41295206264 on ancestor `48bbe70670dcbeaf2fd22ec2afa6e723d3bdb7f2` passed 503 tests with 6 skipped, but is not current-head evidence.
- Part 1 made no application-code changes. No live Instagram messaging, publishing, deployment, or external account action was performed.
- Handoff to Part 2: inspect the diverged `security/audit-scheduler-duplicate-safety` branch (5 commits ahead, 12 behind main) before reusing it; PR #126 already aligned the admin daily cap to the publisher's 20-item limit. Keep OAuth/live webhook behavior unverified and live-action flags OFF.
- Handoff to Part 3: reconcile the earlier timezone-validation/readiness diagnostic finding and direct Canva publishing bypass with current code. Keep live Canva connection and Render configuration/health unverified until directly tested.


### Part 1 follow-up — open PR inventory correction — 2026-11-01

- A subsequent final open-PR search found one open PR: [#127](https://github.com/francistheroo/nova-instagram-ai/pull/127), a documentation-only Part 3 Render verification follow-up.
- GitHub currently reports PR #127 as `mergeable=false`; its head is `5bb95e22e87208f611a289f9888a7f2eab85ff29`, based on `0f69c8b1bf1a603d6160e0a3883e874ec87138ef`. The main branch has advanced since that base because of Part 1 coordination/checkpoint updates. Part 3 should synchronize the branch and preserve both its Render findings and Part 1's checkpoint additions before merge.
- PR #127's documentation corrects the old daily-cap mismatch finding: current main has admin and publisher limits aligned at 0–20. It retains the unresolved invalid-`NOVA_TIMEZONE` startup/readiness diagnostic finding. No application code is changed by PR #127.
- Current-main CI remains **NOT VERIFIED**. PR #126 head CI is green (507 passed, 6 skipped, 40 warnings, 0 failed), but this is not a current-main merge-commit CI result.


### Part 1 latest follow-up — PR #128 status — 2026-11-01

- PR [#127](https://github.com/francistheroo/nova-instagram-ai/pull/127) was closed unmerged and replaced by [PR #128](https://github.com/francistheroo/nova-instagram-ai/pull/128), branch `docs/render-verification-followup`, head `afa1d2e5b5b5fca36524eb2008528a65da9186c6`.
- PR #128 is documentation-only and GitHub currently reports `mergeable=true`. Its compare against current main showed 1 commit ahead and 5 behind; its base is `670b1b082baa1e3e0704647f4911db7df495f1c0`, earlier than the latest Part 1 checkpoint updates. Part 3 should synchronize/review it against current main and preserve the latest Part 1 audit text before merge.
- Reviewed PR #128's diff: Render endpoints/deployed runtime remain unverified; the old admin-vs-scheduler daily-cap mismatch is corrected as obsolete (both are 0–20); invalid-`NOVA_TIMEZONE` startup/readiness diagnostics remain a follow-up.
- PR #128 head CI [run #41296728250](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296728250) completed successfully: **507 passed, 6 skipped, 40 warnings, 0 failed**. This is PR-head evidence only; current-main CI remains **NOT VERIFIED**.
- Final open-PR inventory at this check: PR #128 only. No live deployment, DM, or publishing action was performed.


---

## Part 2 coordination re-audit — 2026-11-01

- Reviewed current security and automation implementation on main (application-code audit base: `c552bd561a86f8078809c1fa48e01139b3776a51`). The three-chat coordination update was committed separately as `c1ea576aeadff07d4e9d4c8a5e12eb087787f639`.
- OAuth defaults to Instagram Login scopes `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, and `instagram_business_manage_messages`. OAuth start is admin-protected; callback uses a browser-bound secure cookie, signed 10-minute state, one-time persisted nonce, server-side code exchange, and encrypted token storage. Actual Creator-account permission grants, Meta app review/Advanced Access, and live OAuth remain unverified.
- Admin authentication uses configured HTTP Basic credentials with constant-time comparisons. The PostgreSQL master switch fails closed when the database is missing/unavailable. Sensitive action routes require admin auth and the NOVA API key where implemented.
- Instagram webhook verifies Meta HMAC signature, bounds bodies to 1 MiB, rejects malformed events, ignores echoes, and deduplicates stable message IDs. Auto-DM replies require the DM-specific flag, global automation flag, and database master switch all ON. Live webhook delivery remains unverified.
- DM memory stores per-message 12-hour expiry, excludes expired rows from reads, opportunistically deletes expired rows on reads/writes, and limits context to 30 messages. Physical deletion is lazy; API reads/writes require the NOVA API key and admin login; preview is additionally master-gated and draft-only.
- Scheduler startup is opt-in and requires PostgreSQL; runtime polls re-check scheduler/global automation flags and require the master switch plus `direct_publish_enabled=true`. Unique date/type/slot constraint, `ON CONFLICT DO NOTHING`, advisory locks, and `uncertain` outcomes protect against duplicate scheduled publishes. Stale processing attempts are not automatically retried.
- The old daily-cap mismatch finding is resolved: admin and publisher limits are both 0–20 in current main after PR #126. The old `security/audit-scheduler-duplicate-safety` branch is stale/diverged (5 ahead, 14 behind current main) and its admin-cap change/tests are already represented by PR #126; do not merge/reuse it.
- Current `.env.example` sets `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_SCHEDULER_ENABLED=false`; `NOVA_TIMEZONE=Asia/Kolkata`. Production Render values remain unverified.
- PR #127 was closed without merging; its documentation-only Render follow-up therefore did not update main. Current-main CI remains unverified; PR #126 head CI run #41296358475 passed 507 tests, 6 skipped, 40 warnings, 0 failures (PR-head evidence only).
- Handoffs: Part 1 should refresh PR #127 inventory and seek current-main CI evidence. Part 3 should address invalid `NOVA_TIMEZONE` startup/readiness validation and keep direct Canva publishing routes (which bypass per-item review) disabled. Live Meta OAuth/permissions, webhook delivery, Render configuration/health, and Canva connection remain unverified. No live messages/posts, deployment, or external setting changes were performed.


### Part 1 correction — PR #128 branch synchronization — 2026-11-01

- A fresh comparison against current main (`d154ca50db4dcd6f60207ad038625f08abbacb0e`) now reports PR #128 as **1 commit ahead / 10 commits behind**, diverged, with GitHub `mergeable=false`. This supersedes the earlier mergeable=true / 1-ahead-5-behind observation.
- PR #128 head remains `afa1d2e5b5b5fca36524eb2008528a65da9186c6`, based on `670b1b082baa1e3e0704647f4911db7df495f1c0`. Part 3 should rebase/update against current main, preserve all Part 1/Part 2 checkpoint and coordination additions, and rerun CI before merging.
- PR #128's existing successful run #41296728250 is on its current PR head and records **507 passed, 6 skipped, 40 warnings, 0 failed**; it does not verify a rebased head or current main.


## Render verification follow-up — 2026-11-01

- Attempted to retrieve the deployed public endpoints `https://nova-instagram-ai.onrender.com/health` and `https://nova-instagram-ai.onrender.com/integrations/status`. Both requests were inaccessible from the audit environment, so live Render status, deployed commit, and runtime configuration remain **UNVERIFIED**. This is not evidence that the service is down.
- Re-checked current source: `app/admin.py` validates both daily caps with `Field(ge=0, le=20)`; `app/auto_publisher.py` accepts integer caps from 0 through 20. The previously recorded daily-cap mismatch (admin accepts 50 vs scheduler 0–20) is **incorrect and superseded**; the current limits are aligned at 20.
- The timezone issue remains: `app/main.py:start_auto_publisher` starts the scheduler task without validating `NOVA_TIMEZONE`; `app/auto_publisher.py:scheduler_loop` constructs `ZoneInfo` inside its recurring loop. Invalid timezone configuration can therefore leave the scheduler task failing after startup without a clear startup readiness diagnostic. A focused code/test change is still needed.
- The historical token-refresh `UndefinedTable` report is not confirmed against the current deployed database. Do not run schema initialization or alter Render's database until its actual `DATABASE_URL` target and backup state are confirmed by the owner in the Render dashboard.
- No Render dashboard credentials or private environment values were available. No secrets were requested or exposed, no Render environment values were changed, no deploy was triggered, and publishing/DM automation remains in development-safe OFF posture.
- Next required live verification: inspect the Render service's latest deploy event and logs; confirm deployed commit, health-check path, runtime/build/start commands, and attached PostgreSQL database; then re-fetch both endpoints. Resolve any database error only after identifying the exact missing table and confirming the intended database.


---

## PR #128 CI and Render follow-up — 2026-11-01

- PR #128: https://github.com/francistheroo/nova-instagram-ai/pull/128
- Verified PR head at the time of CI run: `afa1d2e5b5b5fca36524eb2008528a65da9186c6`.
- GitHub Actions workflow run #355 (run ID `41296833074`) completed with conclusion `success`. Its `test` job and all reported steps, including dependency installation and test execution, completed successfully.
- PR #128 was still open and reported mergeable at verification time. No merge was performed.
- Re-attempted the public Render endpoints `/health` and `/integrations/status`; both remained inaccessible from the available web/runtime tools. The connected-browser session was unavailable, and no Render dashboard connector/session or dashboard credentials were available.
- Therefore the current Render deployment, deploy commit, service health, runtime logs, health-check configuration, attached database, and private environment settings remain **UNVERIFIED**. Endpoint retrieval failure is not proof that the service is down.
- No Render settings, secrets, database schema, or deployment were changed. No Instagram messaging or publishing was performed. Keep live actions disabled during development.
- To complete live verification, the owner must provide non-sensitive screenshots or copied text from the Render service's latest deploy event and logs, service settings (build/start/health-check configuration), and database attachment overview. Redact all environment values, connection strings, tokens, and credentials. Once those details are available, compare the deployed commit/configuration with the repository and retry the public endpoints.


---

## Part 2 production-readiness security hardening — 2026-11-01

- Current main base reviewed: `c18af6a32870ad40ceb6735b5c8a368bd7861c9f` (includes merged PR #128 Render documentation follow-up).
- Security finding: the legacy direct Canva photo and Reel endpoints (`app/canva_direct_post.py`, `app/canva_direct_publish.py`) could export from Canva and publish directly after general auth/automation gates, without the separate review/draft path. The one-step `/instagram/publish-image` endpoint also created and published in a single request without a review step.
- PR #130 branch `security/disable-canva-direct-publish-bypass` disables all three legacy one-step endpoints with HTTP 410, `published=false`, and `review_required=true`. API-key, admin and master-switch dependencies remain in place before the rejection response. Canva/Meta publishing code was removed from the direct Canva modules.
- Regression tests replace former success-path tests with assertions that direct Canva photo/Reel endpoints remain disabled even when `INSTAGRAM_AUTOMATION_ENABLED=true`, and add `tests/test_live_action_review_gates.py` to ensure the generic image publisher cannot call Meta.
- Latest PR #130 head: `c303eb5899201c3593879282b80b7f6c796d52b6`. PR is open and GitHub reports mergeable. Latest CI run [#41298815095](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41298815095) completed successfully on that exact head: **505 passed, 6 skipped, 40 warnings, 0 failed**; job `test` and all steps succeeded. Earlier run #41298463804 also passed on the preceding head.
- Other live-action route review: comment and DM replies require admin/API key/master/global automation flag; Reel and Canva draft publishing endpoints require explicit authenticated publish request, global automation/master gates and Meta `FINISHED` status; webhook auto replies require the DM-specific flag, global automation flag and DB master switch; scheduler has its independent gates. The draft publish flow does not persist a separate approval ledger; explicit authenticated publish request is the operator approval action for now.
- No live messages/posts, Canva/Meta API calls, OAuth, Render changes or deployment were attempted. Keep all live action flags OFF.
- Outstanding: PR #130 CI passed on latest head but remains open pending independent review/merge decision. Part 1's documentation PR #131 is now closed unmerged, and stale backup PR #129 is also closed unmerged. Part 1 should record these final dispositions in its coordination section and review PR #130. Part 3 has opened timezone/readiness PR #132 (head `fc587f4c1b58cc38d58e9dff58894e7e6943a3bc`); it remains open/non-mergeable and no workflow run was returned for the latest inspected head `fc587f4c1b58cc38d58e9dff58894e7e6943a3bc`. Its test/CI and Render review remain to be verified. PR #130 and #132 both touch `app/main.py`; coordinate merge order and re-check mergeability/rebase after the first merge. Overall production readiness is not complete until all three parts report evidence.


## Part 1 — PR #131 conflict recovery v3 — 2026-11-01

- Replacement PR #134 and its first resynchronization attempt became stale as `main` continued advancing. This documentation-only retry is based on the latest observed main snapshot `f25e908bba47ad23f297f8642b0f273b826d2ebe`.
- No application code, live settings, deployment, or external integration changed. Ancestor CI is not evidence for this branch; exact-head CI must be checked separately.
- Overall production readiness remains incomplete pending Parts 2 and 3.


---

## Part 3 scheduler timezone and Render readiness — updated 2026-11-01

- **Code merged:** PR #132 merged to main as `09d0e771236d9f989bc4b2db9ba294f7b6918e1e`; tested PR head `34edc8714dc31782cd415c498ffcb1a518502446`.
- `scheduler_timezone()` validates the IANA timezone at startup before schema initialization/task creation. An unset `NOVA_TIMEZONE` defaults to `Asia/Kolkata`; explicitly blank or invalid values fail closed with `invalid_timezone`. The validated ZoneInfo is passed into the scheduler loop.
- `GET /ready` returns HTTP 503 when the scheduler is enabled but timezone/database/task startup is invalid, and 200 when scheduler operation is intentionally disabled. `/health` remains liveness/status. Readiness does not prove Meta/Canva connectivity or continuously probe PostgreSQL.
- Regression coverage includes valid/default/invalid zones, blank/malformed values, fail-closed startup, no schema initialization on invalid timezone, scheduler-loop validation, and readiness behavior.
- PR #132 exact latest code-head CI [#41299392975](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299392975): **513 passed, 6 skipped, 40 warnings, 0 failed**. Latest main `aff87fd67d6feb0d2d1b0a29c48acc41fcfbffd8` CI [#41299632332](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299632332): **513 passed, 6 skipped, 40 warnings, 0 failed**.
- Render repository review: no root `render.yaml` or `Dockerfile`; `requirements.txt` exists. Suggested commands only: `pip install -r requirements.txt` and `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Actual Render Dashboard settings, deployed commit, logs, health-check path, database attachment, and private env values remain **NOT VERIFIED**.
- Render official HTTP checks use GET and accept 2xx/3xx within five seconds; private services use TCP; TCP is the default if no HTTP path is configured. See [Render health checks](https://render.com/docs/health-checks). Use `/ready` when scheduler readiness is required before traffic; use `/health` for liveness only.
- Part 2 PR #130 merged as `cbf9a2fc7ad8c5c2888916060d81752873967b4b`. Part 1 PR #137 is closed unmerged; replacement branch `part1/pr131-conflict-fix-v4` has no unique commits and is 19 commits behind current main. Workflow [#41299562250](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299562250) passed **505 passed, 6 skipped, 40 warnings, 0 failed** on its branch head, but that branch contains no unique changes versus main and is not a new deliverable. No open Part 1 PR was found; the Part 1 section in the coordination hub still needs its owner to reconcile historical entries. No Part 1 branch was changed in this pass.
- Part 3 documentation PR #135 is synchronized at `47de3ffa814239468f38c101840280c547adf2d9`; exact-head CI [#41299803932](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299803932) passed **513 passed, 6 skipped, 40 warnings, 0 failed**. PR is mergeable and remains open pending merge decision. No Render settings, secrets, database, or deployment were changed. No live Instagram, Meta, or Canva requests were made. Keep all live switches OFF; overall readiness remains NOT COMPLETE pending Part 1 handoff and live Render evidence.


---

## Part 1 final conflict recovery and CI handoff — 2026-11-01

- PR #139 merged successfully as `aff87fd67d6feb0d2d1b0a29c48acc41fcfbffd8`. The three documentation files now retain the v3 Part 1 recovery record and replace the stale v2 note.
- Current main is `aff87fd67d6feb0d2d1b0a29c48acc41fcfbffd8`; main CI [#41299632332](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299632332) passed **513 passed, 6 skipped, 40 warnings, 0 failed**.
- Part 2 PR #130 and Part 3 scheduler implementation PR #132 are merged. Part 3 documentation PR #135 remains open, documentation-only, 10 ahead/0 behind, mergeable, with successful exact-head CI [#41299803932](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41299803932).
- No Render settings, secrets, database, deployment, OAuth, Meta/Canva calls, Instagram messages or posts were changed or attempted. Render dashboard/runtime evidence remains **NOT VERIFIED**; end-to-end production readiness is therefore **NOT COMPLETE**.
- Development live-action switches remain OFF.
