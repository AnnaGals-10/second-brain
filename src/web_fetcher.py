"""
Fetches web content and saves it as .md notes in the vault.
Supports: single URL, batch URLs, RSS feeds.
"""
import re
import os
import json
from pathlib import Path
from datetime import datetime
from openai import OpenAI
import trafilatura
import feedparser

client = OpenAI()

# RSS feeds file in data/ directory
DATA_PATH = Path(__file__).parent.parent / "data"
FEEDS_FILE = DATA_PATH / "rss_feeds.json"


# ── Core fetch ────────────────────────────────────────────────────────────────

def fetch_url(url: str) -> dict:
    """Fetch and extract content from a URL. Returns {title, text, url, date}."""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch: {url}")

    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    meta = trafilatura.extract_metadata(downloaded)

    if not text:
        raise ValueError(f"No extractable content at: {url}")

    title = (meta.title if meta and meta.title else url.split("/")[-1] or "Untitled")
    date  = (meta.date  if meta and meta.date  else datetime.now().strftime("%Y-%m-%d"))

    return {"title": title, "text": text, "url": url, "date": date}


def summarize_and_link(title: str, text: str, existing_notes: list) -> dict:
    """Use LLM to summarize content and suggest [[links]] to existing notes."""
    notes_str = ", ".join(existing_notes[:60])
    prompt = (
        f"You are building a knowledge base. Given this article:\n\n"
        f"Title: {title}\n\n"
        f"Content (truncated):\n{text[:3000]}\n\n"
        f"Existing notes in the knowledge base: {notes_str}\n\n"
        "Produce a concise Obsidian-style note:\n"
        "1. Keep only the most relevant insights (3-6 bullet points or short paragraphs)\n"
        "2. Use [[note name]] syntax to link to relevant existing notes\n"
        "3. Be knowledge-dense, no fluff\n\n"
        "Return ONLY the note content (no title, no metadata)."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    summary = response.choices[0].message.content.strip()

    # Extract suggested [[links]]
    links = re.findall(r'\[\[([^\]]+)\]\]', summary)
    return {"summary": summary, "links": links}


def save_as_note(vault_path: str, data: dict, summary: str) -> str:
    """Save fetched content as a .md note. Returns the file path."""
    vault  = Path(vault_path)
    web_dir = vault / "web"
    web_dir.mkdir(parents=True, exist_ok=True)

    safe_title = re.sub(r'[<>:"/\\|?*]', '', data["title"])[:70].strip()
    filename   = f"{data['date']} {safe_title}.md"
    path       = web_dir / filename

    content = (
        f"# {data['title']}\n\n"
        f"> Source: {data['url']}\n"
        f"> Fetched: {data['date']}\n\n"
        f"{summary}\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── Public API ────────────────────────────────────────────────────────────────

def import_url(url: str, vault_path: str, existing_notes: list) -> dict:
    """Full pipeline: fetch → summarize → save → return result."""
    data   = fetch_url(url)
    result = summarize_and_link(data["title"], data["text"], existing_notes)
    path   = save_as_note(vault_path, data, result["summary"])
    return {
        "title":    data["title"],
        "date":     data["date"],
        "path":     path,
        "links":    result["links"],
        "summary":  result["summary"],
    }


def import_batch(urls: list, vault_path: str, existing_notes: list,
                 progress_callback=None) -> list:
    results = []
    for i, url in enumerate(urls):
        if progress_callback:
            progress_callback(i, len(urls), url)
        try:
            r = import_url(url.strip(), vault_path, existing_notes)
            results.append({"url": url, "status": "ok", **r})
        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})
    return results


# ── RSS feeds ─────────────────────────────────────────────────────────────────

def load_feeds() -> list:
    FEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if FEEDS_FILE.exists():
        with open(FEEDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_feeds(feeds: list):
    FEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDS_FILE, "w", encoding="utf-8") as f:
        json.dump(feeds, f, ensure_ascii=False, indent=2)


def fetch_rss(feed_url: str, max_items: int = 5) -> list:
    """Returns list of {title, url, date} from an RSS feed."""
    parsed = feedparser.parse(feed_url)
    items  = []
    for entry in parsed.entries[:max_items]:
        date = entry.get("published", datetime.now().strftime("%Y-%m-%d"))[:10]
        items.append({
            "title": entry.get("title", "Untitled"),
            "url":   entry.get("link", ""),
            "date":  date,
        })
    return items


def sync_rss_feed(feed_url: str, vault_path: str, existing_notes: list,
                  max_items: int = 5) -> list:
    """Fetch latest articles from an RSS feed and import new ones."""
    items   = fetch_rss(feed_url, max_items)
    results = []
    for item in items:
        if item["url"]:
            try:
                r = import_url(item["url"], vault_path, existing_notes)
                results.append({"status": "ok", **r})
            except Exception as e:
                results.append({"url": item["url"], "status": "error", "error": str(e)})
    return results
