# backend/app.py

import os
import asyncio
import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Literal, Annotated
from collections.abc import Generator

from fastapi import FastAPI, Request, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey, Text, func,
    UniqueConstraint, select, and_, or_
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

import httpx
from bs4 import BeautifulSoup

# OpenAI (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()  # good default; change if you prefer
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        _openai_client = None
else:
    _openai_client = None

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------
APP_TITLE = os.getenv("APP_TITLE", "Pocketish")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or "sqlite:///./app.db"
IS_SQLITE = DB_URL.startswith("sqlite:")

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
connect_args = {"check_same_thread": False} if IS_SQLITE else {}
engine = create_engine(DB_URL, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_session() -> Generator[Session, None, None]:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def normalize_url(raw: str) -> str:
    """
    Keep querystrings (as requested), drop fragments, normalize scheme/host case, strip default ports.
    """
    from urllib.parse import urlsplit, urlunsplit
    raw = (raw or "").strip()
    if not raw:
        return raw
    parts = urlsplit(raw)
    scheme = (parts.scheme or "http").lower()
    netloc = parts.netloc
    if ":" in netloc:
        host, port = netloc.rsplit(":", 1)
        host_l = host.lower()
        # strip default ports
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host_l
        else:
            netloc = f"{host_l}:{port}"
    else:
        netloc = netloc.lower()
    # keep path as-is, keep query, drop fragment
    path = parts.path or "/"
    query = parts.query
    frag = ""  # drop
    return urlunsplit((scheme, netloc, path, query, frag))

# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), default="")
    picture = Column(String(1024), default="")
    api_key = Column(String(128), unique=True, index=True, default=lambda: secrets.token_hex(32))
    created_at = Column(DateTime(timezone=True), default=now_utc)

    links = relationship("Link", back_populates="user", cascade="all, delete-orphan")

class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)  # sha256 hex of raw URL
    normalized_url = Column(Text, default="")
    normalized_url_hash = Column(String(64), default="")

    title = Column(Text, default="")
    summary = Column(Text, default="")
    category = Column(String(64), default="")

    status = Column(String(32), default="queued")  # queued|processing|ready|error
    archived_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user = relationship("User", back_populates="links")
    tags = relationship("LinkTag", back_populates="link", cascade="all, delete-orphan")

    # __table_args__ = (
    #     UniqueConstraint("user_id", "url_hash", name="uq_user_url"),
    # )

class LinkTag(Base):
    __tablename__ = "link_tags"
    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("links.id"), nullable=False, index=True)
    name = Column(String(64), nullable=False, index=True)
    submitted_by = Column(String(16), nullable=False, default="user")  # 'user' or 'system'
    created_at = Column(DateTime(timezone=True), default=now_utc)

    link = relationship("Link", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("link_id", "name", "submitted_by", name="uq_link_tag_name_role"),
    )

def init_db():
    Base.metadata.create_all(engine)

# ------------------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(title=APP_TITLE)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[BASE_URL, "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# OAuth (Google only)
# ------------------------------------------------------------------------------
from authlib.integrations.starlette_client import OAuth, OAuthError

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    client_kwargs={"scope": "openid email profile"},
)

def _redirect_uri_from_request(request: Request) -> str:
    # fallback to computed callback (ensure you visit the same host in your browser)
    return str(request.url_for("auth_callback"))

def get_db() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401, "not authenticated")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "session user not found")
    return user

# ------------------------------------------------------------------------------
# Scrape + AI enrich
# ------------------------------------------------------------------------------
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

async def fetch_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }) as client:
            r = await client.get(url)
            ct = r.headers.get("content-type", "")
            if "text/html" not in ct and "<html" not in r.text.lower():
                return ""
            return r.text or ""
    except Exception:
        return ""

def calculate_reading_time(text: str) -> int:
    """
    Calculate estimated reading time in minutes based on average reading speed of 200 WPM.
    Returns minimum of 1 minute.
    """
    if not text:
        return 1
    
    # Count words (split by whitespace)
    word_count = len(text.split())
    
    # Average reading speed is about 200 words per minute
    reading_time_minutes = max(1, round(word_count / 200))
    
    return reading_time_minutes

def _extract_text_from_html(html: str) -> Tuple[str, str]:
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"):
            title = ogt["content"].strip()

    # Prefer meta description, else concatenate first few <p>
    desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        desc = md["content"].strip()
    if not desc:
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        desc = " ".join(ps[:8]).strip()

    return title, desc

async def ai_enrich(url: str, title: str, context_text: str) -> Tuple[str, str, List[str]]:
    """
    Returns (summary, category, tags). If OpenAI isn't configured, returns simple fallbacks.
    """
    # Calculate reading time first
    reading_time = calculate_reading_time(context_text)
    
    if not _openai_client or not OPENAI_API_KEY:
        # Fallbacks with reading time
        fallback_summary = f"[{reading_time} min read] " + ((context_text[:340] + "…") if context_text else (title or url))
        return (
            fallback_summary,
            "Other",
            []
        )

    prompt = (
        "You are helping organize saved web links.\n"
        "Given the URL, title, and extracted text, produce a concise 2–3 sentence summary, "
        "a single high-level category (like Technology, Science, Business, Culture, Politics, Sports, Personal Finance, "
        "Programming, Product, Education, Health, Other), and 3–6 short, lowercase tags.\n"
        f"IMPORTANT: Start the summary with '[{reading_time} min read] ' followed by your summary.\n"
        "Return ONLY a compact JSON object with keys: summary, category, tags.\n"
        f"URL: {url}\n"
        f"Title: {title}\n"
        f"Text: {context_text[:4000]}\n"
    )

    try:
        # Chat Completions style
        resp = await asyncio.to_thread(
            _openai_client.chat.completions.create,
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a concise assistant that outputs strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = resp.choices[0].message.content.strip()
        # Basic JSON parse with a safety net
        import json
        try:
            data = json.loads(content)
        except Exception:
            # Try to salvage JSON if model added code fences
            content_stripped = content
            if content_stripped.startswith("```"):
                content_stripped = content_stripped.strip("`")
                # try to find {...}
            l = content_stripped.find("{")
            r = content_stripped.rfind("}")
            data = {}
            if l != -1 and r != -1 and r > l:
                try:
                    data = json.loads(content_stripped[l:r+1])
                except Exception:
                    data = {}
        summary = (data.get("summary") or "").strip() if isinstance(data, dict) else ""
        category = (data.get("category") or "").strip().title() if isinstance(data, dict) else ""
        tags = data.get("tags") if isinstance(data, dict) else []
        if not isinstance(tags, list):
            tags = []
        # Guardrails
        if not summary:
            summary = f"[{reading_time} min read] " + ((context_text[:340] + "…") if context_text else (title or url))
        elif not summary.startswith(f"[{reading_time} min read]"):
            # Ensure reading time is included if AI didn't follow instructions
            summary = f"[{reading_time} min read] {summary}"
        if not category:
            category = "Other"
        tags = [str(t).strip().lower()[:40] for t in tags if str(t).strip()]
        tags = tags[:6]
        return summary, category, tags
    except Exception:
        # Silent degrade with reading time
        fallback_summary = f"[{reading_time} min read] " + ((context_text[:340] + "…") if context_text else (title or url))
        return (
            fallback_summary,
            "Other",
            []
        )

# ------------------------------------------------------------------------------
# Queue + Worker (DB-polled)
# ------------------------------------------------------------------------------
WORKER_INTERVAL_SEC = float(os.getenv("WORKER_INTERVAL_SEC", "2.0"))

def enqueue_link(db: Session, user_id: int, url: str, title: str = "") -> int:
    url_clean = (url or "").strip()
    if not url_clean:
        raise HTTPException(400, "url required")

    normalized = normalize_url(url_clean)
    url_hash = sha256_hex(url_clean)
    normalized_hash = sha256_hex(normalized) if normalized else ""

    link = Link(
        user_id=user_id,
        url=url_clean,
        url_hash=url_hash,
        normalized_url=normalized,
        normalized_url_hash=normalized_hash,
        title=title or "",
        status="queued",
    )
    db.add(link)
    try:
        db.commit()
        db.refresh(link)
        return link.id
    except IntegrityError:
        db.rollback()
        # Already exists for this user+url
        existing_id = db.execute(
            select(Link.id).where(and_(Link.user_id == user_id, Link.url_hash == url_hash))
        ).scalar_one_or_none()
        if existing_id is None:
            raise
        return existing_id

async def _process_one(db: Session, link_id: int) -> None:
    link: Link = db.get(Link, link_id)
    if not link:
        return
    # Fetch
    html = await fetch_html(link.url)
    title_extracted, text_extracted = _extract_text_from_html(html)
    # Prefer existing title if user passed one; else extracted
    new_title = link.title or title_extracted
    summary, category, sys_tags = await ai_enrich(link.url, new_title or link.url, text_extracted)

    # Persist
    link.title = (new_title or link.title or link.url)[:512]
    link.summary = summary or link.summary
    link.category = category or link.category or "Other"
    link.status = "ready"
    link.updated_at = now_utc()

    # Upsert system tags (avoid duplicates)
    existing_sys = {
        t.name for t in link.tags if t.submitted_by == "system"
    }
    to_add = [t for t in sys_tags if t not in existing_sys]
    for name in to_add:
        db.add(LinkTag(link_id=link.id, name=name, submitted_by="system"))

    db.commit()

async def worker_loop():
    print("[worker] loop starting")
    while True:
        try:
            async with asyncio.timeout(WORKER_INTERVAL_SEC):
                await asyncio.sleep(WORKER_INTERVAL_SEC)
        except Exception:
            await asyncio.sleep(WORKER_INTERVAL_SEC)

        s = SessionLocal()
        try:
            # Fetch the next queued item
            link: Optional[Link] = s.execute(
                select(Link).where(Link.status == "queued").order_by(Link.created_at.asc()).limit(1)
            ).scalar_one_or_none()
            if not link:
                s.close()
                continue

            # Mark as processing
            link.status = "processing"
            s.commit()
            print(f"[worker] start {link.id}: fetching {link.url}")

            try:
                await _process_one(s, link.id)
                print(f"[worker] {link.id}: processing → ready")
            except Exception as e:
                # mark error
                l2 = s.get(Link, link.id)
                if l2:
                    l2.status = "error"
                    l2.updated_at = now_utc()
                    s.commit()
                print(f"[worker] {link.id}: processing → error ({e})")
        finally:
            s.close()

@app.on_event("startup")
async def on_startup():
    init_db()
    # schedule worker
    asyncio.create_task(worker_loop())
    print("[worker] scheduled background task")

# ------------------------------------------------------------------------------
# UI (inline HTML)
# ------------------------------------------------------------------------------
# ---- UI (principle-aligned) ----
INDEX_HTML = ("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pocketish</title>
<link rel="manifest" href="/manifest.webmanifest">
<style>
:root{
  --bg:#fff; --text:#111827; --muted:#6b7280; --border:#e5e7eb;
  --accent:#111827; --accent-weak:#374151; --chip:#f3f4f6; --chip-sys:#f9fafb;
}

*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji","Segoe UI Emoji", "Segoe UI Symbol";
}
.container{max-width:820px;margin:0 auto;padding:24px}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.brand{font-weight:700;letter-spacing:.2px}
header .meta{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:14px}

button, input{
  font:inherit;border:1px solid var(--border);border-radius:10px;padding:8px 12px;background:#fff;color:var(--text)
}
button{cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
button.ghost{background:transparent}
button:focus, input:focus{outline:3px solid #c7d2fe; outline-offset:1px; border-color:#93c5fd}
.row{display:flex;gap:8px;align-items:center}
.controls{gap:8px;margin:12px 0 16px}
.controls input{flex:1 1 280px}
#bmwrap{margin:12px 0 8px;color:var(--muted);font-size:14px}
#bm{display:inline-block;padding:6px 10px;border-radius:8px;border:1px dashed var(--border);text-decoration:none}

.card{
  border:1px solid var(--border);
  border-radius:14px;
  padding:14px 14px 10px;
  margin-bottom:12px;
  background:#fff;
}
.card .top{display:flex;gap:8px;align-items:baseline}
.card h3{font-size:16px;line-height:1.35;margin:0 0 4px 0;font-weight:600}
.card a.title{color:var(--accent);text-decoration:none}
.card a.title:hover{text-decoration:underline}
.card .aux{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
.card .summary{
  font-size:14px;color:#1f2937;margin:4px 0 8px 0;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
}
.card .summary.expanded{-webkit-line-clamp:unset}
.small-actions{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.small-actions button{font-size:12px;padding:6px 8px;border-radius:8px}
.group-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-right:6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}
.tag{background:var(--chip);padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid var(--border)}
.tag.sys{background:var(--chip-sys);color:#4b5563;border-style:dashed}
.tag.add{background:#fff;color:var(--accent-weak);border-style:dotted;cursor:text}
.tag-input{border:none;outline:none;min-width:60px}

.hr{height:1px;background:var(--border);margin:16px 0}

footer{color:var(--muted);font-size:12px;margin-top:24px}

.toast{
  position:fixed;left:50%;bottom:24px;transform:translateX(-50%);
  background:#111827;color:#fff;padding:10px 12px;border-radius:10px;font-size:14px;
  box-shadow:0 10px 30px rgba(0,0,0,.15);opacity:0;pointer-events:none;transition:opacity .2s, transform .2s;
}
.toast.show{opacity:1;transform:translateX(-50%) translateY(-4px)}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">Pocketish</div>
    <div class="meta" id="auth"></div>
  </header>

  <p id="bmwrap" style="display:none">
    Drag this to your bookmarks bar:
    <a id="bm" href="#">★ Save to Pocketish</a>
  </p>

  <div class="row controls">
    <input id="q" placeholder="Search ( / to focus )" aria-label="Search">
    <input id="tag" placeholder="Filter tag…" aria-label="Filter by tag">
    <button id="go" class="ghost">Go</button>
  </div>

  <div class="hr" role="presentation"></div>

  <div id="list" aria-live="polite" aria-busy="false"></div>

  <footer>Tip: press “/” to jump to search. Click a summary to expand.</footer>
</div>

<div id="toast" class="toast" role="status" aria-live="polite"></div>

<script>
(function(){
  const toast = (msg)=>{const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),1400);};

  // --- auth + bookmarklet
  async function me(){
    const r = await fetch('/api/me',{credentials:'include'});
    return r.ok ? r.json() : null;
  }
  (async ()=>{
    const data = await me();
    const auth = document.getElementById('auth');
    if(!data){
      auth.innerHTML = '<a href="/auth/login">Login with Google</a>';
    }else{
      const u = data.user||{};
      auth.innerHTML =
        (u.picture?('<img src="'+u.picture+'" alt="" style="height:22px;border-radius:999px;vertical-align:middle;margin-right:6px">'):'')
        + (u.name||u.email||'') + ' · <button id="logout" class="ghost">Logout</button>';
      document.getElementById('logout').onclick = async ()=>{
        await fetch('/auth/logout',{method:'POST'}); location.reload();
      };

      // Minimal-friction bookmarklet (opens /bm with URL+title)
      const ORIGIN = location.origin;
      const js = `(function(){var u=location.href,t=document.title;window.open('${ORIGIN}/bm?u='+encodeURIComponent(u)+'&t='+encodeURIComponent(t),'_blank','noopener');})()`;
      const a = document.getElementById('bm'); a.href='javascript:'+encodeURIComponent(js);
      document.getElementById('bmwrap').style.display='block';
    }
  })();

  // --- data
  async function load(){
    const list = document.getElementById('list');
    list.setAttribute('aria-busy','true');
    const q = document.getElementById('q').value.trim();
    const tag = document.getElementById('tag').value.trim();
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}`,{credentials:'include'});
    const data = r.ok ? await r.json() : {links:[]};
    list.innerHTML = '';
    for(const it of (data.links||[])){
      const el = document.createElement('div'); el.className='card';
      const created = new Date(it.created_at).toLocaleString();
      const userTags = (it.user_tags||[]).map(t=>`<span class="tag">${t}</span>`).join(' ');
      const sysTags  = (it.system_tags||[]).map(t=>`<span class="tag sys">${t}</span>`).join(' ');
      const summarySafe = (it.summary||'').replace(/</g,'&lt;');
      el.innerHTML = `
        <div class="top">
          <h3><a class="title" href="${it.url}" target="_blank" rel="noopener">${it.title||it.url}</a></h3>
          <div class="aux">${created} · ${it.status}</div>
        </div>
        <div class="summary" data-expand="false">${summarySafe||''}</div>
        <div class="small-actions">
          <button class="ghost js-expand">Toggle summary</button>
          ${it.archived_at ? `<button class="ghost js-unarchive" data-id="${it.id}">Unarchive</button>`
                           : `<button class="ghost js-archive" data-id="${it.id}">Archive</button>`}
        </div>
        <div>
          <span class="group-label">Your tags</span>
          <span class="tags">
            ${userTags}
            <span class="tag add">
              <input class="tag-input" data-id="${it.id}" placeholder="Add tag…">
            </span>
          </span>
        </div>
        ${sysTags ? `<div style="margin-top:6px"><span class="group-label">Suggested</span><span class="tags">${sysTags}</span></div>`:''}
      `;
      // interactions
      el.querySelector('.js-expand').onclick = ()=>{
        const s = el.querySelector('.summary');
        const expanded = s.getAttribute('data-expand') === 'true';
        s.setAttribute('data-expand', (!expanded).toString());
        s.classList.toggle('expanded', !expanded);
      };
      const input = el.querySelector('.tag-input');
      input.addEventListener('keydown', async (e)=>{
        if(e.key==='Enter'){
          const name = input.value.trim(); if(!name) return;
          const linkId = input.getAttribute('data-id');
          input.disabled = true;
          const rr = await fetch('/api/tag',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({link_id:linkId,name})});
          if(rr.ok){ toast('Tag added'); load(); } else { toast('Failed to add tag'); input.disabled=false; }
        }
      });
      const arch = el.querySelector('.js-archive');
      if(arch){ arch.onclick = async ()=>{
        const id = arch.getAttribute('data-id');
        const rr = await fetch(`/api/links/${id}/archive`,{method:'POST',credentials:'include'});
        toast(rr.ok ? 'Archived' : 'Archive failed'); if(rr.ok) load();
      };}
      const unarch = el.querySelector('.js-unarchive');
      if(unarch){ unarch.onclick = async ()=>{
        const id = unarch.getAttribute('data-id');
        const rr = await fetch(`/api/links/${id}/unarchive`,{method:'POST',credentials:'include'});
        toast(rr.ok ? 'Restored' : 'Restore failed'); if(rr.ok) load();
      };}
      list.appendChild(el);
    }
    list.setAttribute('aria-busy','false');
  }
  document.getElementById('go').onclick = load;
  // keyboard: "/" focuses search
  window.addEventListener('keydown',(e)=>{
    if(e.key==='/' && document.activeElement.tagName!=='INPUT'){ e.preventDefault(); document.getElementById('q').focus(); }
    if(e.key==='Enter' && document.activeElement.id==='q'){ load(); }
  });
  load();
})();
</script>
</body>
</html>
""").replace("__APP_TITLE__", APP_TITLE)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML)

@app.get("/manifest.webmanifest")
async def manifest():
    return JSONResponse({
        "name": APP_TITLE,
        "short_name": APP_TITLE,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#111827",
        "icons": [],
    })

# ------------------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------------------
@app.get("/auth/login")
async def auth_login(request: Request):
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI") or _redirect_uri_from_request(request)
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        print("[auth] token exchange failed:", e.error, e.description)
        raise HTTPException(401, "OAuth token exchange failed")

    userinfo = None

    # Prefer ID token
    if token and "id_token" in token:
        try:
            idinfo = await oauth.google.parse_id_token(request, token)
            userinfo = {
                "sub": idinfo.get("sub"),
                "email": idinfo.get("email"),
                "name": idinfo.get("name"),
                "picture": idinfo.get("picture"),
            }
        except Exception as e:
            print("[auth] parse_id_token failed:", repr(e))

    # Fallback to userinfo endpoint
    if not userinfo:
        try:
            resp = await oauth.google.get(
                "https://openidconnect.googleapis.com/v1/userinfo", token=token
            )
            userinfo = resp.json()
        except Exception as e:
            print("[auth] userinfo fetch failed:", repr(e))
            raise HTTPException(401, "Failed to fetch Google user info")

    email = (userinfo or {}).get("email")
    if not email:
        print("[auth] no email in userinfo:", userinfo)
        raise HTTPException(401, "Google account has no email")

    s = SessionLocal()
    try:
        user = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                name=userinfo.get("name") or "",
                picture=userinfo.get("picture") or "",
            )
            s.add(user)
            s.commit()
            s.refresh(user)
        else:
            changed = False
            nm = userinfo.get("name") or ""
            pic = userinfo.get("picture") or ""
            if nm and nm != user.name:
                user.name = nm; changed = True
            if pic and pic != user.picture:
                user.picture = pic; changed = True
            if changed:
                s.commit()

        request.session["user_id"] = user.id
    finally:
        s.close()

    return RedirectResponse("/", status_code=302)

@app.post("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})

# ------------------------------------------------------------------------------
# API
# ------------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/me")
async def api_me(user: User = Depends(get_current_user)):
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "api_key": user.api_key,
        }
    }

@app.get("/api/search")
async def api_search(
    request: Request,
    q: str = "",
    tag: str = "",
    show_archived: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (q or "").strip()
    tag = (tag or "").strip().lower()
    limit = max(1, min(limit, 500))

    stmt = select(Link).where(Link.user_id == user.id)
    if not show_archived:
        stmt = stmt.where(Link.archived_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Link.title.ilike(like),
            Link.url.ilike(like),
            Link.summary.ilike(like),
            Link.category.ilike(like),
        ))
    if tag:
        # Join across tags; both user/system count for filtering
        stmt = stmt.join(LinkTag).where(and_(LinkTag.name == tag))

    stmt = stmt.order_by(Link.created_at.desc()).limit(limit)
    rows: List[Link] = db.execute(stmt).scalars().all()

    result = []
    for l in rows:
        user_tags = [t.name for t in l.tags if t.submitted_by == "user"]
        system_tags = [t.name for t in l.tags if t.submitted_by == "system"]
        result.append({
            "id": l.id,
            "url": l.url,
            "title": l.title or l.url,
            "summary": l.summary or "",
            "category": l.category or "",
            "status": l.status,
            "created_at": (l.created_at or now_utc()).isoformat(),
            "user_tags": user_tags,
            "system_tags": system_tags,
        })
    return {"links": result}

@app.post("/api/links")
async def api_save_link(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    API key flow (for Share Sheet etc):
    - Provide ?api_key=... or header X-API-Key: ...
    """
    api_key = request.query_params.get("api_key") or request.headers.get("x-api-key") or ""
    if not api_key:
        raise HTTPException(401, "missing api key")

    user = db.execute(select(User).where(User.api_key == api_key)).scalar_one_or_none()
    if not user:
        raise HTTPException(401, "invalid api key")

    url = (payload.get("url") or "").strip()
    title = (payload.get("title") or "").strip()
    if not url:
        raise HTTPException(400, "url required")

    link_id = enqueue_link(db, user.id, url, title)
    return {"ok": True, "id": link_id}

@app.get("/bm", response_class=HTMLResponse)
async def bookmarklet_capture(request: Request, u: str = "", t: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Bookmarklet target. Uses session cookie, not API key.
    """
    url = (u or "").strip()
    title = (t or "").strip()
    if not url:
        return HTMLResponse("<p>Missing URL</p>", status_code=400)
    link_id = enqueue_link(db, user.id, url, title)
    return HTMLResponse("<p>Saved! You can close this tab.</p>")

@app.post("/api/links/{link_id}/archive")
async def archive_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Link, link_id)
    if not l or l.user_id != user.id:
        raise HTTPException(404, "link not found")
    l.archived_at = now_utc()
    db.commit()
    return {"ok": True}

@app.post("/api/links/{link_id}/unarchive")
async def unarchive_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Link, link_id)
    if not l or l.user_id != user.id:
        raise HTTPException(404, "link not found")
    l.archived_at = None
    db.commit()
    return {"ok": True}

@app.post("/api/links/{link_id}/tags")
async def add_user_tag(link_id: int, payload: Dict[str, str] = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = (payload.get("name") or "").strip().lower()
    if not name:
        raise HTTPException(400, "name required")
    l = db.get(Link, link_id)
    if not l or l.user_id != user.id:
        raise HTTPException(404, "link not found")
    # upsert user tag
    exists = db.execute(
        select(LinkTag.id).where(and_(LinkTag.link_id == link_id, LinkTag.name == name, LinkTag.submitted_by == "user"))
    ).scalar_one_or_none()
    if not exists:
        db.add(LinkTag(link_id=link_id, name=name, submitted_by="user"))
        db.commit()
    return {"ok": True}

@app.delete("/api/links/{link_id}/tags/{name}")
async def remove_user_tag(link_id: int, name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = (name or "").strip().lower()
    l = db.get(Link, link_id)
    if not l or l.user_id != user.id:
        raise HTTPException(404, "link not found")
    tag_row = db.execute(
        select(LinkTag).where(and_(
            LinkTag.link_id == link_id, LinkTag.name == name, LinkTag.submitted_by == "user"
        ))
    ).scalar_one_or_none()
    if tag_row:
        db.delete(tag_row)
        db.commit()
    return {"ok": True}

@app.get("/api/tags")
async def suggest_tags(suggest: str = "", limit: int = 12, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Suggest from this user's historic tag usage (both user/system), preferring user tags.
    """
    suggest = (suggest or "").strip().lower()
    limit = max(1, min(limit, 50))

    # Find distinct tags used by this user across their links
    q = select(LinkTag.name, LinkTag.submitted_by).join(Link).where(Link.user_id == user.id)
    if suggest:
        q = q.where(LinkTag.name.ilike(f"{suggest}%"))
    rows = db.execute(q).all()
    # Prefer 'user' tags first, then system
    user_first = sorted(rows, key=lambda x: 0 if x[1] == "user" else 1)
    seen = set()
    out = []
    for name, _role in user_first:
        if name not in seen:
            seen.add(name)
            out.append(name)
        if len(out) >= limit:
            break
    return {"tags": out}

class TagCreate(BaseModel):
    link_id: int
    name: str

@app.post("/api/tag")
def api_add_tag(data: TagCreate, user: User = Depends(get_current_user), s: Session = Depends(get_session)):
    # Verify link belongs to user
    link = s.get(Link, data.link_id)
    if not link or link.user_id != user.id:
        raise HTTPException(status_code=404, detail="Link not found")

    # Normalize + enforce model limits
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty tag")
    if len(name) > 64:  # matches String(64)
        name = name[:64]

    # Case-insensitive de-dupe for *user* role on this link
    exists = (
        s.query(LinkTag)
         .filter(
             LinkTag.link_id == link.id,
             func.lower(LinkTag.name) == name.lower(),
             LinkTag.submitted_by == "user",
         )
         .first()
    )
    if not exists:
        try:
            s.add(LinkTag(link_id=link.id, name=name, submitted_by="user"))
            s.commit()
        except IntegrityError:
            s.rollback()  # unique(link_id,name,submitted_by) might have raced

    # Return split lists to match UI need
    tags = s.query(LinkTag).filter_by(link_id=link.id).all()
    return {
        "ok": True,
        "user_tags": [t.name for t in tags if t.submitted_by == "user"],
        "system_tags": [t.name for t in tags if t.submitted_by == "system"],
    }


class TagDelete(BaseModel):
    link_id: int
    name: str

@app.delete("/api/tag")
def api_delete_tag(data: TagDelete, user: User = Depends(get_current_user), s: Session = Depends(get_session)):
    link = s.get(Link, data.link_id)
    if not link or link.user_id != user.id:
        raise HTTPException(status_code=404, detail="Link not found")

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Empty tag")

    # Only remove user-submitted tags
    q = (
        s.query(LinkTag)
         .filter(
             LinkTag.link_id == link.id,
             func.lower(LinkTag.name) == name.lower(),
             LinkTag.submitted_by == "user",
         )
    )
    deleted = q.delete(synchronize_session=False)
    if deleted:
        s.commit()

    tags = s.query(LinkTag).filter_by(link_id=link.id).all()
    return {
        "ok": True,
        "user_tags": [t.name for t in tags if t.submitted_by == "user"],
        "system_tags": [t.name for t in tags if t.submitted_by == "system"],
    }

# Health
@app.get("/healthz")
async def healthz():
    return PlainTextResponse("ok")