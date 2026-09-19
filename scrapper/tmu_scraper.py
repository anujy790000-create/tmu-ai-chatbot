import os
import time
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from urllib.parse import urljoin, urlparse
from datetime import datetime
from collections import deque


BASE_URL = "https://www.tmu.ac.in"
BASE_HOST = urlparse(BASE_URL).netloc


START_URLS = [
    "https://www.tmu.ac.in/",
    "https://www.tmu.ac.in/notice-list",
    "https://www.tmu.ac.in/tmu/exam-overview",
    "https://www.tmu.ac.in/tmu/cbcs-circulars",
    "https://www.tmu.ac.in/tmu/scholarship",
    "https://www.tmu.ac.in/tmu/policies-sops",
    "https://www.tmu.ac.in/college-of-computing-sciences-and-it",
]


# ==============================
# CRAWLER CONFIG
# ==============================

MAX_DEPTH = 2
MAX_PAGES = 120          # cap total pages, avoid crawling the whole site
MAX_PDFS = 200           # HARD LIMIT on PDFs
REQUEST_TIMEOUT = 30
DELAY = 0.4


# ==============================
# PDF FILTERING — the important part
# ==============================
# A PDF is only kept if its URL matches one of these keywords.

KEEP_KEYWORDS = [
    # documents
    "template", "form", "format", "syllabus", "curriculum",
    "ordinance", "policy", "sop", "handbook", "scheme",
    "prospectus", "brochure", "guideline", "regulation",
    "synopsis", "internship", "project", "report",
    "anti-ragging", "grievance", "code-of-conduct",
    "code_of_conduct", "rules", "manual",
    # examinations
    "examination", "exam", "grading", "attendance",
    "datesheet", "date-sheet", "admit", "re-evaluation",
    "reappear",
    # academic
    "academic", "calendar", "fee", "scholarship",
    "cbcs", "nep", "credit",
    # notices / circulars (general ones, still useful)
    "circular", "notice", "announcement",
]

# URLs containing any of these are skipped (result sheets etc).
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


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 "
        "Safari/537.36"
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


def is_internal_link(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc not in (BASE_HOST, "tmu.ac.in", "www.tmu.ac.in"):
            return False

        skip_ext = (
            ".pdf", ".jpg", ".jpeg", ".png", ".gif",
            ".svg", ".zip", ".doc", ".docx", ".xls",
            ".xlsx", ".ppt", ".pptx", ".mp4", ".mp3",
        )
        if any(parsed.path.lower().endswith(ext) for ext in skip_ext):
            return False

        skip_kw = ("/login", "/admin", "/api/", "/search")
        if any(kw in url.lower() for kw in skip_kw):
            return False

        return True
    except Exception:
        return False


def normalize(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def should_keep_pdf(url):
    """Decide if a PDF is likely to contain useful content."""
    u = url.lower()

    # Skip if matches a skip keyword
    if any(kw in u for kw in SKIP_KEYWORDS):
        return False

    # Keep if matches a keep keyword
    if any(kw in u for kw in KEEP_KEYWORDS):
        return True

    # Default: reject (keeps the base clean)
    return False


# ==============================
# PDF HANDLING
# ==============================

def download_pdf(url, filename):
    os.makedirs(PDF_DIR, exist_ok=True)
    filepath = os.path.join(PDF_DIR, filename)

    # Skip if already downloaded
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 1000:  # non-empty
            print(f"  Cached: {filename}")
            return filepath

    try:
        response = requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True
        )
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > MAX_PDF_SIZE_MB:
                print(f"  Skipping ({size_mb:.1f} MB, too large)")
                return None

        with open(filepath, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        return filepath

    except requests.RequestException as error:
        print(f"  Download failed: {error}")
        return None


def extract_pdf_text(filepath):
    try:
        reader = PdfReader(filepath)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return clean_text("\n".join(pages))
    except Exception as error:
        print(f"  Extraction failed: {error}")
        return ""


def safe_filename(url, index):
    name = url.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name = f"document_{index}.pdf"
    return name.replace("?", "_").replace("&", "_")


# ==============================
# PAGE SCRAPING
# ==============================

def scrape_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"  Failed: {error}")
        return "", [], []

    soup = BeautifulSoup(response.text, "html.parser")

    pdf_links = []
    internal_links = []

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        full = urljoin(url, href).split("#")[0]

        if full.lower().endswith(".pdf"):
            if full not in pdf_links:
                pdf_links.append(full)
        elif is_internal_link(full):
            if full not in internal_links:
                internal_links.append(full)

    for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        element.decompose()

    page_text = clean_text(soup.get_text(separator="\n"))

    return page_text, pdf_links, internal_links


# ==============================
# SAVE
# ==============================

def save_data(documents):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("TMU AI ASSISTANT KNOWLEDGE BASE\n")
        file.write(
            "Last updated: "
            + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + "\n"
        )
        file.write("=" * 80 + "\n\n")

        for source, text in documents:
            file.write(f"SOURCE: {source}\n")
            file.write("-" * 80 + "\n")
            file.write(text)
            file.write("\n\n")
            file.write("=" * 80 + "\n\n")


# ==============================
# MAIN CRAWLER
# ==============================

def crawl():
    documents = []
    visited = set()
    all_pdf_links = []
    seen_pdf_names = set()

    queue = deque()
    for seed in START_URLS:
        queue.append((normalize(seed), 0))

    while queue and len(visited) < MAX_PAGES:
        url, depth = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        print(f"\n[depth {depth}] {url}")

        page_text, pdf_links, internal_links = scrape_page(url)

        if page_text:
            documents.append((url, page_text))

        # --- collect PDFs, filtered ---
        for pdf in pdf_links:
            if pdf in all_pdf_links:
                continue

            if not should_keep_pdf(pdf):
                continue

            # dedupe by filename
            fname = safe_filename(pdf, 0)
            if fname in seen_pdf_names:
                continue

            seen_pdf_names.add(fname)
            all_pdf_links.append(pdf)

            if len(all_pdf_links) >= MAX_PDFS:
                print(f"\nReached MAX_PDFS limit ({MAX_PDFS}). Stopping collection.")
                break

        if len(all_pdf_links) >= MAX_PDFS:
            break

        if depth < MAX_DEPTH:
            for link in internal_links:
                link = normalize(link)
                if link not in visited:
                    queue.append((link, depth + 1))

        time.sleep(DELAY)

    print()
    print("=" * 40)
    print(f"Crawled {len(visited)} pages")
    print(f"Kept {len(all_pdf_links)} useful PDFs (of all PDFs found)")
    print("=" * 40)

    # --- Download & extract PDFs ---
    for index, pdf_url in enumerate(all_pdf_links, start=1):
        print(f"\n[{index}/{len(all_pdf_links)}] {pdf_url}")

        filename = safe_filename(pdf_url, index)
        filepath = download_pdf(pdf_url, filename)

        if not filepath:
            continue

        text = extract_pdf_text(filepath)

        if text:
            documents.append((pdf_url, text))
            print("  OK")
        else:
            print("  No text (scanned?)")

    if not documents:
        print("No information collected.")
        return

    save_data(documents)

    print()
    print("=" * 40)
    print("TMU KNOWLEDGE BASE UPDATED")
    print("=" * 40)
    print(f"Documents: {len(documents)}")
    print(f"PDFs: {len(all_pdf_links)}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    crawl()