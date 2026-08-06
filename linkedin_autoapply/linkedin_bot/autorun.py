"""
Unattended LinkedIn Easy Apply run.

    python3 -m linkedin_bot.autorun            # apply to everything the search returns
    python3 -m linkedin_bot.autorun --limit 1  # stop after N applications (validation)

No human is watching, so this run never blocks:
  * easy_apply_only = True  -> jobs with questions the bot can't answer honestly
    are parked in question_jobs.csv instead of waiting for someone to type.
  * confirm() logs and returns immediately rather than waiting on stdin.
Progress goes to linkedin/autorun.log as well as stdout.
"""

import argparse
import os
import sys
import time

from linkedin_bot import config

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_BASE_DIR, "autorun.log")

# REPLACE THIS with your own search: set up the search on linkedin.com/jobs
# with the filters you want (Easy Apply on, date posted, salary, location) and
# paste the resulting address-bar URL here, or pass it with --url.
#   f_AL=true   -> Easy Apply only (strongly recommended for unattended runs)
#   f_TPR=r604800 -> posted in the last 7 days
SEARCH_URL = (
    "https://www.linkedin.com/jobs/search-results/"
    "?keywords=python&f_AL=true&f_TPR=r604800"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25,
                    help="max applications this session (0 = unlimited). "
                         "Default 25: LinkedIn gated the apply flow after ~33 in one burst.")
    ap.add_argument("--delay", type=int, default=4, help="seconds between actions")
    ap.add_argument("--apply-delay", type=int, default=45,
                    help="extra seconds to wait after each submitted application")
    ap.add_argument("--url", default=SEARCH_URL)
    args = ap.parse_args()

    config.easy_apply_only = True   # park question-jobs instead of blocking
    config.batch_size = 0           # never stop to ask
    config.max_applications = args.limit
    # Pacing. A previous run did ~33 applications in 45 min and LinkedIn gated the
    # Easy Apply flow server-side for hours afterwards, so an unattended run now
    # spaces submissions out and caps itself per session by default.
    config.action_delay = max(config.action_delay, args.delay)
    config.post_apply_delay = args.apply_delay

    from linkedin_bot import main as bot
    from linkedin_bot.browser import create_session

    log_file = open(LOG_PATH, "a", buffering=1, encoding="utf-8")

    def write(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")

    class AutoHooks(bot.Hooks):
        def log(self, msg: str) -> None:
            write(msg)

        def confirm(self, prompt: str) -> None:
            # Nobody is here to answer; note it and let the walker move on.
            write("[auto-continue] " + " ".join(str(prompt).split())[:160])

        def wait_if_paused(self) -> None:
            pass

        def on_progress(self, done: int, total: int, applied: int) -> None:
            write(f"[progress] {done}/{total} processed · {applied} applied")

    bot.hooks = AutoHooks()

    write("=" * 70)
    write(f"autorun start · limit={args.limit or '∞'} · easy_apply_only=True")

    driver, _wait, _actions = create_session()
    try:
        driver.get(args.url)
        time.sleep(10)
        if "login" in driver.current_url or "authwall" in driver.current_url:
            write("❌ Not logged in to LinkedIn in the bot profile — aborting.")
            return 2

        links = bot.gather_links(driver)
        if not links:
            write("❌ No job links collected — aborting rather than spinning.")
            return 3

        applied = bot.apply_loop(driver, links)
        write(f"autorun finished · {applied} application(s) submitted")
        return 0
    except Exception as e:
        import traceback
        write(f"❌ autorun crashed: {type(e).__name__}: {e}")
        write(traceback.format_exc())
        return 1
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        log_file.close()


if __name__ == "__main__":
    sys.exit(main())
