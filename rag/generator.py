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
# Prefer NON-reasoning models first — they answer directly
# without dumping their internal "thinking" into the reply.
# Reasoning models go last as fallback.

MODEL_FALLBACKS = [
    "google/gemma-4-26b-a4b-it:free",      # non-reasoning, fast
    "google/gemma-4-31b-it:free",          # non-reasoning
    "z-ai/glm-5.2:free",                   # fallback
    "qwen/qwen3.8-27b:free",               # fallback
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


    return f"""You are the TMU AI Student Assistant, a helpful chatbot for
Teerthanker Mahaveer University students.

Answer the student's question using ONLY the official TMU
information provided below.

STRICT OUTPUT RULES:

1. Output ONLY the final answer for the student.
2. NEVER write your reasoning, thinking, or analysis. Do not write
   phrases like "The user is asking...", "I need to find...",
   "Looking at the document...", "Let me check...", "Based on the
   provided...", or any step-by-step thought process.
3. Keep the answer SHORT — 2 to 3 sentences maximum.
4. Do not include an introduction or conclusion. Just answer.
5. If different programs have different rules, give the most common
   rule first (BCA/B.Tech/general), then briefly mention variations
   in one sentence if relevant.
6. Do not invent information. Use only the provided context.
7. If the information is not present, say exactly:
   "I couldn't find this information in the available official TMU sources."
8. Preserve dates, percentages, deadlines and rules exactly.
9. Never claim access to private student information.
10. Do not write "Source:" or list retrieved documents.
11. You MAY mention a URL only if it appears in the context below.
    When the user asks "where can I find X", include the relevant URL.
12. Do not repeat the question.
13. Do not use Markdown symbols such as ** or ##.
14. Answer directly in plain text.

{f"Recent conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}

Student question:
{question}

Official TMU information:
{context}

Final answer (2-3 sentences, no reasoning):
"""


# ==============================
# CLEAN RESPONSE
# ==============================

# Phrases that signal a model is leaking its reasoning.
REASONING_MARKERS = [
    "the user is asking",
    "the user wants",
    "the student is asking",
    "the student wants",
    "i need to find",
    "i need to check",
    "i should check",
    "let me check",
    "let me look",
    "let me think",
    "looking at the",
    "looking through the",
    "based on the provided",
    "based on the context",
    "from the provided",
    "from the context",
    "first, i",
    "first i will",
    "i will check",
    "i will look",
    "to answer this",
    "now, the",
    "now i need",
]


def _clean_answer(answer):
    """
    Strip leaked reasoning and trim to a concise answer.
    """

    if not answer:
        return answer

    answer = answer.strip()

    # 1) Remove common reasoning prefix before the real answer.
    lower = answer.lower()

    for marker in REASONING_MARKERS:

        idx = lower.find(marker)

        if idx == 0:

            # Try to find where the real answer starts:
            # usually after a double newline.
            double_nl = answer.find("\n\n")

            if double_nl > 0:

                answer = answer[double_nl:].strip()
                lower = answer.lower()

            else:

                # Fallback: find the first sentence that looks like
                # a direct statement (starts with a capital, not "I").
                sentences = re.split(r"(?<=[.!?])\s+", answer)

                for i, s in enumerate(sentences):

                    s_clean = s.strip()

                    if (
                        len(s_clean) > 20
                        and not s_clean.lower().startswith(("i ", "the user", "let me"))
                    ):
                        answer = " ".join(sentences[i:]).strip()
                        break

            break

    # 2) Remove any trailing "Let me know if..." / "I hope this helps"
    cut_phrases = [
        "let me know if",
        "i hope this helps",
        "feel free to ask",
        "if you have any",
    ]

    lower = answer.lower()

    for phrase in cut_phrases:

        idx = lower.find(phrase)

        if idx > 0:

            answer = answer[:idx].strip().rstrip(".,;:")

            lower = answer.lower()

    # 3) Cap the answer to ~500 chars if still too long.
    if len(answer) > 600:

        # keep first 2 paragraphs
        parts = re.split(r"\n\s*\n", answer)

        if len(parts) >= 2:
            answer = (parts[0] + "\n\n" + parts[1]).strip()
        else:
            answer = answer[:600].rsplit(" ", 1)[0] + "…"

    return answer.strip()


# ==============================
# ERROR HELPERS
# ==============================

def _is_rate_limit(error):

    s = str(error).lower()

    return "429" in s or ("rate" in s and "limit" in s)


def _retry_after(error):

    """Extract Retry-After seconds from the error if present."""

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

            answer = choice.message.content

            if not answer:
                raise RuntimeError("Empty answer content")

            if choice.finish_reason == "length":
                print("  WARNING: response truncated by max_tokens")

            # Clean reasoning leaks + enforce brevity
            answer = _clean_answer(answer)

            return answer

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
            "The free AI models are temporarily busy right now. "
            "Please try again in about 30 seconds."
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