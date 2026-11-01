from fastapi.responses import HTMLResponse

HOME_PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080713">
<meta name="description" content="NOVA is an AI-assisted Instagram content studio for captions, content ideas and creator workflows.">
<title>NOVA — Your AI Creator Studio</title>
<style>
:root{color-scheme:dark;--bg:#080713;--panel:#111020;--ink:#f8f7ff;--muted:#aaa7bd;--line:rgba(255,255,255,.11);--violet:#a78bfa;--pink:#f0abfc;--mint:#8df5d1;--max:1160px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;overflow-x:hidden}
body:before{content:"";position:fixed;inset:0;z-index:-2;background:radial-gradient(ellipse at 15% 5%,rgba(124,58,237,.22),transparent 38%),radial-gradient(ellipse at 88% 30%,rgba(219,39,119,.13),transparent 34%),radial-gradient(ellipse at 50% 100%,rgba(45,212,191,.09),transparent 42%)}
a{color:inherit;text-decoration:none}button{font:inherit}.wrap{width:min(var(--max),calc(100% - 40px));margin:auto}
nav{height:82px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:11px;font-weight:850;letter-spacing:.13em}.mark{width:39px;height:39px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#8b5cf6,#ec4899);box-shadow:0 8px 30px #8b5cf644;font-size:20px}
.links{display:flex;gap:30px;color:#c4c0d2;font-size:14px}.links a:hover{color:white}.nav-actions{display:flex;gap:10px;align-items:center}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:12px 19px;border-radius:13px;border:1px solid var(--line);font-weight:750;font-size:14px;transition:transform .2s,box-shadow .2s,background .2s;cursor:pointer}
.btn:hover{transform:translateY(-2px)}.primary{background:linear-gradient(110deg,#8b5cf6,#d946ef);border:0;box-shadow:0 10px 32px #a855f744;color:white}.ghost{background:rgba(255,255,255,.04)}
.menu{display:none;background:none;border:1px solid var(--line);color:white;border-radius:10px;padding:8px 11px}
.hero{padding:92px 0 76px;display:grid;grid-template-columns:1.05fr .95fr;gap:54px;align-items:center;min-height:610px}
.pill{display:inline-flex;align-items:center;gap:9px;border:1px solid #a78bfa55;background:#a78bfa12;border-radius:99px;padding:7px 13px;color:#d9ccff;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.dot{width:7px;height:7px;background:var(--mint);border-radius:50%;box-shadow:0 0 14px var(--mint)}
h1{font-size:clamp(48px,6.5vw,78px);line-height:1.02;letter-spacing:-.065em;margin:23px 0 20px;font-weight:850}h1 span{background:linear-gradient(100deg,#c4b5fd,#f0abfc 55%,#8df5d1);background-clip:text;color:transparent}
.lead{font-size:18px;max-width:570px;color:#b9b5c9;line-height:1.75}.hero-actions{display:flex;gap:13px;flex-wrap:wrap;margin-top:30px}.fine{font-size:12px;color:#858197;margin-top:18px}
.visual{position:relative;min-height:440px;display:grid;place-items:center}.orb{position:absolute;width:350px;height:350px;border-radius:50%;background:linear-gradient(135deg,#8b5cf655,#ec489955);filter:blur(45px);animation:float 7s ease-in-out infinite}
.mock{position:relative;width:min(100%,430px);padding:22px;border:1px solid #ffffff25;border-radius:28px;background:linear-gradient(145deg,#ffffff13,#ffffff05);backdrop-filter:blur(18px);box-shadow:0 30px 90px #0008;transform:rotate(2deg)}
.mock-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}.mock-title{font-weight:800}.live{font-size:11px;color:var(--mint);background:#8df5d115;padding:5px 9px;border-radius:99px}
.preview{border:1px solid var(--line);border-radius:19px;padding:17px;background:#0d0b19}.preview-top{display:flex;align-items:center;gap:10px;font-size:13px}.avatar{width:35px;height:35px;border-radius:50%;background:linear-gradient(135deg,#a78bfa,#f0abfc);display:grid;place-items:center;font-weight:900}.preview-art{height:155px;border-radius:14px;margin:15px 0;background:linear-gradient(135deg,#31205c,#7c3aed 48%,#ec4899);position:relative;overflow:hidden;display:grid;place-items:center}.preview-art:before,.preview-art:after{content:"";position:absolute;border:1px solid #ffffff55;border-radius:50%;width:220px;height:220px}.preview-art:after{width:145px;height:145px}.art-word{font-size:32px;font-weight:900;letter-spacing:-2px;z-index:1;text-shadow:0 3px 20px #0006}.lines{display:grid;gap:8px}.line{height:8px;background:#ffffff18;border-radius:20px}.line:nth-child(2){width:78%}.chips{display:flex;gap:7px;margin-top:14px;flex-wrap:wrap}.chip{font-size:10px;color:#d7c9ff;background:#a78bfa18;border:1px solid #a78bfa30;border-radius:99px;padding:5px 9px}
.float-card{position:absolute;padding:12px 15px;border:1px solid #ffffff22;background:#171327dd;backdrop-filter:blur(12px);border-radius:15px;box-shadow:0 14px 40px #0006;font-size:12px}.float-one{top:50px;right:-6px;animation:float 5s ease-in-out infinite}.float-two{bottom:55px;left:-18px;animation:float 6s ease-in-out infinite reverse}.float-card strong{display:block;font-size:14px}
section.content{padding:72px 0}.section-head{text-align:center;max-width:690px;margin:0 auto 38px}.kicker{color:var(--mint);font-size:12px;letter-spacing:.18em;text-transform:uppercase;font-weight:800}.section-head h2{font-size:clamp(32px,4vw,48px);letter-spacing:-.045em;line-height:1.1;margin:12px 0}.section-head p{color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:17px}.feature{border:1px solid var(--line);border-radius:21px;padding:24px;background:linear-gradient(145deg,#ffffff0b,#ffffff04);transition:transform .25s,border-color .25s}.feature:hover{transform:translateY(-5px);border-color:#a78bfa77}.ico{width:45px;height:45px;border-radius:14px;display:grid;place-items:center;background:#a78bfa1c;color:#d8c7ff;font-size:21px;margin-bottom:19px}.feature h3{margin:0 0 8px;font-size:18px}.feature p{margin:0;color:var(--muted);font-size:14px}
.workflow{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;counter-reset:step}.step{padding:22px;border-radius:18px;background:#ffffff08;border:1px solid var(--line)}.step b{color:var(--pink);font-size:12px;letter-spacing:.15em}.step h3{margin:10px 0 5px}.step p{color:var(--muted);font-size:14px;margin:0}
.status-panel{display:flex;align-items:center;justify-content:space-between;gap:20px;border:1px solid #8df5d133;background:linear-gradient(100deg,#8df5d10b,#a78bfa0c);border-radius:20px;padding:22px 25px}.status-panel p{color:var(--muted);margin:3px 0 0;font-size:13px}.status-tag{white-space:nowrap;color:var(--mint);font-size:12px;border:1px solid #8df5d144;padding:7px 11px;border-radius:99px}
.faq{max-width:790px;margin:auto}.faq details{border-bottom:1px solid var(--line);padding:18px 4px}.faq summary{cursor:pointer;font-weight:700;list-style:none}.faq summary:after{content:"+";float:right;color:var(--pink);font-size:20px}.faq details[open] summary:after{content:"−"}.faq p{color:var(--muted);font-size:14px;margin:12px 0 0}
.cta{padding:45px;border-radius:27px;border:1px solid #ffffff22;background:radial-gradient(ellipse at 20% 0,#8b5cf644,transparent 55%),linear-gradient(130deg,#171329,#171020);text-align:center}.cta h2{font-size:clamp(30px,4vw,45px);letter-spacing:-.04em;margin:0 0 9px}.cta p{color:var(--muted);margin:0 auto 22px;max-width:560px}
footer{padding:35px 0 45px;border-top:1px solid var(--line);color:#8f8ba1;font-size:12px}.foot{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}.footlinks{display:flex;gap:18px}
.reveal{opacity:0;transform:translateY(18px);transition:opacity .7s,transform .7s}.reveal.visible{opacity:1;transform:none}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-13px)}}
@media(max-width:850px){.hero{grid-template-columns:1fr;padding:65px 0 45px;gap:22px}.visual{min-height:400px}.grid{grid-template-columns:repeat(2,1fr)}.workflow{grid-template-columns:1fr}.links{display:none;position:absolute;top:72px;left:20px;right:20px;padding:18px;background:#171329;border:1px solid var(--line);border-radius:15px;flex-direction:column;gap:13px;z-index:10}.links.open{display:flex}.menu{display:block}.nav-actions .ghost{display:none}}
@media(max-width:560px){.wrap{width:min(var(--max),calc(100% - 28px))}nav{height:70px}.hero{padding-top:52px}.lead{font-size:16px}.visual{min-height:350px}.mock{padding:15px}.float-one{right:0;top:20px}.float-two{left:0;bottom:20px}.grid{grid-template-columns:1fr}.content{padding:52px 0!important}.status-panel{align-items:flex-start;flex-direction:column}.cta{padding:30px 18px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation:none!important;transition:none!important}.reveal{opacity:1;transform:none}}
</style>
</head>
<body>
<div class="wrap">
<nav aria-label="Main navigation">
<a class="brand" href="/"><span class="mark">N</span><span>NOVA</span></a>
<div class="links" id="navLinks"><a href="#features">Features</a><a href="#how">How it works</a><a href="#faq">FAQ</a><a href="/privacy">Privacy</a></div>
<div class="nav-actions"><a class="btn ghost" href="/app">Sign in</a><a class="btn primary" href="/app">Open Studio ↗</a><button class="menu" id="menuBtn" aria-label="Open navigation" aria-expanded="false">☰</button></div>
</nav>
<main>
<section class="hero">
<div>
<div class="pill"><span class="dot"></span> AI-assisted creator studio</div>
<h1>Your ideas.<br><span>NOVA's spark.</span></h1>
<p class="lead">A calmer, smarter space to plan Instagram content. Create caption drafts, explore fresh content ideas, and prepare your next post with AI assistance.</p>
<div class="hero-actions"><a class="btn primary" href="/app">Explore NOVA Studio <span>→</span></a><a class="btn ghost" href="#features">Discover features ↓</a></div>
<p class="fine">Built for creators · AI-generated drafts · You stay in control</p>
</div>
<div class="visual" aria-label="Illustration of the NOVA content studio">
<div class="orb"></div>
<div class="mock">
<div class="mock-head"><div class="mock-title">✦ NOVA Studio</div><span class="live">CREATIVE MODE</span></div>
<div class="preview"><div class="preview-top"><div class="avatar">N</div><div><strong>nova.creator</strong><div style="color:#9993ad;font-size:11px">Your next idea starts here</div></div></div>
<div class="preview-art"><span class="art-word">MAKE IT<br>MEMORABLE.</span></div>
<div class="lines"><div class="line"></div><div class="line"></div></div>
<div class="chips"><span class="chip">Caption ideas</span><span class="chip">Reels concepts</span><span class="chip">Manglish</span></div></div>
<div style="display:flex;justify-content:space-between;color:#a9a4bb;font-size:11px;margin-top:15px"><span>✧ Draft workspace</span><span>Made with NOVA</span></div>
</div>
<div class="float-card float-one">✦ AI writing<strong>Fresh caption ideas</strong></div>
<div class="float-card float-two">◈ Creator toolkit<strong>One idea at a time</strong></div>
</div>
</section>
<section class="content reveal" id="features">
<div class="section-head"><div class="kicker">Made for making</div><h2>Your creative sidekick</h2><p>Useful tools for the content workflow, with clear review steps before anything goes live.</p></div>
<div class="grid">
<article class="feature"><div class="ico">✍</div><h3>AI caption drafts</h3><p>Turn a topic into a caption draft with tone and language choices, including Manglish.</p></article>
<article class="feature"><div class="ico">✧</div><h3>Content ideas</h3><p>Explore original post, Reel and carousel concepts to help plan your content calendar.</p></article>
<article class="feature"><div class="ico">▧</div><h3>Image generation</h3><p>Prepare image concepts through a separately configured image provider when available.</p></article>
<article class="feature"><div class="ico">◎</div><h3>Instagram connection</h3><p>Connect an eligible professional account through Meta authorization. Access depends on approval and permissions.</p></article>
<article class="feature"><div class="ico">◇</div><h3>Canva workflow</h3><p>Canva design and export integration is available when the Canva app is configured and authorized.</p></article>
<article class="feature"><div class="ico">⌁</div><h3>Creator-first control</h3><p>Review your drafts and decide what to use. NOVA does not publish a draft just because it was generated.</p></article>
</div>
</section>
<section class="content reveal" id="how">
<div class="section-head"><div class="kicker">Simple workflow</div><h2>From thought to draft</h2><p>Keep the creative process clear and in your hands.</p></div>
<div class="workflow">
<div class="step"><b>01 / SHARE</b><h3>Bring your idea</h3><p>Start with a topic, niche, or the message you want your audience to remember.</p></div>
<div class="step"><b>02 / CREATE</b><h3>Explore with NOVA</h3><p>Generate caption drafts and content concepts, then edit them to fit your voice.</p></div>
<div class="step"><b>03 / REVIEW</b><h3>You choose what happens</h3><p>Check the result before using it. Publishing and account actions require separate authorization.</p></div>
</div>
</section>
<section class="content reveal">
<div class="status-panel"><div><strong>Service status</strong><p id="healthText">Checking NOVA service availability…</p></div><span class="status-tag" id="healthTag">Checking</span></div>
</section>
<section class="content reveal" id="faq">
<div class="section-head"><div class="kicker">A few details</div><h2>Good to know</h2></div>
<div class="faq">
<details><summary>Does NOVA automatically publish everything?</summary><p>No. Generating a caption or idea creates a draft. Instagram publishing requires a connected, eligible account, the necessary Meta permissions, and the relevant publishing workflow to be configured.</p></details>
<details><summary>Do I need an Instagram account?</summary><p>You can explore the public site without connecting one. Instagram account features require an eligible Professional or Creator account and Meta authorization.</p></details>
<details><summary>Is image generation always available?</summary><p>Only when a compatible image provider has been configured on the NOVA server. Availability and provider limits may vary.</p></details>
<details><summary>How is my data handled?</summary><p>Read the <a href="/privacy" style="color:#d7c5ff;text-decoration:underline">Privacy Policy</a> and <a href="/data-deletion" style="color:#d7c5ff;text-decoration:underline">Data Deletion Instructions</a> for details.</p></details>
</div>
</section>
<section class="content reveal"><div class="cta"><h2>Make room for your next idea.</h2><p>Open NOVA Studio and start shaping your next piece of content.</p><a class="btn primary" href="/app">Open NOVA Studio →</a></div></section>
</main>
<footer><div class="foot"><div>© <span id="year"></span> NOVA · AI-assisted creator tools</div><div class="footlinks"><a href="/privacy">Privacy</a><a href="/data-deletion">Data deletion</a><a href="/terms">Terms</a></div></div><p style="margin:16px 0 0">NOVA is an AI tool, not a human creator or an official Meta product. Instagram and Canva features are subject to their respective platform permissions and availability.</p></footer>
</div>
<script>
const menuBtn=document.getElementById('menuBtn'),navLinks=document.getElementById('navLinks');
menuBtn.addEventListener('click',()=>{const open=navLinks.classList.toggle('open');menuBtn.setAttribute('aria-expanded',String(open));menuBtn.textContent=open?'✕':'☰'});
navLinks.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{navLinks.classList.remove('open');menuBtn.setAttribute('aria-expanded','false');menuBtn.textContent='☰'}));
document.getElementById('year').textContent=new Date().getFullYear();
if('IntersectionObserver'in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target)}}),{threshold:.12});document.querySelectorAll('.reveal').forEach(el=>observer.observe(el))}else{document.querySelectorAll('.reveal').forEach(el=>el.classList.add('visible'))}
fetch('/health').then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{document.getElementById('healthText').textContent=data.ai_configured?'NOVA is online · AI provider configured':'NOVA is online · AI provider setup may be needed';document.getElementById('healthTag').textContent='● Online'}).catch(()=>{document.getElementById('healthText').textContent='Status could not be checked right now.';document.getElementById('healthTag').textContent='Unavailable'});
</script>
</body></html>"""
