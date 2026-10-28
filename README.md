# NOVA — Instagram AI starter

NOVA is a FastAPI backend with a Manglish-focused AI reply preview and guarded integration scaffolding.

## Existing and added functionality

- `GET /health`: reports whether provider credentials are configured (not whether they have been verified).
- `POST /preview-reply`: generates an AI reply preview; it never sends it to Instagram.
- `GET /instagram/media`: lists accessible professional-account media through Meta's API.
- `GET /instagram/media/{media_id}/comments`: reads comments where permitted.
- `POST /instagram/comments/{comment_id}/reply`: replies to a comment when action endpoints are enabled and the account has permission.
- `POST /instagram/messages/reply`: attempts a supported message reply for an eligible Instagram-scoped recipient ID.
- `POST /instagram/publish-image`: creates and publishes an image container from a publicly reachable image URL.
- `POST /ai/generate-image`: calls a separately configured OpenAI-compatible image-generation API.
- `GET /canva/status`: reports credential presence only; Canva OAuth, design listing, and export are not implemented.

## Security and setup

1. Configure the official Meta app and authorize the Creator account using the appropriate Instagram Login flow.
2. In Render's private environment settings, set `META_GRAPH_BASE_URL`, `META_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_USER_ID` using values appropriate to that flow. The sample API version may need updating to a currently supported version.
3. Set `NOVA_API_KEY` to a long, random secret. Do not put it in frontend code, public repositories, or chat.
4. Keep `INSTAGRAM_AUTOMATION_ENABLED=false` while testing read-only endpoints. Set it to `true` only after confirming permissions and testing with content you control.
5. Add the key as the `X-NOVA-API-Key` header when calling protected NOVA endpoints. Do not expose this key in a public browser client.
6. Configure `IMAGE_API_BASE_URL`, `IMAGE_API_KEY`, and `IMAGE_MODEL` for an image provider that actually supports the OpenAI-compatible `/images/generations` endpoint. A text-only Groq model is not an image-generation provider.
7. Use a publicly reachable image URL for Instagram publishing. The image-generation endpoint's returned URL may be temporary; reliable publishing usually needs persistent object storage and a public URL.
8. Deploy and check `/health`, then test read-only `/instagram/media` before enabling any write action.

## Important limitations

- This is not a complete OAuth application: token acquisition, refresh, webhook subscription/verification, persistent job queue, Canva OAuth/design/export, and automatic event processing are not implemented.
- Instagram API permissions and endpoint behavior vary by API version and login flow. App review or access approval may be required.
- Like/unlike automation is not exposed as a supported general action by the standard Instagram API; no like endpoint is implemented.
- Instagram Notes creation and attaching music to Notes are not supported by the standard public API. Do not automate them through private endpoints or browser workarounds.
- Reels audio/music publishing requires a separately verified, supported Meta audio workflow and suitable licensing. This starter does not attach music to Reels.
- Message sending is subject to Meta messaging permissions, eligible conversations, and messaging windows. Do not use it for unsolicited bulk messages.
- Canva credentials alone do not provide an integration; OAuth and the required Connect API scopes/endpoints still need to be implemented.
- Render free instances may sleep, and local disk may not persist. Use persistent storage and a queue/scheduler for reliable automation.

Never commit API keys, access tokens, or secrets.
