import os, json, time, asyncio, re
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import select
from openai import OpenAI
from backend.db import SessionLocal, init_db
from backend.models import Link, Tag, LinkTag
from backend.utils import fetch_html, extract_content

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def oai():
    return OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def calculate_reading_time(text: str) -> int:
    """Calculate estimated reading time in minutes based on 200 WPM."""
    if not text:
        return 1
    word_count = len(text.split())
    return max(1, round(word_count / 200))

def llm(title: str, desc: str, body: str):
    client = oai()
    reading_time = calculate_reading_time(body)
    
    if not client:
        # fallback with reading time
        summary = (desc or body[:400]).strip()
        summary = re.sub(r"\\s+", " ", summary)[:460]  # Leave room for reading time prefix
        return {"summary": f"[{reading_time} min read] {summary}", "tags": ["web","read"], "category":"Other"}
    
    prompt = f"""
You organize saved web links. Return JSON with fields:
summary (<=80 words), tags (3-6 lowercase nouns), category (Technology|Science|Business|Culture|Health|Education|Entertainment|Finance|Politics|Sports|Other).
IMPORTANT: Start the summary with '[{reading_time} min read] ' followed by your summary.
Title: {title}
Description: {desc}
Content (truncated): {body[:4000]}
JSON only:
"""
    resp = client.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], temperature=0.2)
    txt = resp.choices[0].message.content
    try:
        data = json.loads(txt)
        # Ensure reading time prefix is included
        summary = data.get("summary", "")
        if summary and not summary.startswith(f"[{reading_time} min read]"):
            data["summary"] = f"[{reading_time} min read] {summary}"
        return data
    except Exception:
        m = re.search(r"\\{[\\s\\S]*\\}", txt)
        fallback_data = json.loads(m.group(0)) if m else {"summary": txt, "tags": [], "category": "Other"}
        # Ensure fallback also has reading time
        summary = fallback_data.get("summary", "")
        if summary and not summary.startswith(f"[{reading_time} min read]"):
            fallback_data["summary"] = f"[{reading_time} min read] {summary}"
        return fallback_data\n\n\ndef upsert_tags(s, link: Link, names):\n    existing = {t.name: t for t in s.query(Tag).filter(Tag.name.in_(list(names))).all()}\n    for name in names:\n        tag = existing.get(name)\n        if not tag:\n            tag = Tag(name=name); s.add(tag); s.flush()\n        s.merge(LinkTag(link_id=link.id, tag_id=tag.id))\n\n\ndef process_link(link_id: int):\n    with SessionLocal() as s:\n        link = s.get(Link, link_id)\n        if not link: return\n        link.status = \"processing\"; s.commit()\n        try:\n            html = asyncio.get_event_loop().run_until_complete(fetch_html(link.url))\n            t, d, body = extract_content(html, link.title or \"\")\n            out = llm(t, d, body)\n            link.title = t or link.title\n            link.summary = out.get(\"summary\",\"\")\n            link.category = out.get(\"category\",\"Other\")\n            s.commit()\n            upsert_tags(s, link, [str(x)[:64] for x in out.get(\"tags\", [])])\n            link.status = \"ready\"; s.commit()\n        except Exception:\n            link.status = \"error\"; s.commit()\n\n\ndef main():\n    init_db()\n    # Poll for links in 'queued' state as a simple local worker\n    while True:\n        with SessionLocal() as s:\n            items = s.execute(select(Link).where(Link.status == \"queued\")).scalars().all()\n            for it in items:\n                process_link(it.id)\n        time.sleep(2)\n\nif __name__ == \"__main__\":\n    main()\n