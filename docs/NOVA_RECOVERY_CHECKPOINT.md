# NOVA Instagram AI — Recovery Checkpoint
Updated: 2026-10-29 (verified against GitHub main)

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

## Existing milestones (verify before relying on them)
- PRs #1–#27 cover FastAPI starter, CI, OAuth, Canva, guarded publishing, status, AI caption drafts/content ideas, and Content Studio.
- PR #29: webhook ingestion and 12-hour DM memory.
- PR #30: opt-in DM auto-replies within the standard 24-hour messaging window; default off.
- PRs #31/#32: duplicate message-memory protection and tests.
- PR #34 was merged on 2026-10-28. Its merged commit is `b77850006b0e4f3b9b55a8edf5ffc24148b0ae3d`. It added the database-backed retry-state helper foundation to `app/dm_memory.py`, but it did NOT integrate those helpers into the webhook. The merged PR's own description explicitly says integration remains unfinished.
- Verified current `main`: `app/dm_memory.py` has `claim_dm_event` and `finish_dm_event`; `app/instagram_webhook.py` still imports only `store_dm_message` and `generate_dm_reply` and does not use the event-state helpers.
- The event-state schema on main allows only `processing`, `sent`, and `retryable`; it does not include `ignored`. Do not assume the newer unmerged draft integration code is on main.
- Latest check for PR #34's merged head workflow lookup returned no workflow runs; earlier helper-only CI was reported successful, but it does not validate webhook integration.
- Open tracking issue #33: https://github.com/francistheroo/nova-instagram-ai/issues/33

## Current next work — draft PR #35
- URL: https://github.com/francistheroo/nova-instagram-ai/pull/35
- Branch: `feature/webhook-dm-retries`
- Head commit: `51bec9e05e5a5248b4a64f2c846cc9a3f4b5299d`
- Open draft, not merged/deployed. Initial CI lookup returned no workflow runs yet; check again before claiming tests passed.
- Current branch changes integrate claim/finish state in the webhook, add `ignored` as a terminal state with a DB constraint migration, and add a regression test for retry after AI failure even when the inbound message is already stored.
- Duplicate idempotency test now mocks claim rejection. More tests are still needed.

## Remaining work for PR #35
1. Check the latest workflow run for exact head SHA and fix failures; no CI pass is confirmed yet.
2. Review and expand retry tests for Meta API failure, successful send, expired lease reclaim, duplicate/concurrent delivery, out-of-window and invalid timestamps, and missing IDs.
3. Integrate `claim_dm_event` / `finish_dm_event` carefully:
   - Claim before processing messages that have a Meta `mid`.
   - Handle a retryable event whose user message is already in DM memory; don't let memory dedup block retry.
   - Mark successful Meta sends `sent`.
   - Mark transient AI/Meta failures `retryable`.
   - Mark out-of-window or invalid-timestamp events terminal only after adding a supported terminal status/schema migration, or leave them retryable with a deliberate documented policy.
   - Handle missing message IDs safely and keep auto-replies opt-in.
   - Consider database failures and send timeouts; exactly-once delivery cannot be guaranteed if Meta accepts a send but the response is lost.
4. Mock tests are not proof of real PostgreSQL concurrency; add database-backed tests if the project has a safe test database.
5. Keep PR #35 draft until tests and schema are reviewed. Do not merge or deploy without user authorization.

## User workflow
The user often says “Next” to request the next incremental step. Make actual repository progress and report exact state; avoid generic advice. If a new chat starts, verify GitHub before trusting this checkpoint.
