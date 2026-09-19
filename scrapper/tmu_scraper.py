import os
import time
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from urllib.parse import urljoin
from datetime import datetime


# ==============================
# CURATED WHITELIST
# ==============================
# Every page that matters to students. Add more if needed.
# No crawling — just fetch each URL + its PDFs.

PAGES = [
    # Root
    "https://www.tmu.ac.in/",

    # Exams
    "https://www.tmu.ac.in/tmu/exam-overview",
    "https://www.tmu.ac.in/tmu/exam-ordinance",
    "https://www.tmu.ac.in/tmu/cbcs-circulars",

    # Notices & circulars
    "https://www.tmu.ac.in/notice-list",

    # Scholarships
    "https://www.tmu.ac.in/tmu/scholarship",

    # Policies
    "https://www.tmu.ac.in/tmu/policies-sops",

    # CCSIT college
    "https://www.tmu.ac.in/college-of-computing-sciences-and-it",
    "https://www.tmu.ac.in/college-of-computing-sciences-and-it/project-templates",

    # Other colleges (add more if you want them)
    "https://www.tmu.ac.in/college-of-engineering",
    "https://www.tmu.ac.in/college-of-management",
    "https://www.tmu.ac.in/college-of-pharmacy",
]


# ==============================
# PDF FILTER (keep only useful reference docs)
# ==============================

KEEP_KEYWORDS = [
    "template", "synopsis", "format", "specimen",
    "proforma", "form", "affidavit", "undertaking",

    "syllabus", "curriculum", "scheme", "grading",
    "cbcs", "nep", "credit",

    "ordinance", "policy", "policies", "sop",
    "regulation", "handbook", "manual", "guideline",
    "rules", "code_of_conduct", "code-of-conduct",
    "anti-ragging", "anti_ragging", "grievance",

    "examination_rules", "exam_rules",
    "evaluation", "re-evaluation", "reappear_rules",

    "academic_calendar", "academic-calendar",
    "prospectus", "brochure", "scheme_of_study",

    "internship", "project_report", "project-report",
    "project_guidelines", "minor_project", "major_project",

    "scholarship_rules", "scholarship_guidelines",
    "scholarship_policy",
]

SKIP_KEYWORDS = [
    "result", "merit", "rank", "selection", "waiting",
    "counseling", "counselling", "roll", "uid_", "uid-",
    "student_list", "student-list", "admission_list",
    "admission-list", "fee_receipt", "fee-receipt",
    "answer_key", "answer-key",
    "phd_entrance", "phd-entrance",
]


DATA_DIR = "data"
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
OUTPUT_FILE = os.path.join(DATA_DIR, "tmu_data.txt")

MAX_PDF_SIZE_MB = 10
REQUEST_TIMEOUT = 30
DELAY = 0.4


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}


# ==============================
# HELPERS
# ==============================

def clean_text(text):
    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines)


def should_keep_pdf(url):
    u = url.lower()
    if any(kw in u for kw in SKIP_KEYWORDS):
        return False
    return any(kw in u for kw in KEEP_KEYWORDS)


def download_pdf(url, filename):
    os.makedirs(PDF_DIR, exist_ok=True)
    filepath = os.path.join(PDF_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath

    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        r.raise_for_status()

        cl = r.headers.get("content-length")
        if cl:
            mb = int(cl) / (1024 * 1024)
            if mb > MAX_PDF_SIZE_MB:
                print(f"  Skip ({mb:.1f} MB)")
                return None

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        return filepath

    except requests.RequestException as e:
        print(f"  Download failed: {e}")
        return None


def extract_pdf_text(path):
    try:
        reader = PdfReader(path)
        pages = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                pages.append(t)
        return clean_text("\n".join(pages))
    except Exception as e:
        print(f"  Extract failed: {e}")
        return ""


def safe_filename(url, i):
    name = url.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name = f"document_{i}.pdf"
    return name.replace("?", "_").replace("&", "_")


def scrape_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed: {e}")
        return "", []

    soup = BeautifulSoup(r.text, "html.parser")

    pdf_links = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(url, href).split("#")[0]
        if full.lower().endswith(".pdf") and full not in pdf_links:
            pdf_links.append(full)

    for el in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        el.decompose()

    return clean_text(soup.get_text(separator="\n")), pdf_links


def save_data(documents):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("TMU AI ASSISTANT KNOWLEDGE BASE\n")
        f.write("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write("=" * 80 + "\n\n")
        for source, text in documents:
            f.write(f"SOURCE: {source}\n")
            f.write("-" * 80 + "\n")
            f.write(text)
            f.write("\n\n")
            f.write("=" * 80 + "\n\n")


# ==============================
# MAIN
# ==============================

def main():
    documents = []
    all_pdfs = []
    seen_names = set()

    print("Fetching whitelisted pages...\n")

    for url in PAGES:
        print(f"→ {url}")
        text, pdfs = scrape_page(url)

        if text:
            documents.append((url, text))

        for pdf in pdfs:
            if not should_keep_pdf(pdf):
                continue
            fname = safe_filename(pdf, 0)
            if fname in seen_names:
                continue
            seen_names.add(fname)
            all_pdfs.append(pdf)

        time.sleep(DELAY)

    print(f"\nFound {len(all_pdfs)} relevant PDFs")

    for i, url in enumerate(all_pdfs, 1):
        print(f"\n[{i}/{len(all_pdfs)}] {url}")
        path = download_pdf(url, safe_filename(url, i))
        if not path:
            continue
        text = extract_pdf_text(path)
        if text:
            documents.append((url, text))
            print("  OK")
        else:
            print("  No text")

    if not documents:
        print("Nothing collected.")
        return

    save_data(documents)

    print("\n" + "=" * 40)
    print("TMU KNOWLEDGE BASE UPDATED")
    print("=" * 40)
    print(f"Documents: {len(documents)}")
    print(f"PDFs: {len(all_pdfs)}")


if __name__ == "__main__":
    main()