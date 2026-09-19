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
# Curated list of free, NON-reasoning models that produce complete
# answers. Reasoning models consume max_tokens on hidden thinking
# and produce truncated visible answers, so we avoid them.
#
# Order matters: first working model wins.
# GLM is first because it has been the most reliable on the free tier.
# Gemma models go last because Google's shared pool is often congested.

MODEL_FALLBACKS = [
    "z-ai/glm-5.2:free",                        # most reliable currently
    "nvidia/nemotron-3-ultra-550b-a55b:free",   # large, different provider
    "qwen/qwen3.8-27b:free",                    # instruction following
    "google/gemma-4-26b-a4b-it:free",           # often rate-limited
    "google/gemma-4-31b-it:free",               # often rate-limited
]

# Kept for backwards compatibility with any code importing MODEL
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

Answer the student's question using ONLY the official
TMU information provided below.

Rules:
- Do not invent information.
- Do not use outside knowledge.
- If the information is not present, say:
  "I couldn't find this information in the available official TMU sources."
- Keep the answer concise.
- Use simple student-friendly language.
- Preserve dates, percentages, deadlines and rules exactly.
- Never claim access to private student information.
- Do not guess current information.
- Do not include URLs.
- Do not write "Source:".
- Do not mention the retrieved documents.
- Do not repeat the question.
- Do not use Markdown symbols such as ** or ##.
- Answer directly.

{f"Recent conversation:{chr(10)}{history_text}{chr(10)}" if history_text else ""}

Student question:
{question}

Official TMU information:
{context}

Provide ONLY the final answer.
"""


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
                max_tokens=600
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

            return answer.strip()

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

            # Auth issues affect every model — stop immediately
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