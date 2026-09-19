import os
import re


DATA_FILE = "data/tmu_data.txt"


STOP_WORDS = {
    "what", "when", "where", "which", "who", "how",
    "can", "does", "the", "is", "are", "was", "were",
    "for", "from", "about", "tell", "me", "please",
    "show", "give", "and", "or", "to", "of", "in",
    "on", "my", "i", "a", "an", "do", "you", "need",
    "should", "would", "could"
}


TOPIC_KEYWORDS = {

    "attendance": [
        "attendance", "absent", "absence", "75%",
        "class attendance", "attendance requirement",
        "minimum attendance"
    ],

    "exam": [
        "exam", "examination", "examinations",
        "date sheet", "admit card", "hall ticket",
        "reappear", "re-evaluation", "result"
    ],

    "scholarship": [
        "scholarship", "scholarships", "concession",
        "fee waiver", "financial assistance"
    ],

    "notice": [
        "notice", "notices", "notification",
        "circular", "announcement", "latest notice",
        "latest update"
    ],

    "academic_calendar": [
        "academic calendar", "calendar",
        "semester dates", "academic session",
        "session dates"
    ],

    "admission": [
        "admission", "apply", "application",
        "eligibility", "admission rules"
    ],

    "fees": [
        "fee", "fees", "payment", "tuition",
        "fee statement", "fee due"
    ],

    "timetable": [
        "timetable", "time table", "class timing",
        "class timings", "schedule"
    ],

    "erp": [
        "erp", "student portal", "student login",
        "uid", "id card"
    ]
}


SOURCE_PRIORITY = {

    "attendance": [
        "exam-overview", "policies-sops", "circular"
    ],

    "exam": [
        "exam-overview", "exam-ordinance", "circular"
    ],

    "scholarship": [
        "scholarship", "policies-sops"
    ],

    "notice": [
        "notice-list", "circular"
    ],

    "academic_calendar": [
        "cbcs-circulars", "calendar", "circular"
    ],

    "admission": [
        "admission", "programme"
    ],

    "fees": [
        "fees", "programme", "admission"
    ],

    "timetable": [
        "timetable", "schedule"
    ],

    "erp": [
        "erp", "policies-sops"
    ]
}


def load_knowledge_base():

    if not os.path.exists(DATA_FILE):
        return ""

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return file.read()


def split_into_sections(text):

    sections = re.split(r"={80,}", text)

    return [
        section.strip()
        for section in sections
        if section.strip()
    ]


def chunk_section(section, max_chars=600, overlap=100):

    source_match = re.search(
        r"SOURCE:\s*(.+)",
        section
    )

    source = source_match.group(1).strip() if source_match else ""

    body = re.sub(
        r"SOURCE:\s*.+\n?-{80,}\n?",
        "",
        section,
        count=1
    ).strip()

    if not body:
        return []

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", body)
        if p.strip()
    ]

    chunks = []
    current = ""

    for para in paragraphs:

        if len(current) + len(para) + 1 <= max_chars:

            current = (
                current + "\n\n" + para
                if current else para
            )

        else:

            if current:
                chunks.append(
                    f"SOURCE: {source}\n{'-'*40}\n{current}"
                )

            overlap_text = (
                current[-overlap:]
                if len(current) > overlap
                else current
            )

            current = (
                overlap_text + "\n\n" + para
                if overlap_text else para
            )

    if current:
        chunks.append(
            f"SOURCE: {source}\n{'-'*40}\n{current}"
        )

    return chunks


def get_words(query):

    words = re.findall(
        r"\b[a-zA-Z0-9%\-]+\b",
        query.lower()
    )

    return {
        word
        for word in words
        if (
            word not in STOP_WORDS
            and len(word) >= 3
        )
    }


def detect_topics(query):

    query_lower = query.lower()

    detected = []

    for topic, keywords in TOPIC_KEYWORDS.items():

        for keyword in keywords:

            if keyword in query_lower:

                detected.append(topic)
                break

    return detected


def get_source(section):

    if "SOURCE:" not in section:
        return ""

    return (
        section
        .split("SOURCE:", 1)[1]
        .split("\n", 1)[0]
        .strip()
    )


def score_chunk(chunk, query):

    chunk_lower = chunk.lower()

    query_words = get_words(query)

    topics = detect_topics(query)

    score = 0

    for word in query_words:

        count = chunk_lower.count(word)

        if count > 0:
            score += min(count, 3) * 2

    for topic in topics:

        for keyword in TOPIC_KEYWORDS[topic]:

            if keyword in chunk_lower:
                score += 4

    source = get_source(chunk).lower()

    for topic in topics:

        for priority in SOURCE_PRIORITY.get(topic, []):

            if priority in source:
                score += 15

    query_lower = query.lower()

    for topic in topics:

        for keyword in TOPIC_KEYWORDS[topic]:

            if keyword in query_lower and keyword in chunk_lower:
                score += 6

    return score


def search_knowledge_base(query, max_results=3):

    text = load_knowledge_base()

    if not text:
        return []

    sections = split_into_sections(text)

    all_chunks = []

    for section in sections:

        chunks = chunk_section(section)

        all_chunks.extend(chunks)

    scored = []

    for chunk in all_chunks:

        score = score_chunk(chunk, query)

        if score > 0:

            scored.append((score, chunk))

    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )

    seen = set()
    results = []

    for score, chunk in scored:

        key = (
            get_source(chunk),
            chunk[:80]
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(chunk)

        if len(results) >= max_results:
            break

    return results


def extract_source(section):

    return get_source(section)


if __name__ == "__main__":

    while True:

        query = input(
            "\nAsk a TMU question "
            "(type 'exit' to quit): "
        ).strip()

        if query.lower() == "exit":
            break

        if not query:
            continue

        results = search_knowledge_base(query)

        if not results:

            print("\nNo relevant information found.")
            continue

        print(f"\nFound {len(results)} relevant chunks:")

        for index, result in enumerate(results, start=1):

            source = extract_source(result)

            print(f"\n--- Result {index} ---")
            print(f"Source: {source}")
            print(result[:1500])