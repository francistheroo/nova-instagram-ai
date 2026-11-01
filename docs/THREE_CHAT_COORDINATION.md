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

**Current status:** NOT STARTED for this coordination cycle.

**Latest update / handoff:**
- Awaiting Part 1 review.
- Previous known result: PR #113 was merged, but no CI status entries were returned for its merge commit at the time of that check. Re-check current GitHub evidence rather than assuming a result.

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
