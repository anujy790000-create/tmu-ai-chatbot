import os
import re
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY is missing from .env")


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
    timeout=45.0
)


# ==============================
# MODEL CONFIGURATION
# ==============================
# 12 free models — maximises chance one succeeds when
# the shared OpenRouter pool is congested. Non-reasoning
# models first; reasoning models last.

MODEL_FALLBACKS = [
    # Tier 1: reliable non-reasoning
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",

    # Tier 2: other reliable models
    "z-ai/glm-5.2:free",
    "qwen/qwen3.8-27b:free",
    "deepseek/deepseek-v4-flash-0731:free",
    "dots-studio/dots-3-note-preview:free",

    # Tier 3: last-resort options
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "nex-agi/nex-n2.5-pro:free",
]

MODEL = MODEL_FALLBACKS[0]


# ==============================
# PROMPT BUILDER
# ==============================

def _build_prompt(question, context, history):

    history_text = ""

    if history:

        lines = []

        for turn in history[-4:]:

            role = (
                "Student"
                if turn["role"] == "user"
                else "Assistant"
            )

            lines.append(f"{role}: {turn['content']}")

        history_text = "\n".join(lines)


    return f"""You are the TMU AI Student Assistant.

Answer the student's question using ONLY the official TMU information below.

STRICT OUTPUT RULES:

1. Start directly with the answer. Do NOT begin with phrases like
   "Looking through", "Based on", "According to the document",
   "I see", "I found", "The user is asking", or any preamble.

2. Output ONLY the final answer. No reasoning, no analysis.

3. Keep the answer SHORT — 2 sentences maximum.

4. Do NOT quote documents verbatim. Summarize in your own words.

5. Do NOT mention chapter numbers, section numbers, or document names.

6. If different programs have different rules, give the general rule
   first for BCA/B.Tech students.

7. If the user asks for specific dates (exam dates, deadlines) and
   the exact dates are not in the context, tell them WHERE to find
   them (e.g. "Check the latest circular at
   https://www.tmu.ac.in/tmu/cbcs-circulars") instead of saying
   "I couldn't find".

8. If NO relevant information is in the context at all, say exactly:
   "I couldn't find this information in the available official TMU sources."

9. Preserve dates, percentages, and deadlines exactly.

10. Never claim access to private student information.

11. Do not write "Source:" or list retrieved documents.

12. You MAY mention a URL only if it appears in the context below.

13. Do not repeat the question.

14. Do not use Markdown symbols such as ** or ##.

15. Answer directly in plain text.

{f"Recent conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}

Student question:
{question}

Official TMU information:
{context}

Answer (2 sentences max, no introduction):
"""


# ==============================
# CLEAN RESPONSE
# ==============================

REASONING_PREFIXES = (
    "the user is asking",
    "the user wants",
    "the student is asking",
    "i need to",
    "i should",
    "i will check",
    "let me",
    "looking at",
    "looking through",
    "searching",
    "to answer",
    "here is what",
    "here's what",
    "i see",
    "i found",
    "based on the provided",
    "based on the context",
    "based on the documents",
    "according to the document",
)


def _clean_answer(answer):

    if not answer:
        return answer

    answer = answer.strip()

    sentences = re.split(r"(?<=[.!?])\s+", answer)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return answer

    # Strip leading reasoning sentences only
    while sentences:
        first_lower = sentences[0].lower()
        if any(first_lower.startswith(p) for p in REASONING_PREFIXES):
            sentences.pop(0)
        else:
            break

    # If everything was stripped, keep the last sentence
    if not sentences:
        all_s = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
        if all_s:
            sentences = [all_s[-1]]
        else:
            return answer

    sentences = sentences[:3]
    cleaned = " ".join(sentences)

    # Remove trailing soft phrases
    cut_phrases = [
        "let me know if",
        "i hope this helps",
        "feel free to ask",
        "if you have any",
    ]
    lower = cleaned.lower()
    for phrase in cut_phrases:
        idx = lower.find(phrase)
        if idx > 0:
            cleaned = cleaned[:idx].strip().rstrip(".,;:")
            lower = cleaned.lower()

    if len(cleaned) > 500:
        cleaned = cleaned[:500].rsplit(" ", 1)[0] + "…"

    return cleaned.strip()


# ==============================
# ERROR HELPERS
# ==============================

def _is_rate_limit(error):
    s = str(error).lower()
    return "429" in s or ("rate" in s and "limit" in s)


def _retry_after(error):
    s = str(error)
    match = re.search(r"retry_after_seconds['\"]?\s*:\s*['\"]?(\d+)", s)
    if match:
        return min(int(match.group(1)), 15)
    return None


# ==============================
# SINGLE MODEL CALL
# ==============================

def _try_model(model, prompt, attempts=2):

    last_error = None

    for attempt in range(attempts):

        try:

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400
            )

            if not response.choices:
                raise RuntimeError("Empty response")

            choice = response.choices[0]
            raw = choice.message.content

            if not raw:
                raise RuntimeError("Empty answer content")

            cleaned = _clean_answer(raw)

            return cleaned

        except Exception as error:

            last_error = error

            if _is_rate_limit(error) and attempt < attempts - 1:
                delay = _retry_after(error) or 2
                print(f"  -> 429, waiting {delay}s...")
                time.sleep(delay)
                continue

            raise

    raise last_error


# ==============================
# PUBLIC ENTRY POINT
# ==============================

def generate_answer(question, context, history=None):

    prompt = _build_prompt(question, context, history)

    last_error = None

    for i, model in enumerate(MODEL_FALLBACKS, 1):

        try:

            print(f"[{i}/{len(MODEL_FALLBACKS)}] Trying: {model}")

            answer = _try_model(model, prompt, attempts=2)

            print(f"  OK — {model}")

            return answer

        except Exception as error:

            last_error = error

            print(f"  X {type(error).__name__}: {str(error)[:150]}")

            msg = str(error).lower()

            if "invalid api key" in msg or "401" in msg:
                break

            continue


    print()
    print("========== ALL MODELS FAILED ==========")
    print(last_error)
    print("=======================================")
    print()

    msg = str(last_error).lower() if last_error else ""

    if "invalid api key" in msg or "401" in msg:
        return (
            "The AI service authentication failed. "
            "Please contact the administrator."
        )

    if "402" in msg or "insufficient" in msg or "credits" in msg:
        return (
            "The AI service is out of credits. "
            "Please check your OpenRouter balance."
        )

    if "429" in msg or "rate limit" in msg:
        return (
            "The free AI models are all busy right now. "
            "Please wait 30–60 seconds and try again."
        )

    if "timeout" in msg or "timed out" in msg:
        return (
            "The AI service took too long to respond. "
            "Please try again in a moment."
        )

    return (
        "I couldn't generate the answer right now. "
        "Please try again in a moment."
    )