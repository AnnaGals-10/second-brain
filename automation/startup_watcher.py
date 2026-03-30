#!/usr/bin/env python3
"""
Start the file watcher daemon for second-brain.

This daemon monitors conversations.json for changes and auto-imports new conversations.
It uses watchdog to detect file modifications and triggers import_conversations.py.

Usage:
  python startup_watcher.py [conversations_path]
  
For Windows, run in the background:
  Start-Process python -ArgumentList "automation/startup_watcher.py" -WindowStyle Hidden
  
For Linux/Mac, run in the background:
  python automation/startup_watcher.py &
"""
import sys
import os
from pathlib import Path

# Ensure paths are set correctly
AUTOMATION_DIR = Path(__file__).parent
PROJECT_ROOT = AUTOMATION_DIR.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(AUTOMATION_DIR))

from watcher import main as watcher_main

if __name__ == "__main__":
    try:
        watcher_main()
    except KeyboardInterrupt:
        print("\n[startup] Watcher stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"[startup] Error: {e}", file=sys.stderr)
        sys.exit(1)
