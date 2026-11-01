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

**Current status:** COMPLETE — security-gate hardening merged and exact-head CI passed. Live Meta/OAuth behavior remains unverified; live actions remain disabled.

**Final handoff — 2026-11-01:**
- Security hardening PR [#130](https://github.com/francistheroo/nova-instagram-ai/pull/130) is merged. The legacy direct Canva photo/Reel publishing routes and the one-step `/instagram/publish-image` route are disabled with HTTP 410 responses; publishing calls were removed from those bypass routes.
- Regression tests cover the disabled routes and assert no Meta/Canva publishing call occurs through them. PR-head CI [#41298815095](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41298815095) completed successfully: **505 passed, 6 skipped, 40 warnings, 0 failed**.
- The reviewed draft flow still uses an explicit authenticated admin publish action after the draft/status review. There is no separate durable per-item approval ledger; treat that as a documented future auditability improvement, not as an unverified claim of a formal approval record.
- Remaining external verification: real Meta OAuth permissions, account connectivity, webhook delivery, and Render runtime are not verified in this repository-only pass.
- No real Instagram messages/posts, Meta/Canva requests, OAuth flow, Render settings, secrets or deployments were changed or attempted.
- Keep `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_SCHEDULER_ENABLED=false` during development. Do not enable live publishing as part of this closeout.
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

- **Status:** SUPERSEDED — no unique changes remain; replacement PR #139 merged.
- **Branch:** `part1/pr131-conflict-fix-v4`.
- **Disposition:** This temporary branch was superseded by the conflict-free PR #139. Do not reopen or merge this branch.