"""
Watches conversations.json for changes and auto-imports new conversations.
Run in background: python watcher.py [path/to/conversations.json]
"""
import sys
import time
import subprocess
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SCRIPT_DIR = Path(__file__).parent
IMPORT_SCRIPT = SCRIPT_DIR / "import_conversations.py"


class ConversationsHandler(FileSystemEventHandler):
    def __init__(self, conversations_file: str):
        self.conversations_file = Path(conversations_file).resolve()
        self._last_run = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).resolve() != self.conversations_file:
            return
        # Debounce: ignore repeated events within 5 seconds
        now = time.time()
        if now - self._last_run < 5:
            return
        self._last_run = now
        self._run_import()

    def _run_import(self):
        print(f"[watcher] conversations.json changed — importing...")
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, str(IMPORT_SCRIPT), str(self.conversations_file)],
            cwd=str(SCRIPT_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode != 0:
            print(f"[watcher] ERROR: {result.stderr}", file=sys.stderr)
        else:
            print("[watcher] Import complete.")


def main():
    conversations_file = sys.argv[1] if len(sys.argv) > 1 else "conversations.json"
    conversations_path = Path(conversations_file).resolve()

    if not conversations_path.exists():
        print(f"[watcher] Waiting for {conversations_path} to appear...")

    print(f"[watcher] Watching {conversations_path}")
    print("[watcher] Press Ctrl+C to stop.\n")

    handler = ConversationsHandler(str(conversations_path))
    observer = Observer()
    observer.schedule(handler, str(conversations_path.parent), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
