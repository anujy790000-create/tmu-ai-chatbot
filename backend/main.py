from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# LIGHTWEIGHT SESSION MEMORY
# ==============================
# Stores the last few messages per session ID.
# Cleared when server restarts — no database needed.

SESSION_HISTORY = {}
MAX_HISTORY = 6  # last 3 user + 3 assistant messages


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

    # Get recent history for this session
    history = SESSION_HISTORY.get(session_id, [])

    # Search official TMU knowledge base
    results = search_knowledge_base(
        question,
        max_results=3
    )

    if not results:

        # Still record the question in history
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

    # Generate AI answer with conversation context
    answer = generate_answer(
        question,
        context,
        history=history
    )

    # Update session history
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    SESSION_HISTORY[session_id] = history[-MAX_HISTORY:]

    return {
        "answer": answer,
        "sources": sources
    }