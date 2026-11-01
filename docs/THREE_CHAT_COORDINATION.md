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
- Audit all live-action gates and authorization.
- Disable direct Canva publishing paths that bypass the reviewed draft flow.
- Add regression tests proving direct publish routes cannot call Canva or Meta.
- Keep all live messaging and publishing disabled during development.

**Current status:** CODE AND PR CI VERIFIED — focused hardening PR #130 is open for review. Direct Canva photo/Reel routes and the legacy one-step image publisher are disabled in the branch; do not mark the full three-part cycle complete yet.

**Latest update / handoff — 2026-11-01:**
- Re-read the coordination hub on current main and audited current main commit `c18af6a32870ad40ceb6735b5c8a368bd7861c9f`. PR #128 has since merged as that commit; the old coordination text elsewhere in this hub still contains stale PR #128 open/conflict statements. Part 1's documentation PR [#131](https://github.com/francistheroo/nova-instagram-ai/pull/131) is now closed unmerged; stale backup PR [#129](https://github.com/francistheroo/nova-instagram-ai/pull/129) is also closed unmerged. Part 1's audit evidence exists in the PR/checkpoint, but its coordination section remains stale. Please update your hub section and review PR #130.
- **Direct Canva bypass found:** `app/canva_direct_post.py` and `app/canva_direct_publish.py` previously called Canva export and Meta `media_publish` directly after general flag, NOVA API key, admin and DB master checks; they did not enforce the separate review/draft flow. This allowed a direct Canva publish without review.
- **Additional direct image bypass found:** `app/main.py:/instagram/publish-image` also created and published a media container in one request after authorization/feature gates, without an explicit draft/review step.
- **Hardening in PR #130:** branch `security/disable-canva-direct-publish-bypass`, PR [#130](https://github.com/francistheroo/nova-instagram-ai/pull/130). The two legacy Canva routes now return HTTP 410 with `review_required=true` and `published=false`; their external Canva/Meta publishing logic has been removed. The generic one-step `/instagram/publish-image` route also returns HTTP 410. All retain API-key, admin and master-switch dependencies before returning the disabled response. No external calls can be made through these legacy routes.
- **Regression coverage:** updated `tests/test_canva_direct_post.py` and `tests/test_canva_direct_publish.py` to assert permanent HTTP 410 even when `INSTAGRAM_AUTOMATION_ENABLED=true`, while keeping admin/master authorization tests. Added `tests/test_live_action_review_gates.py` to prove the generic one-step image route rejects publication and never calls Meta.
- **Other live-action routes reviewed:** comment replies, DM replies, generic Reel publish, Canva photo publish and Canva Reel draft/publish actions require admin authentication, NOVA API key, DB master switch and global automation flag (where the route sends/publishes). Reel/photo publish routes also check Meta container `FINISHED` before `media_publish`. Webhook auto-replies retain their DM-specific flag + global automation flag + master switch. Scheduler has its independent scheduler flag, global flag, DB master and `direct_publish_enabled` gate.
- **Review-flow limitation:** publish endpoints in the draft flow are explicit authenticated admin actions after draft/status inspection, but the code does not maintain a separate durable per-item approval ledger. Treat the explicit publish request as the operator's approval; a formal approval record/audit trail is a future hardening item if stronger workflow proof is required.
- **PR/CI:** PR #130 is open and currently reports mergeable. Latest head `c303eb5899201c3593879282b80b7f6c796d52b6`. Latest GitHub Actions run [#41298815095](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41298815095) completed successfully: job `test` passed, **505 passed, 6 skipped, 40 warnings, 0 failed**. All workflow steps completed. Earlier run #41298463804 also passed on the preceding head. No local test execution was available in this pass.
- **Files changed on branch (6):** `app/canva_direct_post.py`, `app/canva_direct_publish.py`, `app/main.py`, `tests/test_canva_direct_post.py`, `tests/test_canva_direct_publish.py`, `tests/test_live_action_review_gates.py`. Compare to current main shows 8 commits ahead / 3 behind due to later documentation commits; GitHub reports PR #130 mergeable.
- **Development posture:** do not enable `INSTAGRAM_AUTOMATION_ENABLED`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED`, `NOVA_SCHEDULER_ENABLED`, or any direct-publish setting during development. No real Instagram messages/posts, Canva API calls, OAuth, Render changes or deployment were performed.
- **Part 1 handoff:** PR #128 is now merged in main at `c18af6a32870ad40ceb6735b5c8a368bd7861c9f`; update stale coordination status and inspect open PR [#129](https://github.com/francistheroo/nova-instagram-ai/pull/129), a backup of PR #113 with scheduler code changes, reported open and non-mergeable. Determine whether it is needed or should be closed; do not merge it blindly.
- **Part 3 handoff:** Part 3 has opened timezone/readiness PR [#132](https://github.com/francistheroo/nova-instagram-ai/pull/132), branch `fix/scheduler-timezone-readiness`, latest inspected head `fc587f4c1b58cc38d58e9dff58894e7e6943a3bc`; it is open and currently reports non-mergeable. Both PR #130 and PR #132 modify `app/main.py` in different areas (direct image route vs scheduler startup/readiness), so coordinate merge order and re-check/rebase the remaining branch after the first merges. Latest workflow lookup returned no CI run for the inspected PR #132 head. Please complete test/CI review and Render evidence separately. Canva/Render live connections remain unverified.
- Overall production-readiness work is **NOT COMPLETE** until Parts 1 and 3 post current-cycle evidence and PR #130 receives Part 1 review/merge decision.
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
- Previous known result: PR #124 updated the master recovery checkpoint for Canva, scheduler and Render audit. Re-read the current checkpoint and ve### 2026-11-01 — Part 2 — production-readiness live-action gate hardening

- **Status:** VERIFIED — PR-head CI passed; PR remains open for independent review.
- **Branch / PR:** `security/disable-canva-direct-publish-bypass`, [PR #130](https://github.com/francistheroo/nova-instagram-ai/pull/130), open, GitHub reports mergeable.
- **Commit SHA:** Base main at branch creation `c18af6a32870ad40ceb6735b5c8a368bd7861c9f`; latest branch head `7437f07b7a6a977c984e9cc1c5b6eff4bcc301e7`. Compare to current main: 8 ahead / 3 behind; behind commits are documentation updates after branch creation.
- **Changes made:** Disabled legacy Canva photo/Reel direct-publish routes with HTTP 410; disabled legacy one-step `/instagram/publish-image`; removed external API publishing code from direct Canva modules; added no-call review-bypass regression tests. Auth/API-key/master-switch dependencies remain enforced before returning 410.
- **Tests run and results:** GitHub Actions [run #41298815095](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41298815095), job `test`: **505 passed, 6 skipped, 40 warnings, 0 failed**. All steps succeeded. Earlier run #41298463804 also passed on the preceding head. No local test execution.
- **CI evidence:** PR-head CI run #41298815095 on `c303eb5899201c3593879282b80b7f6c796d52b6`; no claim about current-main CI.
- **Risks or blockers:** Draft-flow publish endpoints treat the explicit authenticated admin publish request as operator approval after Meta reports FINISHED; no separate persisted approval ledger exists. Keep all live action flags OFF.
- **Next part / requested action:** Part 1: update stale PR #128 coordination status (it is merged as `c18af6a32870ad40ceb6735b5c8a368bd7861c9f`? verify exact SHA from main) and review open backup PR #129 plus PR #130. Part 3 has opened timezone/readiness PR #132 (head `d98965e92ced00428d0b9d717a8f5d4ccba9095f`); complete its tests/CI and review Render deployment evidence. Both #130 and #132 touch `app/main.py`; re-check mergeability/rebase after the first merges. Overall cycle remains open until all three parts supply current evidence.

### 2026-11-01 — Part 2 — production-readiness live-action gate hardening

- **Status:** IN PROGRESS — code changes submitted; PR-head CI pending.
- **Branch / PR:** `security/disable-canva-direct-publish-bypass`, [PR #130](https://github.com/francistheroo/nova-instagram-ai/pull/130), open, mergeable at latest check.
- **Commit SHA:** Base main `c18af6a32870ad40ceb6735b5c8a368bd7861c9f`; latest branch head `7437f07b7a6a977c984e9cc1c5b6eff4bcc301e7`.
- **Changes made:** Disabled legacy Canva photo and Reel direct-publish routes with HTTP 410; disabled legacy one-step `/instagram/publish-image`; added regression tests that assert review is required and external Meta/Canva calls do not occur. Existing authorization dependencies remain enforced.
- **Tests run and results:** Regression tests committed; not run locally. GitHub Actions [run #41298463804](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41298463804) is in progress; no pass/fail conclusion yet.
- **CI evidence:** Pending on PR head `7437f07b7a6a977c984e9cc1c5b6eff4bcc301e7`.
- **Risks or blockers:** Draft-flow publish endpoints use explicit authenticated admin publish requests after Meta reports FINISHED, but there is no separate persisted approval ledger. Keep all live action flags OFF until all Parts complete review.
- **Next part / requested action:** Part 1: refresh coordination inventory after PR #128 merge and review stale open PR #129. Part 3: independently fix timezone readiness and verify Render only with authorized evidence. Both should post updated findings before overall completion.

### 2026-11-01 — Part 1 — PR #128 follow-up handoff

- **Status:** VERIFIED — documentation diff reviewed; PR-head CI passed. Current-main CI remains NOT VERIFIED.
- **Branch / PR:** `docs/render-verification-followup`, [PR #128](https://github.com/francistheroo/nova-instagram-ai/pull/128), open, documentation-only, GitHub `mergeable=true`.
- **Commit SHA:** PR head `afa1d2e5b5b5fca36524eb2008528a65da9186c6`; base `670b1b082baa1e3e0704647f4911db7df495f1c0`; current main at audit read `6437f7d04286f745feba90c42cf73819dcba4b19`.
- **Changes made:** No PR changes by Part 1. Reviewed PR #128's one-file diff in `docs/NOVA_RECOVERY_CHECKPOINT.md`; it accurately marks Render endpoints/runtime unverified, corrects the obsolete daily-cap mismatch (both limits 0–20), and retains the timezone readiness follow-up. PR #127 is closed unmerged.
- **Tests run and results:** PR #128 CI [run #41296728250](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296728250): **507 passed, 6 skipped, 40 warnings, 0 failed**.
- **CI evidence:** PR-head CI only; current main combined status had no entries and no current-main workflow run was returned.
- **Risks or blockers:** PR #128 is 1 commit ahead/5 behind current main despite GitHub reporting mergeable; its base predates the latest Part 1 checkpoint edits in the same recovery file.
- **Next part / requested action:** Part 3: rebase/update PR #128 against current main or verify the merge preserves the latest Part 1 section before merging. Address timezone startup validation in a separate code/test PR. Part 2: update its section in this hub when its security audit is complete.

eserves the latest Part 1 section before merging. Address timezone startup validation in a separate code/test PR. Part 2: update its section in this hub when its security audit is complete.

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
