# Instagram OAuth setup checklist for NOVA

This is a setup checklist, not a claim that OAuth is already implemented. The current NOVA backend expects an access token and Instagram user ID to be configured manually. Do not enable write actions just because credentials exist.

## Before coding the OAuth flow

- [ ] Create/configure a Meta developer app owned by the account owner.
- [ ] Choose the official Instagram API login flow that matches the Creator account and the endpoints NOVA needs.
- [ ] Configure the exact HTTPS callback URL for the deployed Render service.
- [ ] Request only the permissions needed for the first milestone (read profile/media and comments). Add publishing or messaging permissions only when their use cases are implemented and approved.
- [ ] Complete Meta's required app setup, testing roles, and access review for the intended users.
- [ ] Store app secrets and tokens only in server-side secret storage. Never commit them or put them in browser JavaScript.
- [ ] Use a cryptographically random, single-use OAuth state value; bind it to the initiating session, expire it quickly, and reject missing, expired, or mismatched state.
- [ ] Exchange authorization codes on the server, validate error responses, and avoid logging authorization codes or tokens.
- [ ] Implement long-lived token refresh/renewal according to the current official Meta documentation, with expiry tracking and failure alerts.
- [ ] Decide on persistent encrypted token storage before deploying OAuth. Do not store production tokens only in process memory: Render restarts and multiple instances can lose or disagree on the token.
- [ ] Keep Instagram write actions disabled until read-only account access has been tested and the required permissions are confirmed.

## Implementation acceptance checks

1. A user can start authorization from NOVA and sees Meta's official authorization screen.
2. A callback with invalid/missing state is rejected.
3. A declined authorization shows a safe error without exposing secrets.
4. A valid callback exchanges the code server-side and stores tokens in the chosen persistent encrypted store.
5. Health status distinguishes credentials present from authorization completed and verified.
6. Tests cover state mismatch, provider errors, token expiry, and missing configuration.
7. Disconnect/revoke behavior removes stored tokens and disables actions.

## Official references

- Instagram Platform documentation: https://developers.facebook.com/docs/instagram-platform/
- Meta's official Postman API collection: https://www.postman.com/meta/instagram/

Use the current official docs to confirm the login flow, exact scopes, token endpoints, and API version before implementation. The API version currently in NOVA's environment defaults may need updating.

## Current status

Instagram OAuth, token refresh, webhook verification, and persistent token storage are not implemented in NOVA yet. This checklist does not connect an account or enable automation.
