import os
import time
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from urllib.parse import urljoin
from datetime import datetime


# ==============================
# WHITELIST WITH PER-PAGE PDF CAPS
# ==============================
# (url, max_pdfs_to_keep)
#
# Order matters — put the most valuable pages first.
# 0 = don't scrape PDFs from this page (just the page text).

PAGES = [
    # === HIGHEST VALUE — templates & project docs ===
    ("https://www.tmu.ac.in/college-of-computing-sciences-and-it/project-templates", 30),
    ("https://www.tmu.ac.in/college-of-computing-sciences-and-it", 10),

    # === Examination rules & ordinances ===
    ("https://www.tmu.ac.in/tmu/exam-overview", 8),
    ("https://www.tmu.ac.in/tmu/exam-ordinance", 10),

    # === Scholarships ===
    ("https://www.tmu.ac.in/tmu/scholarship", 8),

    # === Policies, SOPs ===
    ("https://www.tmu.ac.in/tmu/policies-sops", 12),

    # === College pages (sample syllabi / handbooks) ===
    ("https://www.tmu.ac.in/college-of-engineering", 6),
    ("https://www.tmu.ac.in/college-of-management", 6),
    ("https://www.tmu.ac.in/college-of-pharmacy", 6),

    # === Homepage (page text only) ===
    ("https://www.tmu.ac.in/", 0),

    # === SKIP PDFs from these (page text only) ===
    ("https://www.tmu.ac.in/notice-list", 0),
    ("https://www.tmu.ac.in/tmu/cbcs-circulars", 5),
]


# ==============================
# HARD PDF KEYWORD FILTER
# ==============================
# Only filenames matching at least one of these are kept.
# NOTHING else (no "circular", no "notice", no "result").

KEEP_KEYWORDS = [
    "template", "synopsis", "proforma", "specimen",
    "format", "affidavit", "undertaking",

    "syllabus", "curriculum",
    "scheme_of_study", "scheme-of-study",

    "ordinance", "academic_ordinance", "academic-ordinance",
    "examination_ordinance", "examination-ordinance",

    "sop", "policy", "policies", "guideline",
    "handbook", "manual",

    "anti-ragging", "anti_ragging",
    "grievance", "code_of_conduct", "code-of-conduct",

    "academic_calendar", "academic-calendar",
    "prospectus",

    "internship", "project_report", "project-report",
    "project_guidelines", "minor_project", "major_project",

    "scholarship_rules", "scholarship_guidelines",
]

SKIP_KEYWORDS = [
    "result", "merit", "rank", "selection",
    "waiting", "counseling", "counselling",
    "roll", "student_list", "student-list",
    "admission_list", "admission-list",
    "fee_receipt", "answer_key", "answer-key",
]


DATA_DIR = "data"
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
OUTPUT_FILE = os.path.join(DATA_DIR, "tmu_data.txt")

REQUEST_TIMEOUT = 30
DELAY = 0.4
MAX_PDF_SIZE_MB = 10
GLOBAL_PDF_CAP = 60


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


def safe_filename(url, i):
    name = url.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name = f"document_{i}.pdf"
    return name.replace("?", "_").replace("&", "_")


def download_pdf(url, filename):
    os.makedirs(PDF_DIR, exist_ok=True)
    filepath = os.path.join(PDF_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath

    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        r.raise_for_status()

        cl = r.headers.get("content-length")
        if cl and int(cl) / (1024 * 1024) > MAX_PDF_SIZE_MB:
            return None

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return filepath
    except requests.RequestException as e:
        print(f"    download failed: {e}")
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
        print(f"    extract failed: {e}")
        return ""


def scrape_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"    page failed: {e}")
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
    seen_filenames = set()
    total_pdfs = 0

    print("Fetching whitelisted pages (curated)...\n")

    for url, max_pdfs in PAGES:

        print(f"→ {url}  (max PDFs: {max_pdfs})")

        text, pdfs = scrape_page(url)

        if text:
            documents.append((url, text))

        if max_pdfs == 0:
            print(f"    page OK, skipping PDFs")
            continue

        kept_here = 0
        for pdf in pdfs:
            if kept_here >= max_pdfs:
                break
            if total_pdfs >= GLOBAL_PDF_CAP:
                break
            if not should_keep_pdf(pdf):
                continue

            fname = safe_filename(pdf, 0)
            if fname in seen_filenames:
                continue

            seen_filenames.add(fname)
            kept_here += 1
            total_pdfs += 1

            print(f"    [{total_pdfs}] {fname}")
            path = download_pdf(pdf, fname)
            if not path:
                continue

            pdf_text = extract_pdf_text(path)
            if pdf_text:
                documents.append((pdf, pdf_text))
            else:
                print(f"      (no text — skipped)")

        time.sleep(DELAY)

    if not documents:
        print("\nNothing collected.")
        return

    save_data(documents)

    print("\n" + "=" * 40)
    print("TMU KNOWLEDGE BASE UPDATED")
    print("=" * 40)
    print(f"Documents: {len(documents)}")
    print(f"PDFs kept: {total_pdfs}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()