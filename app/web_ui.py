from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def nova_content_studio():
    """Serve a small same-origin UI for review-only AI drafts."""
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#050505">
<title>NOVA Content Studio</title>
<style>
:root{color-scheme:dark;--bg:#050505;--panel:#101010;--line:#282828;--text:#f5f5f5;--muted:#a4a4a4;--accent:#8cffc7}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#13231c 0,#050505 48%);color:var(--text);font:16px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:980px;margin:auto;padding:28px 18px 60px}.brand{display:flex;align-items:center;gap:12px;margin-bottom:24px}.logo{width:46px;height:46px;border:1px solid #3e7459;border-radius:15px;display:grid;place-items:center;color:var(--accent);font-weight:900;letter-spacing:-2px;background:#0b1711}.eyebrow{font-size:12px;color:var(--accent);text-transform:uppercase;letter-spacing:.15em}.brand h1{font-size:24px;margin:0}.sub{color:var(--muted);margin:3px 0 0}.notice{border:1px solid #39473f;background:#0d1510;border-radius:14px;padding:12px 14px;color:#cbd8cf;margin:20px 0 24px;font-size:14px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.card{background:color-mix(in srgb,var(--panel) 94%,transparent);border:1px solid var(--line);border-radius:18px;padding:20px;min-width:0}.card h2{font-size:19px;margin:0 0 5px}.desc{color:var(--muted);font-size:14px;margin:0 0 18px}label{display:block;font-size:13px;color:#d8d8d8;margin:13px 0 6px}input,select,textarea{font:inherit;width:100%;background:#080808;color:var(--text);border:1px solid #363636;border-radius:10px;padding:11px 12px;outline:none}textarea{min-height:90px;resize:vertical}input:focus,select:focus,textarea:focus{border-color:var(--accent)}button{margin-top:16px;border:0;border-radius:11px;background:var(--accent);color:#06110a;font-weight:750;padding:12px 16px;font-size:14px;cursor:pointer;width:100%}button:disabled{opacity:.6;cursor:wait}.output{margin-top:15px;border-top:1px solid var(--line);padding-top:13px;white-space:pre-wrap;overflow-wrap:anywhere;color:#e6e6e6;min-height:0}.output:empty{display:none}.status{color:var(--muted);font-size:13px;margin-top:9px}.footer{color:var(--muted);font-size:12px;margin-top:20px}@media(max-width:700px){.grid{grid-template-columns:1fr}main{padding:20px 13px 40px}.card{padding:16px}}
</style>
</head>
<body>
<main>
<header class="brand"><div class="logo">N</div><div><div class="eyebrow">AI assistant</div><h1>NOVA Content Studio</h1><p class="sub">Create ideas and captions before you post.</p></div></header>
<div class="notice"><strong>Review mode:</strong> This page only creates drafts. It does not publish, schedule, like, follow, or message anyone. AI provider settings must be configured on the server.</div>
<section class="card" style="margin-bottom:16px"><h2>Connection checklist</h2><p class="desc">Configuration only — this does not verify live account access.</p><div id="integrationStatus" class="status" role="status">Checking server configuration…</div></section>
<div class="grid">
<section class="card">
<h2>Caption writer</h2><p class="desc">Generate a caption in Manglish, Malayalam, or English.</p>
<form id="captionForm">
<label for="captionTopic">Post topic</label><textarea id="captionTopic" required minlength="3" maxlength="1000" placeholder="Example: funny Kerala school memories"></textarea>
<label for="captionTone">Tone</label><select id="captionTone"><option>funny and engaging</option><option>cinematic</option><option>friendly</option><option>informative</option><option>emotional</option><option>professional</option></select>
<label for="captionLanguage">Language</label><select id="captionLanguage"><option>Manglish</option><option>Malayalam</option><option>English</option><option>Malayalam and English</option></select>
<label><input id="hashtags" type="checkbox" checked style="width:auto;margin-right:8px">Include hashtags</label>
<button type="submit">Generate caption</button><div class="status" id="captionStatus" role="status"></div><div class="output" id="captionOutput" aria-live="polite"></div>
</form></section>
<section class="card">
<h2>Content ideas</h2><p class="desc">Plan original photo posts, Reels, and carousels.</p>
<form id="ideasForm">
<label for="ideasTopic">Topic or niche</label><textarea id="ideasTopic" required minlength="3" maxlength="1000" placeholder="Example: Malayalam comedy for teens"></textarea>
<label for="ideasCount">Number of ideas</label><select id="ideasCount"><option value="3">3 ideas</option><option value="5" selected>5 ideas</option><option value="8">8 ideas</option><option value="10">10 ideas</option></select>
<label for="ideasFormat">Preferred format</label><select id="ideasFormat"><option>mix of Reels, carousels, and photo posts</option><option>Reels</option><option>carousels</option><option>photo posts</option></select>
<label for="ideasLanguage">Language</label><select id="ideasLanguage"><option>Manglish</option><option>Malayalam</option><option>English</option><option>Malayalam and English</option></select>
<button type="submit">Generate ideas</button><div class="status" id="ideasStatus" role="status"></div><div class="output" id="ideasOutput" aria-live="polite"></div>
</form></section>
</div>
<p class="footer">NOVA Content Studio · Drafts are AI-generated and may need fact-checking and editing. Trend data is not fetched by this tool.</p>
</main>
<script>
async function loadIntegrationStatus() {
  const target = document.getElementById('integrationStatus');
  try {
    const response = await fetch('/integrations/status');
    if (!response.ok) throw new Error('Status endpoint unavailable');
    const s = await response.json();
    const rows = [
      ['AI text provider', s.ai && s.ai.text_provider_configured],
      ['Canva OAuth settings', s.canva && s.canva.oauth_environment_ready],
      ['Instagram OAuth settings', s.instagram && s.instagram.oauth_environment_ready],
      ['Publishing actions', s.instagram && s.instagram.publishing_enabled]
    ];
    target.textContent = rows.map(([label, ready]) => label + ': ' + (ready ? 'configured/enabled' : 'not configured/disabled')).join('\\n')
      + '\\nLive account verification: not performed.';
  } catch (_) {
    target.textContent = 'Could not read configuration status. Draft generation may still work if the AI provider is configured.';
  }
}
loadIntegrationStatus();

async function submitDraft(form, status, output, path, buildBody, render) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true; status.textContent = 'Generating…'; output.textContent = '';
  try {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(buildBody())});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed.');
    output.textContent = render(data);
    status.textContent = 'Draft ready — review before using.';
  } catch (error) {
    status.textContent = error.message || 'Could not generate a draft. Check server configuration.';
  } finally { button.disabled = false; }
}
document.getElementById('captionForm').addEventListener('submit', event => {
  event.preventDefault();
  submitDraft(event.currentTarget, document.getElementById('captionStatus'), document.getElementById('captionOutput'), '/ai/generate-caption', () => ({
    topic:document.getElementById('captionTopic').value,
    tone:document.getElementById('captionTone').value,
    language:document.getElementById('captionLanguage').value,
    include_hashtags:document.getElementById('hashtags').checked
  }), data => data.caption);
});
document.getElementById('ideasForm').addEventListener('submit', event => {
  event.preventDefault();
  submitDraft(event.currentTarget, document.getElementById('ideasStatus'), document.getElementById('ideasOutput'), '/ai/content-ideas', () => ({
    topic:document.getElementById('ideasTopic').value,
    count:Number(document.getElementById('ideasCount').value),
    format:document.getElementById('ideasFormat').value,
    language:document.getElementById('ideasLanguage').value
  }), data => data.ideas.map((idea, i) => (i+1)+'. '+idea.title+' ('+idea.format+')\nHook: '+idea.hook+'\nIdea: '+idea.concept+(idea.call_to_action?'\nCTA: '+idea.call_to_action:'')).join('\n\n'));
});
</script>
</body>
</html>
"""
    )
