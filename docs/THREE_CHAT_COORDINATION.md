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

**Current status:** IN PROGRESS — latest inventory found one open PR (#127); current-main CI is not independently verified.

**Latest update / handoff — 2026-11-01:**
- Latest `main` inspected at `9b8c331eb80a04a577d0fe5ed75f3d20999364ca` (commit: `Document live-action gates in NOVA security checkpoint`). Latest commit changes only `docs/security-audit-checkpoint-2026-11-01.md`.
- Open PR search initially returned zero; a subsequent fresh search found one open PR: [#127](https://github.com/francistheroo/nova-instagram-ai/pull/127), a Part 3 documentation-only Render verification follow-up. It targets main, is currently reported `mergeable=false`, and its branch base predates Part 1's latest main checkpoint commit. PRs #122–#126 and #113 are closed/merged. Part 1 did not merge or close any PR.
- Latest verified application-code CI remains PR #126 head run [#41296358475](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41296358475): **507 passed, 6 skipped, 40 warnings, 0 failed**. PR #126 merge commit is `d2e445be791ba36170946c2fc5d1f66bdfaad3f1`. A separate CI run on the current main head/merge commit was not returned by the available commit-run lookup; combined commit status for current main returned no status entries. Therefore current-main CI is **NOT VERIFIED**, not PASS. The earlier main run #41295206264 (503 passed, 6 skipped) is historical evidence on ancestor `48bbe70670dcbeaf2fd22ec2afa6e723d3bdb7f2`, not the current main head.
- No failing tests or merge conflicts are currently reported for open PRs because there are no open PRs. Part 1 made no application-code changes.
- Branch hygiene: `fix/validate-scheduler-settings-current-main` is 34 commits behind main with no unique commits; `security/audit-scheduler-duplicate-safety` is diverged (5 ahead, 12 behind) and modifies `app/admin.py` plus scheduler tests. Do not merge either branch without a fresh focused review/rebase. The former rebased scheduler branch is stale; duplicate test definitions observed there are not in main.
- **Handoff to Part 2:** Please inspect `security/audit-scheduler-duplicate-safety` before reusing or deleting it. It is 5 ahead/12 behind main and contains changes to `app/admin.py`, `tests/test_scheduler_admin_limits.py`, and `tests/test_scheduler_duplicate_claim.py`; PR #126 has already merged the admin cap alignment, so avoid duplicating that fix. Also keep all live-action gates OFF; current repository documentation requires `INSTAGRAM_AUTOMATION_ENABLED=false`, `INSTAGRAM_AUTO_DM_REPLIES_ENABLED=false`, and `NOVA_SCHEDULER_ENABLED=false` during development. OAuth, real permissions, and live webhook delivery remain unverified.
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

**Current status:** NOT STARTED for this coordination cycle.

**Latest update / handoff:**
- Previous known result: PR #123 added the global automation gate for webhook DM replies and was merged. Re-verify current code and tests before relying on it.
- No live OAuth connection, webhook delivery or real Instagram messaging should be assumed.

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
