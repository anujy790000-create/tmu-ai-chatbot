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

MODEL_FALLBACKS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "z-ai/glm-5.2:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
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

1. Start your answer DIRECTLY with the information. Never begin with
   any of these phrases:
   - "Looking through..."
   - "Looking at..."
   - "I see..."
   - "I found..."
   - "The user is asking..."
   - "Based on..."
   - "According to the document..."
   - "Let me..."
   - "Here is what I found..."
   - "The documents mention..."

2. Output ONLY the final answer. No reasoning, no thinking, no analysis.

3. Keep the answer SHORT — 2 sentences maximum. No exceptions.

4. Do NOT quote documents verbatim. Summarize in your own words.

5. Do NOT mention chapter numbers, section numbers, or document names
   (no "Chapter 5", "Academic Ordinance 2022", "section 7.1", etc).

6. Give the general rule for BCA/B.Tech/regular programs. Only mention
   other programs (Pharmacy, Medical, Nursing, Dental) if the question
   is specifically about them.

7. If the information is not present, say exactly:
   "I couldn't find this information in the available official TMU sources."

8. Preserve dates, percentages, and deadlines exactly.

9. Never claim access to private student information.

10. Do not write "Source:" or list retrieved documents.

11. You MAY mention a URL only if it appears in the context below. When
    the user asks "where can I find X", include the relevant URL.

12. Do not repeat the question.

13. Do not use Markdown symbols such as ** or ##.

14. Answer directly in plain text.

{f"Recent conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}

Student question:
{question}

Official TMU information:
{context}

Answer (2 sentences max, start directly with the answer, no intro):
"""


# ==============================
# CLEAN RESPONSE
# ==============================

# Sentence-starting patterns that indicate the model is narrating
# its own reasoning rather than answering the question.
REASONING_STARTS = (
    "the user",
    "the student",
    "i need",
    "i should",
    "i will",
    "i'll",
    "i see",
    "i found",
    "i can see",
    "let me",
    "looking",
    "based on",
    "from the",
    "from this",
    "first,",
    "first i",
    "now,",
    "now i",
    "to answer",
    "searching",
    "checking",
    "considering",
    "given the",
    "reviewing",
    "according to",
    "here is",
    "here's",
    "the document",
    "the documents",
    "the provided",
    "the context",
    "the information provided",
    "we can see",
    "we see",
)


def _clean_answer(answer):
    """
    Filter at the sentence level: drop any sentence that looks like
    reasoning, keep only real answer sentences.
    """

    if not answer:
        return answer

    answer = answer.strip()

    # ---- 1) Split into sentences ----
    # Split on period/exclamation/question followed by space, AND on
    # newlines. This catches sentences ending in colons too.
    chunks = re.split(r"(?<=[.!?])\s+|\n+", answer)

    # ---- 2) Filter ----
    real_sentences = []

    for s in chunks:

        s = s.strip()

        if not s:
            continue

        # Remove stray markdown / bullets
        s = re.sub(r"^[-*\u2022\d.)\s]+", "", s).strip()

        if len(s) < 15:
            continue

        s_lower = s.lower()

        # Skip sentences that start with a reasoning marker
        if any(s_lower.startswith(m) for m in REASONING_STARTS):
            continue

        real_sentences.append(s)

    # ---- 3) Decide what to return ----

    if not real_sentences:
        # The model produced ONLY reasoning. Don't leak it.
        # Return a short, honest message.
        return (
            "I couldn't generate a clean answer right now. "
            "Please try rephrasing your question."
        )

    # Keep at most 3 sentences
    real_sentences = real_sentences[:3]

    cleaned = " ".join(real_sentences)

    # ---- 4) Remove trailing soft phrases ----
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

    # ---- 5) Hard length cap ----
    if len(cleaned) > 450:
        cleaned = cleaned[:450].rsplit(" ", 1)[0] + "…"

    return cleaned.strip()


# ==============================
# ERROR HELPERS
# ==============================

def _is_rate_limit(error):

    s = str(error).lower()

    return "429" in s or ("rate" in s and "limit" in s)


def _retry_after(error):

    s = str(error)

    match = re.search(
        r"retry_after_seconds['\"]?\s*:\s*['\"]?(\d+)",
        s
    )

    if match:
        return min(int(match.group(1)), 15)

    return None


# ==============================
# SINGLE MODEL CALL WITH RETRY
# ==============================

def _try_model(model, prompt, attempts=2):

    last_error = None

    for attempt in range(attempts):

        try:

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=400
            )

            if not response.choices:
                raise RuntimeError("Empty response")

            choice = response.choices[0]

            print(f"  finish_reason: {choice.finish_reason}")

            raw = choice.message.content

            if not raw:
                raise RuntimeError("Empty answer content")

            if choice.finish_reason == "length":
                print("  WARNING: response truncated by max_tokens")

            print(f"  raw length: {len(raw)}")

            cleaned = _clean_answer(raw)

            print(f"  cleaned length: {len(cleaned)}")

            return cleaned

        except Exception as error:

            last_error = error

            if _is_rate_limit(error) and attempt < attempts - 1:

                delay = _retry_after(error) or 3

                print(
                    f"  -> 429 rate limit, waiting {delay}s "
                    f"before retry..."
                )

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

    for model in MODEL_FALLBACKS:

        try:

            print(f"Trying OpenRouter model: {model}")

            answer = _try_model(model, prompt, attempts=2)

            print(f"Success with: {model}")

            return answer

        except Exception as error:

            last_error = error

            print(
                f"  -> Failed: {type(error).__name__}: "
                f"{str(error)[:200]}"
            )

            msg = str(error).lower()

            if "invalid api key" in msg or "401" in msg:
                break

            continue


    print()
    print("========== OPENROUTER FINAL ERROR ==========")
    print(last_error)
    print("============================================")
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
            "The free AI models are temporarily busy. "
            "Please try again in 30–60 seconds."
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