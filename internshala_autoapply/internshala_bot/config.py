"""
Internshala Auto Applier - Configuration

Edit EVERYTHING in this file before your first run. The keywords, the cover
letter, and the canned answers are placeholders - they are not usable as-is.
"""

# Keywords to look for in the job/internship description.
# If ANY one of these appears (case-insensitive, whole-word match), the bot
# hits Apply. Also editable live in the UI while the bot runs.
keywords = [
    # ADD YOUR OWN - e.g. "python", "react", "digital marketing", "figma".
    # WARNING: an empty list means every job your filters return is a match,
    # so fill this in before your first run.
]

# If ANY of these appears in the JOB TITLE (case-insensitive, whole-word),
# the job is skipped even when a keyword matches the description. This is also
# checked against the URL slug, so matches are skipped without opening the page.
# Also editable live in the UI.
exclude_title_keywords = [
    # e.g. "sales", "telecaller", "tutor" - roles you never want.
    # NOTE: Internshala hosts both internships and fresher jobs. If you only
    # want jobs, add "internship" here; if you want both, leave it out.
]

# Auto-filled into the "Why should you be hired for this role?" cover letter box.
# WRITE YOUR OWN - name real projects and the stack you actually work with.
# Generic cover letters get ignored.
cover_letter = (
    "REPLACE ME: what you build, 2-3 concrete projects you have shipped and "
    "what you did on them, the stack you work with, and your availability."
)

# Auto-answers for custom employer questions. The FIRST regex (case-insensitive)
# that matches the question text wins; its answer is typed into the box.
# Questions that match nothing still pause for manual input (and get logged to
# questions_log.csv, so you can turn recurring ones into new entries here).
canned_answers = {
    r"portfolio|github|behance|dribbble|personal website|profile link":
        "Portfolio: https://YOUR-PORTFOLIO.example | "
        "GitHub: https://github.com/YOUR-USERNAME",

    r"rate yourself|rate your|programming languages.*(used|know)|technical (tools|skills)":
        "REPLACE ME: rate your main tools out of 10, e.g. Python 8, SQL 7, Excel 7.",

    r"describe (one|a|any).*(project|website|automation|dashboard|api)|project.*worked on":
        "REPLACE ME: one project - what it does, what you built, which tools.",

    r"why (should|do).*(hire|hired|join|fit)":
        cover_letter,

    r"(available|availability|when can you (start|join))|notice period|immediate":
        "REPLACE ME: your actual availability, e.g. immediately / 30 days notice.",
}

# Max applications to submit in one run (0 = unlimited).
# Set this to 1 for your first run so you can watch one application land.
max_applications = 0

# Pause and ask "continue?" after this many applications (0 = never ask)
batch_size = 0

# Seconds to wait between actions (keep >= 2 to look human)
action_delay = 2

# Skip links that appear in applied_history.csv from earlier runs. Off, so every
# run walks the full result set again. Internshala still shows "Applied" on jobs
# you have already applied to and the bot skips those on the page itself, so
# this being off costs time, not duplicate applications. Turn it on for speed
# once your history file has grown.
skip_already_seen = False

# Click buttons via JavaScript instead of real mouse clicks. Real clicks make
# the OS pull the Chrome window to the front every single time, which makes the
# bot unusable while you work on something else. JS clicks don't touch focus.
# Set to False if a button stops responding - a few sites only react to real
# ("trusted") events, and a JS click on those silently does nothing.
js_clicks = True

# Logs always land next to this file, regardless of where the script is run from
import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where to log applied/skipped jobs
log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")

# Where custom employer questions get logged for later review
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")

# Jobs that redirect to the company's own website instead of applying on
# Internshala. The bot closes the redirect popup and parks them here so you can
# work through them by hand later.
external_jobs_path = os.path.join(_BASE_DIR, "external_jobs.csv")
