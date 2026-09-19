import os
import re
from collections import defaultdict
from typing import Optional, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.search import (
    search_knowledge_base,
    extract_source
)

from rag.generator import generate_answer


app = FastAPI(
    title="TMU AI Student Assistant"
)


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
# HOME
# ==============================

@app.get("/")
def home():
    return {
        "message": "TMU AI Student Assistant API is running"
    }


# ==============================
# RESOURCES HELPERS
# ==============================

DATA_FILE = "data/tmu_data.txt"


def _extract_source_urls():
    """Read the knowledge base and pull every SOURCE: URL."""

    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    urls = re.findall(
        r"^SOURCE:\s*(.+)$",
        content,
        re.MULTILINE
    )

    seen = set()
    result = []

    for url in urls:
        url = url.strip()
        if url and url not in seen:
            seen.add(url)
            result.append(url)

    return result


def _friendly_name(url):
    """Turn a URL into a human-readable name."""

    path = url.split("?")[0].rstrip("/")
    last = path.split("/")[-1]

    if last.lower().endswith(".pdf"):
        last = last[:-4]

    name = last.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()

    if not name:
        return "TMU Document"

    return name.title()


def _categorize_pdf(url):
    """Assign a PDF to a category based on its URL."""

    u = url.lower()

    if "/announcement/" in u or "circular" in u or "notice" in u:
        return "Circulars & Notices"

    if "syllabus" in u or "curriculum" in u:
        return "Syllabus"

    if "form" in u or "template" in u or "format" in u:
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


# ==============================
# RESOURCES ENDPOINT
# ==============================

@app.get("/resources")
def get_resources():
    """Return all TMU pages and PDFs found by the scraper."""

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

    # Sort groups by a preferred order
    order = [
        "Examination",
        "Circulars & Notices",
        "Forms & Templates",
        "Syllabus",
        "Scholarships",
        "Policies & Ordinances",
        "Results",
        "Fees",
        "Hostel",
        "Other Documents",
    ]

    sorted_groups = []

    for category in order:
        if category in pdf_groups:
            items = sorted(
                pdf_groups[category],
                key=lambda x: x["name"]
            )
            sorted_groups.append({
                "category": category,
                "items": items,
            })

    total_pdfs = sum(
        len(g["items"]) for g in sorted_groups
    )

    return {
        "pages": sorted(pages, key=lambda x: x["name"]),
        "pdf_groups": sorted_groups,
        "total_pdfs": total_pdfs,
    }


# ==============================
# CHAT
# ==============================

@app.post("/chat")
def chat(request: ChatRequest):

    question = request.message.strip()
    session_id = request.session_id or "default"

    if not question:
        return {
            "answer": "Please enter a question.",
            "sources": []
        }

    history = SESSION_HISTORY.get(session_id, [])

    results = search_knowledge_base(
        question,
        max_results=3
    )

    if not results:

        history.append({"role": "user", "content": question})
        SESSION_HISTORY[session_id] = history[-MAX_HISTORY:]

        return {
            "answer": (
                "I couldn't find this information in the "
                "available official TMU sources. "
                "Please check the official TMU website "
                "or contact the relevant university department."
            ),
            "sources": []
        }

    context_parts = []
    sources = []

    for result in results:

        context_parts.append(result)

        source = extract_source(result)

        if source and source not in sources:
            sources.append(source)

    context = "\n\n".join(context_parts)

    answer = generate_answer(
        question,
        context,
        history=history
    )

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    SESSION_HISTORY[session_id] = history[-MAX_HISTORY:]

    return {
        "answer": answer,
        "sources": sources
    }