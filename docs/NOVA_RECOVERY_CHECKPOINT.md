# NOVA Instagram AI — Recovery Checkpoint
Updated: 2026-10-29

## Project
- GitHub repository: https://github.com/francistheroo/nova-instagram-ai
- Render service URL: https://nova-instagram-ai.onrender.com
- Goal: NOVA, an Instagram AI assistant with natural chat/personality, Manglish Malayalam + English, caption/content ideas, supported Instagram publishing and messaging, Canva integration, and short-lived DM context.
- Instagram account type: Creator. Canva plan: Free.

## Safety and operating rules
- Do not request or paste API keys, passwords, access tokens, or secrets into chat.
- Do not enable live DM auto-replies, publish, deploy, merge a PR, or change Meta settings without explicit user authorization.
- `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false` by default. Keep it disabled during development.
- Use supported official Meta APIs only. No private endpoints, browser automation, cold DMs, or unsolicited bulk messaging.
- Meta does not provide standard APIs for Instagram Notes/music or standard auto-like/follow/follow-back. DM access depends on permissions and conversation eligibility.
- Do not claim live Meta behavior works unless it has been verified.

## Existing project milestones (verify current main branch before relying on them)
- PR #1: FastAPI starter and guarded routes.
- PR #2/#3/#5: CI, import-path fix, health flags.
- PR #6: Meta OAuth docs.
- PR #9/#10: Instagram OAuth and manual token refresh.
- PR #12/#13/#15: Canva OAuth, design/export APIs, token refresh.
- PR #16: Canva-to-Instagram draft export review gate.
- PR #18/#20: guarded Reel workflow and direct Canva Reel publishing (no music).
- PR #21: Canva photo publishing.
- PR #23: integration status diagnostics.
- PR #24/#25/#26/#27: AI caption drafts, content ideas, newline fix, draft Content Studio UI.
- PR #29: webhook ingestion and 12-hour DM memory. Database uses PostgreSQL via DATABASE_URL; schema initialized with `python -m app.init_oauth_db`.
- PR #30: opt-in DM auto-replies with 12-hour context and standard 24-hour messaging window. Auto-replies default off.
- PR #31/#32: webhook duplicate-event protection and follow-up test mock fix. PR #32 CI was reported successful.

## Current work — draft PR #34
- URL: https://github.com/francistheroo/nova-instagram-ai/pull/34
- Branch: `feature/dm-retry-state`
- Title: “Add database-backed DM event retry state foundation”
- PR #34 is open and draft; do not assume merged.
- Branch changes currently include:
  - `app/dm_memory.py`: PostgreSQL `nova_instagram_dm_events` state table with `processing`, `sent`, `retryable`, `ignored` states; atomic claim with lease expiry; finish helper.
  - `app/instagram_webhook.py`: integration of claim/finish helpers into webhook, recording sent/retryable outcomes and ignoring out-of-window messages.
  - `tests/test_dm_event_state.py`: initial mocked unit tests for claim helpers.
  - `tests/test_webhook_idempotency.py`: mocks for duplicate claims.
  - `README.md`: migration/behavior caveat.
- Important: latest integration commit at checkpoint was `2274af5e731a99158f467258ca1825baf83d3e3b` (README update). CI lookup for this latest commit returned no runs. Earlier helper-only commit `4ad72d2c406f3cd488baad7f626d7a7950d1e0b0` had a successful test run #66, but that does NOT validate the later integration.
- Need inspect current branch/PR and latest CI before doing more. Run the test workflow after the latest commit; if no run appears, use the GitHub UI/connector to inspect why.
- Do not merge PR #34 until:
  1. Latest CI passes.
  2. Tests cover success, duplicate delivery, retry after AI failure, retry after Meta failure, expired lease reclaim, concurrent claims, and terminal ignored events.
  3. Review that a claimed event is always marked appropriately, no path strands it unnecessarily, and the schema migration works against PostgreSQL.
  4. Check all modified test mocks match the new webhook behavior.
  5. Be transparent that exactly-once sending cannot be guaranteed if Meta accepts a send but the response is lost.
- Issue #33 tracks safe DM retries: https://github.com/francistheroo/nova-instagram-ai/issues/33
- Nothing in this work has been deployed or merged as part of PR #34; do not enable auto-replies.

## User preferences and interaction
- User usually advances work by saying “Next”. Continue with real incremental work and report exact status, not generic suggestions.
- User appreciates concise checkpoints because chat history may be lost.
- User’s broader AIOS Linux project is separate and not part of this NOVA task.

## First action in a new chat
1. Verify repository main and PR #34 state/head SHA.
2. Check workflow runs for the exact latest head SHA.
3. Read current `app/instagram_webhook.py`, `app/dm_memory.py`, and relevant tests from the PR branch.
4. Continue from actual current repository state, not this checkpoint if GitHub differs.
