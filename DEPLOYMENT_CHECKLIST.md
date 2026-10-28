# NOVA deployment checklist

- [ ] Create a private Git repository (never commit `.env`).
- [ ] Deploy the FastAPI app to a Python host.
- [ ] Add AI provider secrets using the host's environment-variable settings.
- [ ] Verify `/health`.
- [ ] Test `/preview-reply` with Manglish, Malayalam, and English.
- [ ] Configure Meta Developer app and authorize your Instagram account.
- [ ] Confirm the exact Instagram API permissions available to your account.
- [ ] Implement and test only supported endpoints.
- [ ] Add persistent storage, scheduler, retries, rate limiting, and an emergency stop.
- [ ] Start in draft/test mode before enabling permitted autonomous actions.

Do not paste passwords, session cookies, access tokens, or API keys into a chat.
