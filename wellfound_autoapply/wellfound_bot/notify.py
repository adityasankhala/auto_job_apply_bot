"""macOS notification + beep, used when the bot pauses for manual input."""

import subprocess
import sys


def notify(title: str, message: str) -> None:
    # Terminal bell as a fallback/extra signal
    sys.stdout.write("\a")
    sys.stdout.flush()
    try:
        safe_msg = message.replace('"', "'")
        safe_title = title.replace('"', "'")
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe_msg}" with title "{safe_title}" sound name "Glass"'],
            check=False, timeout=10,
        )
    except Exception:
        pass  # notification is best-effort, never break the run
