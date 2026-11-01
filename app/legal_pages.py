"""Public legal and privacy information pages for the NOVA app."""
import html
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#080d0a">
<title>{html.escape(title)} · NOVA</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#080d0a;color:#edf5ef;font:16px/1.7 system-ui,sans-serif}}
main{{max-width:820px;margin:40px auto;padding:28px 22px 56px}}
.brand{{color:#91f2bd;font-weight:800;letter-spacing:.16em;font-size:13px}}
h1{{font-size:clamp(30px,5vw,44px);line-height:1.15;margin:12px 0}}
h2{{font-size:21px;margin:28px 0 8px;color:#b7f5d0}}
p,li{{color:#d1ddd5}}a{{color:#91f2bd}}
.card{{background:#101914;border:1px solid #263b2e;border-radius:16px;padding:18px;margin:18px 0}}
small{{color:#9eafa4}}footer{{margin-top:36px;border-top:1px solid #263b2e;padding-top:16px;color:#9eafa4}}
</style></head><body><main>
<div class="brand">NOVA · AI CREATOR TOOLS</div>
{body}
<footer><a href="/privacy">Privacy</a> · <a href="/data-deletion">Data deletion</a> · <a href="/terms">Terms</a></footer>
</main></body></html>"""
    )


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy():
    body = """
<h1>Privacy Policy</h1>
<p><small>Last updated: 1 November 2026</small></p>
<p>This policy explains how the NOVA application handles information when an account owner connects Instagram or uses NOVA's AI-assisted content tools.</p>
<div class="card"><strong>In short:</strong> NOVA uses information to provide the features you choose, does not sell personal information, and requires the app operator to handle deletion requests.</div>
<h2>Information processed</h2>
<ul>
<li>Instagram account identifiers, profile details, media, comments and messages that the connected account authorizes NOVA to access.</li>
<li>Instagram access credentials. OAuth access tokens are encrypted before being stored in the configured PostgreSQL database.</li>
<li>Content, prompts and settings submitted to NOVA, including AI-generated drafts and any conversation context used by enabled features.</li>
<li>Technical information needed to operate and secure the service, such as request and error records produced by the hosting platform.</li>
</ul>
<h2>How information is used</h2>
<p>Information is used to connect the account, display authorized account content, support enabled comment or messaging workflows, create content drafts, and operate security and administration features. NOVA does not promise that every feature is available for every Instagram account or Meta permission.</p>
<h2>Third-party services</h2>
<p>When configured and used, information may be sent to Meta/Instagram, the selected AI provider (which may include Google Gemini or Groq), Canva, the configured image-generation provider, and the hosting/database providers. Those services process information under their own terms and privacy policies. Do not submit sensitive personal information in prompts or messages unless necessary and understood.</p>
<h2>Storage and security</h2>
<p>Instagram OAuth tokens are encrypted before database storage. Other information may be processed or retained by the application, its database, and hosting logs for as long as needed to provide, secure, and maintain the service. No online service can guarantee absolute security.</p>
<h2>Sharing and sale</h2>
<p>NOVA does not sell personal information. Information is shared with the service providers described above when needed to provide a feature, comply with law, or protect the service and its users.</p>
<h2>Your choices and deletion</h2>
<p>You can stop using NOVA and revoke its Instagram permissions through Meta/Instagram settings. To request deletion of information held by NOVA, follow the instructions on the <a href="/data-deletion">User Data Deletion</a> page.</p>
<h2>Children</h2>
<p>NOVA is not intended for children under 13. If you believe a child has provided personal information, contact the app operator using the contact details shown below so the issue can be reviewed.</p>
<h2>Contact</h2>
<p>For privacy questions, contact the NOVA app operator:</p>
"""
    contact = os.getenv("NOVA_PRIVACY_CONTACT_EMAIL", "zedexeditingz@gmail.com").strip()
    if contact:
        safe = html.escape(contact)
        body += f'<p><a href="mailto:{safe}">{safe}</a></p>'
    else:
        body += '<p class="card">Privacy contact email is not configured yet. The app operator must set the NOVA_PRIVACY_CONTACT_EMAIL environment variable before submitting this policy for Meta review.</p>'
    body += "<p>This policy may be updated when the service or its data practices change.</p>"
    return _page("Privacy Policy", body)


@router.get("/data-deletion", response_class=HTMLResponse, include_in_schema=False)
async def data_deletion():
    contact = os.getenv("NOVA_PRIVACY_CONTACT_EMAIL", "").strip()
    body = """
<h1>User Data Deletion</h1>
<p>This page explains how to request deletion of information associated with NOVA.</p>
<h2>Step 1 — Revoke access</h2>
<p>In your Meta/Facebook account settings, open Business Integrations or Apps and Websites, find NOVA, and remove its access. This stops future access through that authorization. The exact settings label may vary by account.</p>
<h2>Step 2 — Request deletion from NOVA</h2>
<p>Send a request to the NOVA app operator using the contact address below. Include your Instagram username and state that you want your NOVA-associated data deleted. Do not send your password or access token.</p>
<h2>What happens next</h2>
<p>The operator will verify the request without asking for your password, remove the connected Instagram token and other identifiable NOVA data that can be located, and reply when the request has been handled. Some records may be retained where required by law or for legitimate security purposes; any such retention will be limited to that purpose.</p>
"""
    if contact:
        safe = html.escape(contact)
        body += f'<div class="card"><strong>Deletion request contact</strong><p><a href="mailto:{safe}?subject=NOVA%20data%20deletion%20request">{safe}</a></p></div>'
    else:
        body += '<div class="card"><strong>Deletion contact not configured.</strong><p>The NOVA operator must set NOVA_PRIVACY_CONTACT_EMAIL before this page is ready for public Meta submission.</p></div>'
    body += '<p>Revoking Meta access alone does not send a deletion request to NOVA. Please also contact the operator.</p>'
    return _page("User Data Deletion", body)


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_of_service():
    body = """
<h1>Terms of Service</h1>
<p><small>Last updated: 1 November 2026</small></p>
<p>NOVA provides AI-assisted content creation and account-management tools for authorized Instagram professional accounts. By using NOVA, you agree to use it lawfully and in accordance with Meta, Canva, and other connected service terms.</p>
<h2>Your responsibility</h2>
<p>You must own or be authorized to manage any connected account and content. You are responsible for reviewing AI-generated text, images, replies and other outputs before use, checking accuracy and rights, and ensuring your activity follows applicable law and platform policies.</p>
<h2>Third-party services and availability</h2>
<p>Instagram, Meta, Canva, AI providers, hosting and database services are operated by third parties. Their availability, permissions, limits and terms may change. NOVA cannot guarantee uninterrupted service or that Meta will approve every permission or publishing action.</p>
<h2>AI-generated content</h2>
<p>AI output may be inaccurate, incomplete, or unsuitable. Review it before sharing. NOVA is an AI tool and does not represent itself as a human.</p>
<h2>Acceptable use</h2>
<p>Do not use NOVA to spam, deceive, harass, infringe rights, bypass platform restrictions, or access accounts or information without authorization.</p>
<h2>Changes and contact</h2>
<p>These terms may be updated as NOVA changes. For questions, use the contact information on the <a href="/privacy">Privacy Policy</a> page.</p>
"""
    return _page("Terms of Service", body)
