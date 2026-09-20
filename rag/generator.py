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
# Order matters. Non-reasoning, instruction-following models first.
# Qwen/DeepSeek moved to the bottom — they tend to echo prompt text.

MODEL_FALLBACKS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "dots-studio/dots-3-note-preview:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "qwen/qwen3.8-27b:free",
    "deepseek/deepseek-v4-flash-0731:free",
    "nex-agi/nex-n2.5-pro:free",
]

MODEL = MODEL_FALLBACKS[0]


# ==============================
# PROMPT BUILDER
# ==============================
# The prompt is written as plain sentences — NOT a numbered list —
# because some models echo numbered lists back as their answer.

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


    return f"""You are a student assistant for Teerthanker Mahaveer University.

Below this message you will find two sections: a student's question, and official TMU text excerpts. Your job is to write the student's answer.

Write 2 short sentences that directly answer the student's question, using ONLY the official TMU text excerpts. Start the first sentence with the actual rule, fact, or answer — never with an introduction. Use plain language. Do not quote the excerpts word-for-word. Do not mention document names, chapter numbers, or section numbers. Do not output your analysis or thinking. If the excerpts mention multiple programs with different rules, give the general rule for BCA and B.Tech students.

If the exact dates are not in the excerpts but the student is asking for dates, tell the student where to check instead of saying "I couldn't find". If nothing at all relevant is in the excerpts, reply exactly: I couldn't find this information in the available official TMU sources.

{f"Recent conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}
--- STUDENT QUESTION ---
{question}

--- OFFICIAL TMU TEXT EXCERPTS ---
{context}

--- YOUR ANSWER (2 sentences, plain text, no reasoning) ---
"""


# ==============================
# CLEAN RESPONSE
# ==============================

REASONING_PREFIXES = (
    # First-person narration
    "the user is asking",
    "the user wants",
    "the student is asking",
    "the student wants",
    "i need to",
    "i should",
    "i will check",
    "i will look",
    "i see",
    "i found",
    "let me",
    # First-person plural (echo of prompt)
    "we need to",
    "we should",
    "we can see",
    "we see",
    "we have",
    # Meta / echoing the prompt
    "to answer",
    "here is what",
    "here's what",
    "based on the provided",
    "based on the context",
    "based on the documents",
    "based on the excerpts",
    "according to the document",
    "according to the excerpts",
    "looking at",
    "looking through",
    "searching",
    "checking",
    "the answer should",
    "the response should",
    "provide short answer",
    "must give",
    "must provide",
    "note that",
    "remember to",
    "keep in mind",
    "as per the instructions",
    "following the instructions",
    "the rules say",
    "the instructions say",
)


def _is_reasoning_sentence(s):
    """True if a sentence looks like reasoning or prompt echo."""

    s_lower = s.lower().strip()

    # Direct prefix match
    if any(s_lower.startswith(p) for p in REASONING_PREFIXES):
        return True

    # Contains suspicious meta phrases
    meta_phrases = (
        "using only official tmu",
        "using only the provided",
        "using only the excerpts",
        "provide short answer",
        "max 2 sentences",
        "no preamble",
        "no quoting",
        "general rule first",
        "must give general rule",
        "answer the question",
        "answer the student",
        "the question asks",
    )

    if any(mp in s_lower for mp in meta_phrases):
        return True

    return False


def _clean_answer(answer):

    if not answer:
        return answer

    answer = answer.strip()

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return answer

    # Drop leading reasoning / echo sentences
    while sentences:
        if _is_reasoning_sentence(sentences[0]):
            sentences.pop(0)
        else:
            break

    # If everything got stripped, look for any middle sentence that
    # looks like a real answer
    if not sentences:

        all_s = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", answer)
            if s.strip()
        ]

        good = [s for s in all_s if not _is_reasoning_sentence(s)]

        if good:
            sentences = good
        else:
            # Truly nothing usable — return honest failure
            return (
                "I couldn't generate a clean answer. "
                "Please try rephrasing your question."
            )

    # Keep at most 3 sentences
    sentences = sentences[:3]

    cleaned = " ".join(sentences)

    # Trim trailing soft phrases
    cut_phrases = (
        "let me know if",
        "i hope this helps",
        "feel free to ask",
        "if you have any",
        "note:",
    )

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

            # If the model echoed the prompt, reject and try next
            if cleaned.lower().startswith(("we need", "we should", "we have")):
                raise RuntimeError("Prompt echo detected")

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