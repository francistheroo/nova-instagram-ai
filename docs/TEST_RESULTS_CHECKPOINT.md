# NOVA Test Results Checkpoint

Last updated: 2026-10-31

This file tracks verified repository/CI checks separately from live Instagram integration checks. A green CI run does **not** prove that a real Instagram account is connected or that Meta permissions are approved.

## Latest verified results

| Stale scheduler processing reconciliation | PASS + MERGED | [PR #119](https://github.com/francistheroo/nova-instagram-ai/pull/119) · [CI #41288262861](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41288262861) | Rows left in `processing` for over two hours become `uncertain`, retain daily-cap capacity, and are never automatically retried. Tests cover the transition and threshold validation. Merged as `47ba003436e2c9cc36736d2778883225cebcba15`. No live publishing occurred. |


| Instagram account webhook subscription controls | PASS + MERGED | [PR #117](https://github.com/francistheroo/nova-instagram-ai/pull/117) · [CI #41287980131](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41287980131) | Protected subscribe/status/unsubscribe routes use the Instagram Login `/me/subscribed_apps` edge and only the supported `messages` field. Reuses the PostgreSQL refresh lock; tokens are not returned. CI passed on the implementation commit; final follow-up change was README wording only. App-level callback/field setup and live delivery remain Meta Dashboard tasks. Merge SHA `ae815a1ed66a947b01dd8701031dc7565f962d34`. |

| Automatic Instagram token refresh worker | PASS + MERGED | [PR #114](https://github.com/francistheroo/nova-instagram-ai/pull/114) · [CI #41287441307](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41287441307) | Adds an opt-in background check every six hours; refreshes known, valid tokens within seven days of expiry under the existing PostgreSQL advisory lock. Worker stops on shutdown and exposes health state. Merged as `d67159d4c775b1a8bb7dc210553575329d2b3821`. Tests passed; no live Meta request was made. Enable only after Meta OAuth is connected and DATABASE_URL is configured: `INSTAGRAM_TOKEN_AUTO_REFRESH_ENABLED=true`. |

| Scheduled publish ambiguity protection | PASS + MERGED | [PR #111](https://github.com/francistheroo/nova-instagram-ai/pull/111) · [CI #41204551914](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41204551914) | Added an `uncertain` publish state for ambiguous Meta publish outcomes; uncertain runs reserve daily capacity and are not automatically retried. Existing schema constraint is migrated without deleting history. Tests passed; merged as `0015dd0b1d0110508dc3eebccf3584160d72a65a`. No live publishing occurred. |

| Checkpoint PR #107 | PASS + MERGED | [PR #107](https://github.com/francistheroo/nova-instagram-ai/pull/107) · [CI #41203446639](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41203446639) | Records PR #106 retry-safety merge and passing CI; merged as `2d21d68640c174866081da9b2aafa0670fa1b424`. |
| Scheduler startup/health readiness | PASS + MERGED | [PR #108](https://github.com/francistheroo/nova-instagram-ai/pull/108) · [CI #41203747682](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41203747682) | Scheduler no longer starts without DATABASE_URL; /health reports database_not_configured and actual task state. Added startup/health regression tests; merged as `24d82c50f7438f97aa64b6cd10aad23e029d3670`. |

| Checkpoint after PR #105 | PASS + MERGED | [PR #106](https://github.com/francistheroo/nova-instagram-ai/pull/106) · [CI run #41203349695](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41203349695) | Records merged webhook retry classification, successful CI, and remaining manual reconciliation/scheduler limitations. Merged as `4204943d2d874a56d5ccb2b8a613739c25a8f195`. |

| Meta DM send-response classification | PASS + MERGED | [PR #105](https://github.com/francistheroo/nova-instagram-ai/pull/105) · [CI run #41203236563](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41203236563) | HTTP 408/429 are retryable; other 3xx/4xx are terminally ignored; 5xx are marked uncertain to avoid possible duplicate sends. Regression tests cover 400, 401, 403, 429, and 503. Merged as `afffb468ab69013a95cb308bd354c6740ef760cb`. No live Instagram messages sent. |
| Webhook/scheduler audit checkpoint | PASS + MERGED | [PR #104](https://github.com/francistheroo/nova-instagram-ai/pull/104) · [CI run #41203039316](https://github.com/francistheroo/nova-instagram-ai/actions/runs/41203039316) | Documents current webhook idempotency coverage and remaining concurrency verification; records scheduler stale-processing and missed-slot policy limitations. Merged as `a9599c96bf2dd1499f660a5ef9e9bc7332e72d46`. |

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

PRs #83, #85, and #94 were closed because their security changes are already represented in the current main implementation and tests. They were **not merged**; no duplicate or stale branch changes were introduced. Main workflow #271 passed after the checkpoint refresh. PR #104 CI run #41203039316 and PR #105 CI run #41203236563 also passed. See the PR conversation comments for the file-by-file rationale.

## Not yet verified

- Webhook duplicate/idempotency review: existing tests cover duplicate message IDs, retryable AI/Meta failures, post-send history failure, and ambiguous send timeout; further concurrent-delivery/database integration testing remains pending.
- Scheduler reliability: existing tests cover daily-cap reservation and midnight local-date handling. Processing rows older than two hours are changed to `uncertain`, retain their daily-cap reservation, and are never automatically retried because Meta may already have accepted the publish before a worker crash. Manual reconciliation is still needed to decide the final outcome. Downtime longer than the one-minute catch-up window can miss a slot; decide whether missed slots should be skipped or backfilled.
- Ambiguous outbound DM delivery remains a manual-reconciliation case: send timeouts and Meta HTTP 5xx responses are marked uncertain and are not automatically resent. No automated reconciliation UI/workflow is implemented.
- Scheduler daily limits and timezone boundary cases beyond the already merged midnight-slot fix.
- Live Meta OAuth authorization and token exchange.
- Live webhook verification/subscription and real test-message ingestion.
- Live Instagram publishing permissions and end-to-end publish test.
- Production deployment, persistent worker operation, and emergency-stop behavior.
- Live Meta OAuth, webhook subscription/delivery, approved permissions, real DM replies, and live publishing remain unverified; CI does not prove external account readiness.

## Rules for updating this checkpoint

1. Record each check as PASS, FAIL, SKIPPED, BLOCKED, or NOT RUN.
2. Include the exact GitHub Actions run, PR, commit, and relevant test count when available.
3. A PR branch CI pass is not the same as a merge or a main-branch pass.
4. Do not mark live Instagram integration as passed based only on unit tests or `/health`.
5. Do not record secrets, passwords, access tokens, cookies, or private account data here.
6. Keep unverified items pending until the corresponding test is actually run and its result inspected.

## Safety / scope

This checkpoint records repository tests only. It does not authorize deployment, connecting an Instagram account, or enabling live automation.
