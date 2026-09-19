import os
import re
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.search import (
    search_knowledge_base,
    extract_source,
)

from rag.generator import generate_answer
from rag.live_search import search_tmu, fetch_page_text


app = FastAPI(title="TMU AI Student Assistant")


# ==============================
# CORS
# ==============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tmu-ai-student-assistant.vercel.app",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# SESSION MEMORY
# ==============================

SESSION_HISTORY = {}
MAX_HISTORY = 6


# ==============================
# REQUEST MODEL
# ==============================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


# ==============================
# ROOT
# ==============================

@app.get("/")
def home():
    return {"message": "TMU AI Student Assistant API is running"}


# ==============================
# RESOURCES
# ==============================

DATA_FILE = "data/tmu_data.txt"


def _extract_source_urls():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    urls = re.findall(r"^SOURCE:\s*(.+)$", content, re.MULTILINE)

    seen = set()
    out = []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _friendly_name(url):
    path = url.split("?")[0].rstrip("/")
    last = path.split("/")[-1]
    if last.lower().endswith(".pdf"):
        last = last[:-4]
    name = last.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name.title() if name else "TMU Document"


def _categorize_pdf(url):
    u = url.lower()
    if "/announcement/" in u or "circular" in u or "notice" in u:
        return "Circulars & Notices"
    if "syllabus" in u or "curriculum" in u:
        return "Syllabus"
    if "form" in u or "template" in u or "format" in u or "synopsis" in u:
        return "Forms & Templates"
    if "exam" in u or "admit" in u or "date sheet" in u or "datesheet" in u:
        return "Examination"
    if "scholarship" in u:
        return "Scholarships"
    if "policy" in u or "sop" in u or "ordinance" in u:
        return "Policies & Ordinances"
    if "result" in u:
        return "Results"
    if "hostel" in u:
        return "Hostel"
    if "fee" in u:
        return "Fees"
    return "Other Documents"


@app.get("/resources")
def get_resources():
    urls = _extract_source_urls()
    pages = []
    pdf_groups = defaultdict(list)

    for url in urls:
        if not url.startswith("https://"):
            continue
        if "tmu.ac.in" not in url:
            continue

        if ".pdf" in url.lower():
            category = _categorize_pdf(url)
            pdf_groups[category].append({
                "url": url,
                "name": _friendly_name(url),
            })
        else:
            pages.append({
                "url": url,
                "name": _friendly_name(url),
            })

    order = [
        "Examination", "Circulars & Notices", "Forms & Templates",
        "Syllabus", "Scholarships", "Policies & Ordinances",
        "Results", "Fees", "Hostel", "Other Documents",
    ]

    sorted_groups = []
    for c in order:
        if c in pdf_groups:
            sorted_groups.append({
                "category": c,
                "items": sorted(pdf_groups[c], key=lambda x: x["name"]),
            })

    total_pdfs = sum(len(g["items"]) for g in sorted_groups)

    return {
        "pages": sorted(pages, key=lambda x: x["name"]),
        "pdf_groups": sorted_groups,
        "total_pdfs": total_pdfs,
    }


# ==============================
# CHAT (with live-search fallback)
# ==============================

@app.post("/chat")
def chat(request: ChatRequest):
    question = request.message.strip()
    session_id = request.session_id or "default"

    if not question:
        return {"answer": "Please enter a question.", "sources": []}

    history = SESSION_HISTORY.get(session_id, [])

    # ---- Step 1: try the local knowledge base ----
    results = search_knowledge_base(question, max_results=3)

    sources = []
    context_parts = []

    for result in results:
        context_parts.append(result)
        source = extract_source(result)
        if source and source not in sources:
            sources.append(source)

    context = "\n\n".join(context_parts)

    # ---- Step 2: if KB is thin, use live search ----
    live_used = False

    if not results or len(context) < 300:
        try:
            live_results = search_tmu(question, max_results=3)
        except Exception:
            live_results = []

        if live_results:
            live_parts = []
            for r in live_results[:2]:
                page_text = fetch_page_text(r["url"])
                if page_text:
                    live_parts.append(
                        f"SOURCE: {r['url']}\n{'-'*40}\n{page_text}"
                    )
                    if r["url"] not in sources:
                        sources.append(r["url"])

            if live_parts:
                context = (context + "\n\n" + "\n\n".join(live_parts)).strip()
                live_used = True

    # ---- Step 3: nothing at all ----
    if not context:
        history.append({"role": "user", "content": question})
        SESSION_HISTORY[session_id] = history[-MAX_HISTORY:]

        return {
            "answer": (
                "I couldn't find this information in the "
                "available official TMU sources. "
                "Please check the official TMU website "
                "or contact the relevant university department."
            ),
            "sources": [],
        }

    # ---- Step 4: generate ----
    answer = generate_answer(question, context, history=history)

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    SESSION_HISTORY[session_id] = history[-MAX_HISTORY:]

    return {
        "answer": answer,
        "sources": sources,
        "live": live_used,
    }