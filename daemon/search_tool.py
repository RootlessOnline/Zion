"""
search_tool.py — Free web search for Zion Worker agent.

Uses DuckDuckGo HTML endpoint — no API key, no cost, no account.
Results are injected into Worker context before LLM call.

Usage:
    from search_tool import search, needs_search

    if needs_search(task_text):
        results = search(task_text)
        # inject results into Worker context
"""

import re
import logging
import requests
from typing import Optional

log = logging.getLogger("zion.search")

# ── Search trigger detection ───────────────────────────────────────────────────

SEARCH_TRIGGER_WORDS = [
    r"\bfind\b",
    r"\bsearch\b",
    r"\blist\b",
    r"\bresearch\b",
    r"\blook up\b",
    r"\bwhere (can|to)\b",
    r"\bsupplier",
    r"\bwho (makes|sells|offers|provides)\b",
    r"\bwhat (is|are) the (best|cheapest|nearest|closest)\b",
    r"\bhow much (does|is|are)\b",
    r"\bprice of\b",
    r"\bcost of\b",
    r"\bcontact (info|details|information)\b",
    r"\bwebsite\b",
    r"\bURL\b",
    r"\baddress\b",
    r"\blocation of\b",
    r"\bstudio",
    r"\bshop",
    r"\bstore",
    r"\bcompan",
    r"\borganis",
    r"\borganiz",
]

def needs_search(task_text: str) -> bool:
    """Return True if task likely needs real web data."""
    task_lower = task_text.lower()
    for pattern in SEARCH_TRIGGER_WORDS:
        if re.search(pattern, task_lower):
            return True
    return False


# ── DuckDuckGo search ──────────────────────────────────────────────────────────

DDG_URL = "https://html.duckduckgo.com/html/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo and return list of results.
    Each result: {title, url, snippet}
    Returns empty list on failure — never raises.
    """
    try:
        response = requests.post(
            DDG_URL,
            data={"q": query, "b": "", "kl": "nl-nl"},  # Netherlands locale
            headers=HEADERS,
            timeout=10,
            allow_redirects=True
        )
        response.raise_for_status()
        return _parse_ddg_html(response.text, max_results)
    except requests.exceptions.Timeout:
        log.warning(f"Search timeout for query: {query}")
        return []
    except requests.exceptions.ConnectionError:
        log.warning(f"Search connection failed for query: {query}")
        return []
    except Exception as e:
        log.warning(f"Search failed for query '{query}': {e}")
        return []


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML response into structured results."""
    results = []

    # Extract result blocks
    result_blocks = re.findall(
        r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html,
        re.DOTALL
    )

    for block in result_blocks[:max_results * 2]:
        # Extract URL
        url_match = re.search(r'href="(https?://[^"]+)"', block)
        if not url_match:
            continue
        url = url_match.group(1)

        # Skip DuckDuckGo internal links
        if "duckduckgo.com" in url:
            continue

        # Extract title
        title_match = re.search(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
        title = _strip_tags(title_match.group(1)) if title_match else ""

        # Extract snippet
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</[a-z]+>', block, re.DOTALL)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""

        if url and (title or snippet):
            results.append({
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet.strip()
            })

        if len(results) >= max_results:
            break

    log.info(f"Search returned {len(results)} results")
    return results


def _strip_tags(html: str) -> str:
    """Remove HTML tags from string."""
    return re.sub(r"<[^>]+>", "", html).strip()


# ── Context builder ────────────────────────────────────────────────────────────

def build_search_context(task_text: str, max_results: int = 5) -> Optional[str]:
    """
    Run search for task and return formatted context string.
    Returns None if search not needed or failed.
    """
    if not needs_search(task_text):
        return None

    # Build a focused search query from the task
    query = _build_query(task_text)
    log.info(f"Searching for: {query}")

    results = search(query, max_results)

    if not results:
        log.warning("Search returned no results — Worker will proceed without web data")
        return None

    lines = [
        "REAL WEB SEARCH RESULTS (use these — do not invent information):",
        f"Query used: {query}",
        ""
    ]

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        if r['snippet']:
            lines.append(f"   {r['snippet']}")
        lines.append("")

    lines.append("IMPORTANT: Only use URLs from the list above. Do not invent URLs.")
    lines.append("If the results do not contain enough information, say so explicitly.")

    return "\n".join(lines)


def _build_query(task_text: str) -> str:
    """Build a focused search query from a task description."""
    # Remove common filler words to make query more focused
    task_lower = task_text.lower()

    # If task mentions Netherlands/Rotterdam specifically, add to query
    geo = ""
    if "netherlands" in task_lower or "nederland" in task_lower:
        geo = " Netherlands"
    elif "rotterdam" in task_lower:
        geo = " Rotterdam"

    # Trim to reasonable query length
    query = task_text[:120] + geo
    return query


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Test: needs_search ===")
    print(needs_search("find pottery studios in Rotterdam"))        # True
    print(needs_search("list 5 vegetables that grow in spring"))    # True
    print(needs_search("summarise the project goals"))              # False

    print("\n=== Test: search ===")
    results = search("pottery studios Rotterdam Netherlands", max_results=3)
    if results:
        for r in results:
            print(f"  {r['title']}")
            print(f"  {r['url']}")
            print(f"  {r['snippet'][:100]}")
            print()
    else:
        print("  No results (check network connection)")

    print("\n=== Test: build_search_context ===")
    ctx = build_search_context("find 3 pottery studios in Rotterdam with contact info")
    print(ctx or "No context built")
