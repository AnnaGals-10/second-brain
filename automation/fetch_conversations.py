#!/usr/bin/env python3
"""
Fetch conversations from claude.ai using session cookie.
Saves to conversations.json in the format expected by import_conversations.py.

Setup: set CLAUDE_SESSION_KEY in config/.env
  1. Open claude.ai in Chrome
  2. DevTools (F12) > Application > Cookies > https://claude.ai
  3. Copy the value of 'sessionKey'
  4. Paste into config/.env as CLAUDE_SESSION_KEY=<value>
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

COOKIE_STRING = os.getenv("CLAUDE_COOKIE_STRING", "").strip()
CONVERSATIONS_FILE = os.getenv("CONVERSATIONS_FILE", "./conversations.json")
BASE_URL = "https://claude.ai/api"


def get_headers() -> dict:
    return {
        "cookie": COOKIE_STRING,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "referer": "https://claude.ai/",
        "origin": "https://claude.ai",
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "accept-language": "ca,es;q=0.9,en;q=0.8",
        "anthropic-client-version": "0",
        "x-requested-with": "XMLHttpRequest",
    }


def api_get(url: str, **kwargs):
    return requests.get(url, headers=get_headers(), impersonate="chrome124", **kwargs)


def get_organization_id() -> str:
    """Get the first organization UUID from the account."""
    r = api_get(f"{BASE_URL}/bootstrap", timeout=15)
    r.raise_for_status()
    data = r.json()
    memberships = data["account"]["memberships"]
    if not memberships:
        raise RuntimeError("No organizations found.")
    return memberships[0]["organization"]["uuid"]


def fetch_paginated(url: str) -> list[dict]:
    """Fetch all items from a paginated endpoint."""
    items = []
    params: dict = {}
    while True:
        r = api_get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            items.extend(data)
            break
        items.extend(data.get("data", data.get("conversations", [])))
        cursor = data.get("next_cursor") or data.get("cursor")
        if not cursor:
            break
        params["cursor"] = cursor
    return items


def fetch_all_conversations(org_id: str) -> list[dict]:
    """Fetch conversations from root + all projects."""
    all_convs = []

    # Root conversations (not inside any project)
    root = fetch_paginated(f"{BASE_URL}/organizations/{org_id}/chat_conversations")
    all_convs.extend(root)
    print(f"  {len(root)} root conversations")

    # Conversations inside each project
    projects = fetch_paginated(f"{BASE_URL}/organizations/{org_id}/projects")
    for proj in projects:
        pid = proj.get("uuid") or proj.get("id")
        pname = proj.get("name", pid)
        proj_convs = fetch_paginated(
            f"{BASE_URL}/organizations/{org_id}/projects/{pid}/conversations"
        )
        if proj_convs:
            print(f"  {len(proj_convs)} conversations in project '{pname}'")
        all_convs.extend(proj_convs)

    return all_convs


def fetch_conversation_messages(org_id: str, conv_id: str) -> list[dict]:
    """Fetch full messages for a single conversation."""
    url = f"{BASE_URL}/organizations/{org_id}/chat_conversations/{conv_id}"
    r = api_get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("chat_messages", data.get("messages", []))


def normalize_message(msg: dict) -> dict:
    """Normalize message to the format used by import_conversations.py."""
    sender = msg.get("sender") or msg.get("role", "")
    # claude.ai may use 'human'/'assistant' or 'user'/'assistant'
    if sender in ("user", "human"):
        sender = "human"
    else:
        sender = "assistant"

    # Text content may be nested
    text = msg.get("text", "")
    if not text:
        content = msg.get("content", [])
        if isinstance(content, list):
            parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            text = "\n".join(parts)
        elif isinstance(content, str):
            text = content

    return {"sender": sender, "text": text}


def build_conversations_json(raw_convs: list[dict], org_id: str) -> list[dict]:
    """Build the conversations.json format, fetching messages for each."""
    result = []
    total = len(raw_convs)

    for i, conv in enumerate(raw_convs, 1):
        conv_id = conv.get("uuid") or conv.get("id", "")
        name = conv.get("name") or conv.get("title") or "Untitled"
        created_at = conv.get("created_at", "")
        summary = conv.get("summary", "")

        print(f"  [{i}/{total}] {name[:60]}")

        try:
            raw_messages = fetch_conversation_messages(org_id, conv_id)
            messages = [normalize_message(m) for m in raw_messages]
            messages = [m for m in messages if m["text"]]
        except Exception as e:
            print(f"    ⚠ Could not fetch messages: {e}")
            messages = []

        result.append({
            "uuid": conv_id,
            "name": name,
            "created_at": created_at,
            "summary": summary,
            "chat_messages": messages,
        })

    return result


def main():
    if not COOKIE_STRING:
        print("ERROR: CLAUDE_COOKIE_STRING not set in config/.env")
        print()
        print("How to get it:")
        print("  1. Open claude.ai in your browser")
        print("  2. DevTools (F12) > Network > refresh page")
        print("  3. Click any request to claude.ai/api/...")
        print("  4. Request Headers > find 'cookie:' line")
        print("  5. Copy the full value to config/.env as CLAUDE_COOKIE_STRING=<value>")
        sys.exit(1)

    print("Fetching conversations from claude.ai...")

    try:
        org_id = get_organization_id()
        print(f"Organization: {org_id}")
    except Exception as e:
        print(f"ERROR: Could not authenticate ({e.response.status_code})")
        print("Your session key may have expired. Get a new one from DevTools.")
        sys.exit(1)

    raw_convs = fetch_all_conversations(org_id)
    print(f"Found {len(raw_convs)} conversations. Fetching messages...")

    conversations = build_conversations_json(raw_convs, org_id)

    output_path = Path(CONVERSATIONS_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone! Saved {len(conversations)} conversations to {output_path}")
    return len(conversations)


if __name__ == "__main__":
    main()
