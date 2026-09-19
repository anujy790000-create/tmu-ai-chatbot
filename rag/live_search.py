import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}


def _is_tmu(url):
    try:
        host = urlparse(url).netloc.lower()
        return "tmu.ac.in" in host
    except Exception:
        return False


def search_tmu(query, max_results=5):
    """
    Search DuckDuckGo for site:tmu.ac.in <query>.
    Returns list of {'title': str, 'url': str}.
    """
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": f"site:tmu.ac.in {query}"},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    for link in soup.select("a.result__a"):
        href = link.get("href", "")
        title = link.get_text(strip=True)

        # DDG wraps links: /l/?uddg=<encoded_url>
        if href.startswith("/l/"):
            qs = parse_qs(urlparse(href).query)
            href = unquote(qs.get("uddg", [""])[0])

        if not href or not _is_tmu(href):
            continue

        if any(r["url"] == href for r in results):
            continue

        results.append({"title": title, "url": href})

        if len(results) >= max_results:
            break

    return results


def fetch_page_text(url, max_chars=3500):
    """Fetch a TMU page and return its cleaned text."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(r.text, "html.parser")

    for el in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        el.decompose()

    text = soup.get_text(separator="\n")

    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)

    return "\n".join(lines)[:max_chars]