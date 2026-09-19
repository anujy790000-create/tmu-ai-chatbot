import os
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from urllib.parse import urljoin
from datetime import datetime


BASE_URL = "https://www.tmu.ac.in"

START_URLS = [
    "https://www.tmu.ac.in/",
    "https://www.tmu.ac.in/notice-list",
    "https://www.tmu.ac.in/tmu/exam-overview",
    "https://www.tmu.ac.in/tmu/cbcs-circulars",
    "https://www.tmu.ac.in/tmu/scholarship",
    "https://www.tmu.ac.in/tmu/policies-sops",
]


DATA_DIR = "data"
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
OUTPUT_FILE = os.path.join(DATA_DIR, "tmu_data.txt")


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


def clean_text(text):
    """Clean unnecessary whitespace."""

    lines = []

    for line in text.splitlines():

        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines)


def download_pdf(url, filename):
    """Download a PDF from TMU."""

    os.makedirs(
        PDF_DIR,
        exist_ok=True
    )

    filepath = os.path.join(
        PDF_DIR,
        filename
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        with open(
            filepath,
            "wb"
        ) as file:

            file.write(
                response.content
            )

        return filepath

    except requests.RequestException as error:

        print(
            f"PDF download failed: {error}"
        )

        return None


def extract_pdf_text(filepath):
    """Extract text from a PDF."""

    try:

        reader = PdfReader(filepath)

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text)

        return clean_text(
            "\n".join(pages)
        )

    except Exception as error:

        print(
            f"PDF extraction failed: {error}"
        )

        return ""


def scrape_page(url):
    """Scrape webpage text and linked PDFs."""

    print()
    print(f"Scraping: {url}")

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as error:

        print(
            f"Page failed: {error}"
        )

        return [], []

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # Find PDF links before removing elements
    pdf_links = []

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if ".pdf" in href.lower():

            pdf_url = urljoin(
                url,
                href
            )

            if pdf_url not in pdf_links:

                pdf_links.append(
                    pdf_url
                )

    # Remove unnecessary HTML
    for element in soup([
        "script",
        "style",
        "noscript",
        "header",
        "footer",
        "nav"
    ]):

        element.decompose()

    text = soup.get_text(
        separator="\n"
    )

    page_text = clean_text(text)

    return page_text, pdf_links


def safe_filename(url, index):
    """Create a safe PDF filename."""

    name = url.rstrip("/").split("/")[-1]

    if not name.lower().endswith(".pdf"):

        name = f"document_{index}.pdf"

    name = name.replace(
        "?",
        "_"
    )

    name = name.replace(
        "&",
        "_"
    )

    return name


def save_data(documents):
    """Save webpages and PDFs to the knowledge base."""

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "TMU AI ASSISTANT KNOWLEDGE BASE\n"
        )

        file.write(
            "Last updated: "
            + datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            + "\n"
        )

        file.write(
            "=" * 80
            + "\n\n"
        )

        for source, text in documents:

            file.write(
                f"SOURCE: {source}\n"
            )

            file.write(
                "-" * 80
                + "\n"
            )

            file.write(text)

            file.write(
                "\n\n"
            )

            file.write(
                "=" * 80
                + "\n\n"
            )


def main():

    documents = []

    all_pdf_links = []

    # -------------------------
    # Scrape webpages
    # -------------------------

    for url in START_URLS:

        page_text, pdf_links = scrape_page(
            url
        )

        if page_text:

            documents.append(
                (
                    url,
                    page_text
                )
            )

        for pdf_url in pdf_links:

            if pdf_url not in all_pdf_links:

                all_pdf_links.append(
                    pdf_url
                )


    print()
    print(
        f"Found {len(all_pdf_links)} PDF links."
    )


    # -------------------------
    # Download and extract PDFs
    # -------------------------

    for index, pdf_url in enumerate(
        all_pdf_links,
        start=1
    ):

        print()
        print(
            f"Processing PDF {index}/"
            f"{len(all_pdf_links)}"
        )

        print(pdf_url)

        filename = safe_filename(
            pdf_url,
            index
        )

        filepath = download_pdf(
            pdf_url,
            filename
        )

        if not filepath:
            continue

        text = extract_pdf_text(
            filepath
        )

        if text:

            documents.append(
                (
                    pdf_url,
                    text
                )
            )

            print(
                "PDF extracted successfully."
            )

        else:

            print(
                "No text extracted from PDF."
            )


    # -------------------------
    # Save knowledge base
    # -------------------------

    if not documents:

        print()
        print(
            "No information was collected."
        )

        return


    save_data(
        documents
    )


    print()
    print(
        "========================================"
    )

    print(
        "TMU KNOWLEDGE BASE UPDATED"
    )

    print(
        "========================================"
    )

    print(
        f"Documents collected: {len(documents)}"
    )

    print(
        f"PDFs found: {len(all_pdf_links)}"
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()