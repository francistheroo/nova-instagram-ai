# NOVA — Three-Chat Coordination Hub

**Purpose:** Shared handoff point for the three NOVA development chats. Read this file before starting work and update your own section when work changes.

- Repository: https://github.com/francistheroo/nova-instagram-ai
- Default branch: `main`
- Current baseline when this hub was created: `2270b2cecaa0ce89431652bfa2d4f114dab5dfa7`
- Master recovery checkpoint: [docs/NOVA_RECOVERY_CHECKPOINT.md](NOVA_RECOVERY_CHECKPOINT.md)
- Test-results checkpoint: [docs/TEST_RESULTS_CHECKPOINT.md](TEST_RESULTS_CHECKPOINT.md)

> **Important communication limitation:** Separate ChatGPT conversations do not automatically send messages to one another. This file is the shared handoff channel. Each chat must read it at the start of a task and write its findings here before handing work to another chat.

## Shared operating rules

1. Fetch the latest `main` before making decisions or changes. The baseline SHA above is historical, not a permanent branch target.
2. Do not overwrite another part's section. Edit only your own section and append dated handoff notes.
3. If two chats update this file at the same time and GitHub rejects a stale update, fetch the latest version, preserve both sets of notes, and retry. Never discard another chat's update.
4. Prefer focused branches and pull requests for code changes. Do not merge unrelated work just to synchronize chats.
5. Report exact branch names, commit SHAs, PR numbers, test commands and CI run URLs where available.
6. Distinguish **verified**, **not verified**, **blocked** and **not attempted**. Empty CI results are not a passing CI result.
7. Do not expose secrets, tokens, OAuth codes, passwords, private environment values or personal data in this file.
8. Keep live Instagram messaging and publishing disabled during development. Never trigger real messages or posts as a test.
9. Do not claim Render health, OAuth connection, Canva access, webhook delivery or Instagram publishing is live unless directly verified.
10. Update the master recovery checkpoint when a meaningful milestone is completed. Link to this coordination hub from handoff notes when useful.

## Work division

### Part 1 — GitHub, pull requests and CI

**Owner:** Chat / Part 1

Tasks:
- Inspect latest `main`, open PRs and recent commits.
- Review code changes, conflicts and failing tests.
- Fix appropriate issues without duplicating Parts 2 or 3.
- Run relevant tests and verify GitHub CI.
- Record PR/commit/test/CI evidence and update the recovery checkpoint.

**Current status:** COMPLETE — Part 1 audit and handoffs recorded. One open Part 3 documentation PR (#128) remains under Part 3 ownership; current-main CI is not independently verified.

**Latest update / handoff — 2026-11-01:**
- Latest application/security code commit inspected at `9b8c331eb80a04a577d0fe5ed75f3d20999364ca` (`Document live-action gates in NOVA security checkpoint`); subsequent Part 1 commits on main update only coordination/recovery documentation.
- Final open PR search found one open PR: [#128](https://github.com/francistheroo/nova-instagram-ai/pull/128), a Part 3 documentation-only Render verification follow-up. PR #127 was closed unmerged and replaced by #128. PR #128 targets main, is currently reported `mergeable=false`; compare shows its branch is 1 commit ahead and 10 behind current main. It is based on `670b1b082baa1e3e0704647f4911db7df495f1c0`, not the latest main. PRs #122–#126 and #113 are closed/merged. Part 1 did not merge or close any PR.
- Latest verified application-code CI remains PR #126 head run [#41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475): **507 passed, 6 skipped, 40 warnings, 0 failed**. PR #126 merge commit is `d2e445be791ba36170946c2fc5d1f66bdfaad3f1`. A separate CI run on the current main head/merge commit was not returned by the available commit-run lookup; combined commit status for current main returned no status entries. Therefore current-main CI is **NOT VERIFIED**, not PASS. The earlier main run #41295206264 (503 passed, 6 skipped) is historical evidence on ancestor `48bbe70670dcbeaf2fd22ec2afa6e723d3bdb7f2`, not the current main head.
- PR #128 is documentation-only and GitHub currently reports `mergeable=true`; its branch is 1 ahead/5 behind current main. Its CI run #41296728250 passed **507 tests, 6 skipped, 40 warnings, 0 failed**. No open application-code PRs or failing test runs were found. Part 1 made no application-code changes.
- Branch hygiene: `fix/validate-scheduler-settings-current-main` is 34 commits behind main with no unique commits; `security/audit-scheduler-duplicate-safety` is diverged (5 ahead, 14 behind per Part 2's later branch comparison) and modifies `app/admin.py` plus scheduler tests. Do not merge either branch without a fresh focused review/rebase. The former rebased scheduler branch is stale; duplicate test definitions observed there are not in main.
- **Handoff to Part 2:** Please inspect `security/audit-scheduler-duplicate-safety` before reusing or deleting it. It is 5 ahead/14 behind main per Part 2's fresh comparison and contains changes to `app/admin.py`, `tests/test_scheduler_admin_limits.py`, and `tests/test_scheduler_duplicate_claim.py`; PR #126 has already merged the admin cap alignment, so avoid duplicating that fix. Part 2 has since re-reviewed the branch and confirms its cap changes/tests are already represented on main; do not reuse it. Also keep all live-action gates OFF; current repository documentation requires `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_SCHEDULER_ENABLED=false` during development. OAuth, real permissions, and live webhook delivery remain unverified.
- **Handoff to Part 3:** Please reconcile the Part 3 audit notes in `docs/NOVA_RECOVERY_CHECKPOINT.md` with current main. The audit records an invalid-`NOVA_TIMEZONE` startup/readiness diagnostic gap and a direct Canva publishing bypass that must remain disabled; confirm whether either has since been addressed before changing integration/deployment status. Keep Canva live connection and Render environment/health marked unverified unless directly checked.
- Master recovery checkpoint and test-results checkpoint should continue to distinguish PR-head CI from merge-commit/main CI. See latest Part 1 record in `docs/TEST_RESULTS_CHECKPOINT.md`.

### Part 2 — Instagram security and automation

**Owner:** Chat / Part 2

Tasks:
- Audit Creator-account OAuth scopes, permissions and token handling.
- Verify admin-only authentication and global automation master switch.
- Review webhook security and 12-hour DM conversation-memory expiry.
- Audit scheduler safety, duplicate prevention and uncertain publish outcomes.
- Keep live messaging and publishing disabled throughout development.

**Current status:** COMPLETE for this coordination cycle — current-main security and automation paths re-reviewed. No new application-code changes were needed.

**Latest update / handoff — 2026-11-01:**
- Re-verified current `main` at `c552bd561a86f8078809c1fa48e01139b3776a51`. This is the latest commit returned by the current-main coordination/recovery checkpoint inspection.
- **OAuth:** `app/instagram_oauth.py` requests the configured Instagram Login scopes (default: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, `instagram_business_manage_messages`). OAuth start is admin-protected; callback is intentionally public for Meta's redirect but requires matching HttpOnly/Secure/SameSite=Lax browser cookie, signed short-lived state (10 minutes), one-time persisted nonce consumption, server-side code exchange, and encrypted token storage. Refresh requires admin login and NOVA API key. Actual Creator-account grants, Meta app review/Advanced Access and live OAuth remain **NOT VERIFIED**.
- **Authentication/master switch:** `app/security.py` validates HTTP Basic credentials against `NOVA_ADMIN_USERNAME`/`NOVA_ADMIN_PASSWORD` using constant-time comparisons. Sensitive actions also require the NOVA API key where implemented. The PostgreSQL master switch returns OFF when the database is absent/unavailable; `require_master_enabled` fails closed.
- **Webhook:** `app/instagram_webhook.py` validates Meta's `X-Hub-Signature-256`, bounds request bodies to 1 MiB, rejects malformed/unsupported payloads, ignores echoes, requires stable message IDs for reply retry claims, and deduplicates inbound events. Automatic replies require all three flags: `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=true`, `INSTAGRAM_AUTOMATION_ENABLED=true`, and the database master switch ON. Live webhook delivery is **NOT VERIFIED**.
- **DM memory:** `app/dm_memory.py` sets per-message expiry to exactly 12 hours from insertion, excludes expired rows from reads, opportunistically deletes expired rows on reads/writes, and caps context at 30 messages. Memory read/write/clear routes require the NOVA API key and admin login; preview additionally requires the master switch and is draft-only. Physical deletion is lazy, not guaranteed at the exact expiry instant.
- **Scheduler:** `app/auto_publisher.py` is opt-in at startup (scheduler flag plus database), re-checks scheduler and global automation flags each poll, and requires the master switch plus `direct_publish_enabled=true` before scheduled publishing. PostgreSQL unique `(local_date, content_type, slot)` and `ON CONFLICT DO NOTHING` prevent duplicate slot claims; advisory locks serialize daily-cap checks. Ambiguous Meta publish outcomes and stale processing rows become `uncertain` and are not automatically retried.
- **Daily-cap correction:** current `app/admin.py` and `app/auto_publisher.py` both cap posts/Stories at 20; PR #126 merged this alignment and both regression tests are present on main. The prior Part 3 checkpoint's 50-vs-20 mismatch is superseded.
- **Stale branch review:** `security/audit-scheduler-duplicate-safety` is diverged from current main (5 commits ahead, 14 behind; merge base `2270b2cecaa0ce89431652bfa2d4f114dab5dfa7`). Its admin-cap change and tests are already represented by merged PR #126/current main. Do not merge or reuse this stale branch; no additional code changes were required from it.
- **Development posture:** current `.env.example` sets `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, `NOVA_SCHEDULER_ENABLED=false`, and `NOVA_TIMEZONE=Asia/Kolkata`. Admin defaults are master OFF and direct publishing OFF. Production Render values were not accessed and remain **NOT VERIFIED**.
- **CI:** prior PR #126 head run [#41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475) passed **507 passed, 6 skipped, 40 warnings, 0 failed**. No new tests were run in this coordination pass, and current-main CI is **NOT VERIFIED**; do not conflate PR-head CI with current-main CI.
- **Part 1 handoff:** Part 1 has refreshed the PR inventory: PR #127 is closed unmerged and replaced by open documentation-only PR #128 (Part 3 ownership). A fresh direct PR lookup reports #128 as open and `mergeable=false`; reconcile this with the inconsistent mergeability statements in the Part 1 section/log. Current-main CI remains unverified. No Part 2 security code change is outstanding.
- **Part 3 handoff:** timezone readiness validation remains unresolved: `app/main.py:start_auto_publisher` starts the task without validating `NOVA_TIMEZONE`, and `app/auto_publisher.py:scheduler_loop` constructs `ZoneInfo` inside its recurring loop. Please handle a focused validation/readiness fix and tests. Direct Canva routes `app/canva_direct_post.py` and `app/canva_direct_publish.py` still bypass per-item review and must remain disabled during development; retain all action gates OFF. PR #127 was closed unmerged and replaced by open documentation-only PR #128; a fresh direct lookup reports #128 `mergeable=false`. Part 3 should synchronize it without losing Part 1 checkpoint updates. Live Render and Canva status remain unverified.
- No live Instagram messages/posts, OAuth flow, webhook delivery, Render changes, or deployment were attempted in this pass.

### Part 3 — Integrations, scheduling and deployment

**Owner:** Chat / Part 3

Tasks:
- Audit Canva integration and review-before-publish flow.
- Verify scheduler configuration and `Asia/Kolkata` timezone behavior.
- Review Render deployment and health-check readiness.
- Identify missing configuration without copying secret values.
- Update the master recovery checkpoint with evidence and outstanding deployment requirements.

**Current status:** NOT STARTED for this coordination cycle.

**Latest update / handoff:**
- Previous known result: PR #124 updated the master recovery checkpoint for Canva, scheduler and Render audit. Re-read the current checkpoint and verify the implementation before repeating work.
- Do not infer live Render readiness from repository configuration alone.

## Shared handoff log

Add new entries at the top. Use this format:

### 2026-11-01 — Part 1 — PR #128 follow-up handoff

- **Status:** VERIFIED — documentation diff reviewed; PR-head CI passed. Current-main CI remains NOT VERIFIED.
- **Branch / PR:** `docs/render-verification-followup`, [PR #128](https://github.com/francistheroo/nova-instagram-ai/pull/128), open, documentation-only, GitHub `mergeable=true`.
- **Commit SHA:** PR head `afa1d2e5b5b5fca36524eb2008528a65da9186c6`; base `670b1b082baa1e3e0704647f4911db7df495f1c0`; current main at audit read `6437f7d04286f745feba90c42cf73819dcba4b19`.
- **Changes made:** No PR changes by Part 1. Reviewed PR #128's one-file diff in `docs/NOVA_RECOVERY_CHECKPOINT.md`; it accurately marks Render endpoints/runtime unverified, corrects the obsolete daily-cap mismatch (both limits 0–20), and retains the timezone readiness follow-up. PR #127 is closed unmerged.
- **Tests run and results:** PR #128 CI [run #41296728250](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296728250): **507 passed, 6 skipped, 40 warnings, 0 failed**.
- **CI evidence:** PR-head CI only; current main combined status had no entries and no current-main workflow run was returned.
- **Risks or blockers:** PR #128 is 1 commit ahead/5 behind current main despite GitHub reporting mergeable; its base predates the latest Part 1 checkpoint edits in the same recovery file.
- **Next part / requested action:** Part 3: rebase/update PR #128 against current main or verify the merge preserves the latest Part 1 section before merging. Address timezone startup validation in a separate code/test PR. Part 2: update its section in this hub when its security audit is complete.

### 2026-11-01 — Part 2 — current-main security and automation re-audit

- **Status:** VERIFIED for repository code/configuration review; external Meta/Render behavior NOT VERIFIED.
- **Branch / PR:** Reviewed `main`; no new PR or application-code change. Inspected stale `security/audit-scheduler-duplicate-safety` (5 ahead/14 behind); do not reuse. PR #126 is merged; PR #127 is closed unmerged and replaced by open documentation-only PR #128 (Part 3; direct lookup reports `mergeable=false`).
- **Commit SHA:** Current-main base `c552bd561a86f8078809c1fa48e01139b3776a51`; PR #126 merge `d2e445be791ba36170946c2fc5d1f66bdfaad3f1`.
- **Changes made:** Updated only Part 2's section in this hub with current OAuth, auth/master-switch, webhook, DM TTL, scheduler and branch findings. No application code changed.
- **Tests run and results:** No new tests run in this pass. PR #126 head CI run #41296358475 remains verified at 507 passed, 6 skipped, 40 warnings, 0 failures.
- **CI evidence:** [PR #126 run #41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475). Current-main CI NOT VERIFIED.
- **Risks or blockers:** Real Creator OAuth permissions and webhook delivery unverified; Render flags/health unverified; invalid timezone readiness diagnostic remains unresolved; direct Canva publish routes bypass per-item review and must remain disabled. Expired DM rows are physically deleted opportunistically rather than exactly at expiry.
- **Next part / requested action:** Part 1 has refreshed PR inventory; PR #128 is the current open Part 3 docs PR, but direct GitHub lookup reports `mergeable=false`. Current-main CI remains unverified. Part 3: fix timezone startup/readiness validation in a focused code/test PR; synchronize PR #128 without losing Part 1 checkpoint edits; keep direct Canva routes disabled and verify Render/Canva only with authorized evidence.

### 2026-11-01 — Part 1 — main/PR/CI audit and cross-part handoff

- **Status:** VERIFIED for repository inventory and prior PR-head CI; current-main CI NOT VERIFIED.
- **Branch / PR:** `main`; one open PR [#127](https://github.com/francistheroo/nova-instagram-ai/pull/127), Part 3 docs-only Render follow-up, currently reported `mergeable=false`.
- **Commit SHA:** inspected main `9b8c331eb80a04a577d0fe5ed75f3d20999364ca`; Part 1 coordination commit `0f69c8b1bf1a603d6160e0a3883e874ec87138ef`; Part 1 recovery-checkpoint commit `c552bd561a86f8078809c1fa48e01139b3776a51`.
- **Changes made:** Updated only Part 1's section in this hub and appended the Part 1 audit to `docs/NOVA_RECOVERY_CHECKPOINT.md`; no application code changed.
- **Tests run and results:** No new local tests run; latest verified PR #126 head CI remains 507 passed, 6 skipped, 40 warnings, 0 failed.
- **CI evidence:** [PR #126 run #41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475). Current main combined status had no entries and the commit-workflow lookup returned no runs; do not call current main CI passed.
- **Risks or blockers:** PR #127 is reported not mergeable and must be synchronized with current main. Timezone startup validation gap remains per its diff. Current main has no open code PRs other than this documentation follow-up. Live integrations are not verified.
- **Next part / requested action:** Part 2: review the diverged scheduler/security branch before reuse. Part 3: sync PR #127, correct its base conflict without dropping Part 1 checkpoint content, and handle timezone validation in a separate focused code/test PR. Both parts must update their own sections here before claiming completion.

### YYYY-MM-DD HH:MM IST — Part N — short subject

- **Status:** VERIFIED / NOT VERIFIED / BLOCKED / NOT ATTEMPTED
- **Branch / PR:**
- **Commit SHA:**
- **Changes made:**
- **Tests run and results:**
- **CI evidence:**
- **Risks or blockers:**
- **Next part / requested action:**

---

## Final integration checklist

- [ ] Part 1 has reviewed current main, open PRs, tests and CI evidence.
- [ ] Part 2 has completed the security and automation audit.
- [ ] Part 3 has completed the integration, scheduler and deployment audit.
- [ ] Cross-part conflicts and duplicate work have been resolved.
- [ ] Live messaging and publishing remain disabled during development.
- [ ] Master recovery checkpoint reflects verified results and outstanding work.
- [ ] All three parts have posted a final handoff in this file.

### 2026-11-01 — Part 1 — production-readiness cycle kickoff audit

- **Status:** VERIFIED for PR #128 synchronization/merge and final-main CI; open PR #129 reviewed and flagged as stale backup, not suitable for merge. Part 1 remains active for cross-part handoffs.
- **Main commit:** c18af6a32870ad40ceb6735b5c8a368bd7861c9f (PR #128 merge).
- **PR #128:** already merged, merge commit c18af6a32870ad40ceb6735b5c8a368bd7861c9f; rebased head 7ac3aee40ba4de7f852ae2643a7d38db4a9a49b6 was conflict-free against base 945e221a57e2e36e29d6aa1ca23208082686f856. [PR #128](https://github.com/francistheroo/nova-instagram-ai/pull/128).
- **Current-main CI:** PASS — [run #41297515819](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41297515819), push workflow on exact main merge commit c18af6a32870ad40ceb6735b5c8a368bd7861c9f; job test successful; logs confirm **507 passed, 6 skipped, 40 warnings, 0 failed**. All job steps completed.
- **Open PR inventory:** only [PR #129](https://github.com/francistheroo/nova-instagram-ai/pull/129), “Backup/pr 113 before rebase”, was returned. It is a backup/archival branch, not a current feature PR: head d551cf6c11f733f954cebbbd7c3ee38374328e14, **4 ahead / 66 behind** main, diverged from merge base 77108de70fbed276ba8fdd360c3d33fb4e0490bd; no workflow runs are associated with its head. Its scheduler validation and stale-processing changes overlap current-main implementation/tests, but branch files differ because it is far behind. Do not merge or rebase this backup branch as a production PR. Recommend closing PR #129 as an archival backup after owner confirmation; preserve its branch if needed as a recovery reference.
- **Changes made by Part 1:** documentation-only update on branch part1/production-readiness-audit; no application code, secrets, Render settings, or live integrations changed.
- **Cross-part handoffs:** Part 2: supply this cycle's review evidence for Canva direct-publish bypass protections and regression tests; Part 3: supply this cycle's NOVA_TIMEZONE startup/readiness fix, tests, and Render readiness evidence. Keep all live flags and admin publish gates OFF. The coordination file's prior Part 3 status says NOT STARTED and must be updated by Part 3 with current evidence.
- **Outstanding:** overall production-readiness cycle is NOT COMPLETE until Parts 2 and 3 provide evidence and shared handoffs are reconciled. Render, Meta OAuth, Canva live connection, and live publishing remain unverified.
