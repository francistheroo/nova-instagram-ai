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

**Current status:** COMPLETE — conflict recovery merged, all implementation parts merged, documentation handoff merged, and current-main CI passed. No open PRs remain at this audit.

**Final handoff — 2026-11-01:**
- Latest main after the Part 3 documentation merge: `a138fe0ec1cdba2e0f0dd6558717aebf6040f0d5`.
- Part 1 conflict-recovery PR [#139](https://github.com/francistheroo/nova-instagram-ai/pull/139) merged; the v3 note supersedes the stale v2 note. PRs #131, #134 and #137 remain closed unmerged.
- Part 2 security-gate hardening PR [#130](https://github.com/francistheroo/nova-instagram-ai/pull/130) merged. Legacy direct Canva publish routes and the one-step image publisher are disabled; regression tests verify blocked routes do not call publishing integrations.
- Part 3 scheduler timezone/readiness PR [#132](https://github.com/francistheroo/nova-instagram-ai/pull/132) merged. Startup validates IANA timezone before scheduler initialization; `/ready` reports scheduler startup readiness.
- Part 3 documentation handoff PR [#135](https://github.com/francistheroo/nova-instagram-ai/pull/135) merged as `a138fe0ec1cdba2e0f0dd6558717aebf6040f0d5`. Exact final PR-head CI [#41300177072](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41300177072) succeeded.
- Current-main CI on the merge commit [#41300273208](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41300273208) completed with conclusion `success`; test job, dependency installation and test step all succeeded.
- Final open-PR search returned **zero open PRs**.
- No application code was changed by Part 1. No live Instagram message/post, Meta/Canva API action, OAuth, Render setting, secret, database or deployment change was performed.
- **Remaining external blocker:** actual Render dashboard/service configuration, deployed commit, logs, health-check path and database attachment still require authorized account verification. Repository and CI completion does not establish live deployment readiness.
- Keep `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_SCHEDULER_ENABLED=false` until authorized deployment checks and separate approval are completed.
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
### Part 3 — Scheduler and deployment readiness

**Owner:** Chat / Part 3

**Current status:** SCHEDULER TIMEZONE/READINESS IMPLEMENTATION MERGED; DOCUMENTATION HANDOFF MERGED; CI PASSED; LIVE RENDER VERIFICATION BLOCKED PENDING AUTHORIZED ACCOUNT CONNECTION.

**Final handoff — 2026-11-01:**
- Scheduler/timezone readiness PR #132 is merged; timezone validation fails closed for blank/invalid values, and `/ready` distinguishes scheduler startup readiness from `/health` liveness.
- Documentation handoff PR #135 is merged as `a138fe0ec1cdba2e0f0dd6558717aebf6040f0d5`; exact PR-head CI #41300177072 passed.
- Main CI on the resulting merge commit `a138fe0ec1cdba2e0f0dd6558717aebf6040f0d5` passed in run #41300273208.
- Render repository review documents the suggested Python build/start commands and `/ready` versus `/health` selection. No root `render.yaml` or `Dockerfile` was present at review time.
- Actual Render dashboard build/start settings, deployed commit, health-check path, runtime logs, database attachment, and private environment values remain **NOT VERIFIED**. The Render account connector must be connected before these can be checked.
- No Render settings, secrets, database or deployment were changed. No live Meta/Canva/Instagram requests were made. All live switches remain OFF.
## Final integration checklist

- [x] Part 1 has reviewed current main, open PRs, tests and CI evidence.
- [x] Part 2 security-gate hardening is merged and CI-verified.
- [x] Part 3 scheduler/timezone readiness and documentation handoff are merged and CI-verified; live Render verification remains outstanding.
- [x] Cross-part conflicts and duplicate work have been reconciled.
- [x] Live messaging and publishing remain disabled during development.
- [x] Master recovery checkpoint reflects verified results and outstanding work.
- [x] All three parts have posted a final handoff in this file.


### 2026-11-01 — Part 1 — PR #131 conflict recovery v4

- **Status:** IN PROGRESS — PR #137 became non-mergeable after `main` advanced. This replacement branch is created directly from the current `main` ref to preserve all other chats' latest documentation.
- **Branch:** `part1/pr131-conflict-fix-v4`.
- **Base:** `main` at branch creation; exact base SHA is recorded in the pull request metadata.
- **Changes:** Replaces the stale v2 recovery note with the v3 note in the three Part 1 checkpoint/coordination documents. No application code, tests, live settings, deployment, or external integration changed.
- **CI:** Not yet verified for this exact branch head. Ancestor CI must not be reported as current branch CI.
- **Next:** Verify exact-head CI and mergeability; Part 2 and Part 3 evidence remains independently required before overall readiness can be complete.
