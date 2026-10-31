# NOVA Test Results Checkpoint

Last updated: 2026-10-31

This file tracks verified repository/CI checks separately from live Instagram integration checks. A green CI run does **not** prove that a real Instagram account is connected or that Meta permissions are approved.

## Latest verified results

| Area | Result | Evidence | Notes |
|---|---|---|---|
| Latest main test workflow | PASS | [Actions run #271](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41200649194) | Main-branch workflow completed successfully; all steps including the test step passed. |
| Latest main test workflow after PR #100 | PASS | [Actions run #41202333972](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41202333972) | Main-branch workflow completed successfully after merge commit `b4fd434caeb2dc6641e6847c36780063d4e5a644`. |
| Main test suite with published count | PASS | [Actions run #266](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41199604041) | 456 passed, 6 skipped, 38 warnings, 0 failed. |
| Admin/API-key test setup | PASS | [PR #97](https://github.com/francistheroo/nova-instagram-ai/pull/97) | Fixed missing test API key/header and admin environment setup. PR merged. |
| Webhook sender-ID validation | PASS + MERGED | [PR #98](https://github.com/francistheroo/nova-instagram-ai/pull/98) · [Actions run #267](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41199926158) | CI passed; regression tests cover blank, whitespace, invalid-character, and oversized sender IDs. PR merged to main. |
| Checkpoint documentation | PASS + MERGED | [PR #99](https://github.com/francistheroo/nova-instagram-ai/pull/99) · [Actions run #269](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41200379935) | Documentation-only PR; CI passed and PR merged. |
| PR #95 / #96 test setup failures | FIXED | [PR #97](https://github.com/francistheroo/nova-instagram-ai/pull/97) | Earlier failures were caused by missing test environment setup, not proof of live Instagram failure. |
| Historical main run #260 | FAIL (superseded) | [Actions run #260](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41198306363) | 450 passed, 1 failed, 6 skipped. The failure was invalid-recipient test setup (missing API key); later corrected by PR #97 and subsequent green main runs. |


| PR #103 checkpoint refresh | MERGED | [PR #103](https://github.com/francistheroo/nova-instagram-ai/pull/103) | Recorded PR #102 DM-memory expiry tests and prior main workflow evidence; merged as `46b699b8766745b4ee24bc128c7124e69231e28c`. No application behavior changes. |
| DM memory 12-hour expiry | PASS + MERGED | [PR #102](https://github.com/francistheroo/nova-instagram-ai/pull/102) · [PR CI #41202572266](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41202572266) | Added regression tests proving insertion expiry is exactly 12 hours after creation and reads delete/filter expired rows. Test-only change; merged as `d18fe5054e544fe63c00e6bf892c1a70f8150f55`. No live Instagram messages involved. |
| Checkpoint documentation after PR #101 | PASS | [Main CI #41202516818](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41202516818) | Main workflow completed successfully after PR #101. |

| Oversized inbound DM text | PASS + MERGED | [PR #100](https://github.com/francistheroo/nova-instagram-ai/pull/100) · [PR CI #41202216448](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41202216448) · [main CI #41202333972](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41202333972) | Webhook skips text above the existing 4,000-character storage limit before claiming an idempotency slot or writing memory; tests cover auto-replies on/off and exact-limit acceptance. Merged as `b4fd434caeb2dc6641e6847c36780063d4e5a644`. |

## Security PR status

| Item | Final status | Current-main coverage / evidence |
|---|---|---|
| PR #94 — Instagram read-route admin security | CLOSED as superseded; not merged | Current main protects Instagram verify/media/comment reads and Reel status reads with admin authentication; invalid media/comment IDs are validated. [PR #94](https://github.com/francistheroo/nova-instagram-ai/pull/94) |
| PR #85 — OAuth-start admin security | CLOSED as superseded; not merged | Instagram and Canva OAuth routers apply `Depends(require_user)`; tests include `test_instagram_oauth_start_requires_admin_login` and `test_canva_oauth_start_requires_admin_login`. [PR #85](https://github.com/francistheroo/nova-instagram-ai/pull/85) |
| PR #83 — broader API/admin/master-switch security | CLOSED as superseded; not merged | Current main includes admin checks across Instagram, Reel, DM-memory, Canva API/review/direct-publish, and OAuth routes; action routes retain master-switch and automation gates, API-key checks use constant-time comparison, and Instagram IDs/recipient IDs are validated. [PR #83](https://github.com/francistheroo/nova-instagram-ai/pull/83) |

PRs #83, #85, and #94 were closed because their security changes are already represented in the current main implementation and tests. They were **not merged**; no duplicate or stale branch changes were introduced. Main workflow #271 passed after the checkpoint refresh. See the PR conversation comments for the file-by-file rationale.

## Not yet verified

- Webhook duplicate/idempotency review: existing tests cover duplicate message IDs, retryable AI/Meta failures, post-send history failure, and ambiguous send timeout; further concurrent-delivery/database integration testing remains pending.
- Scheduler reliability: existing tests cover daily-cap reservation and midnight local-date handling. Stale `processing` publish rows intentionally are not auto-reclaimed because Meta may already have accepted a publish before a worker crash; they need an explicit reconciliation policy. Downtime longer than the one-minute catch-up window can miss a slot; decide whether missed slots should be skipped or backfilled.
- Ambiguous outbound DM delivery: ensure uncertain sends are not automatically resent.
- Scheduler daily limits and timezone boundary cases beyond the already merged midnight-slot fix.
- Live Meta OAuth authorization and token exchange.
- Live webhook verification/subscription and real test-message ingestion.
- Live Instagram publishing permissions and end-to-end publish test.
- Production deployment, persistent worker operation, and emergency-stop behavior.

## Rules for updating this checkpoint

1. Record each check as PASS, FAIL, SKIPPED, BLOCKED, or NOT RUN.
2. Include the exact GitHub Actions run, PR, commit, and relevant test count when available.
3. A PR branch CI pass is not the same as a merge or a main-branch pass.
4. Do not mark live Instagram integration as passed based only on unit tests or `/health`.
5. Do not record secrets, passwords, access tokens, cookies, or private account data here.
6. Keep unverified items pending until the corresponding test is actually run and its result inspected.

## Safety / scope

This checkpoint records repository tests only. It does not authorize deployment, connecting an Instagram account, or enabling live automation.
