"""
Naukri Auto Applier - Configuration

Edit EVERYTHING in this file before your first run. Every answer below is a
placeholder and the bot refuses to start while they are still in place.
"""

# Keywords to look for in the job description (case-insensitive, whole-word,
# hyphen- and plural-tolerant: "llm" also matches "LLMs").
# One match = apply. Empty list = apply to everything your search returns.
# Also editable live in the UI.
keywords = [
    # ADD YOUR OWN - e.g. "python", "react", "machine learning", "figma".
    # WARNING: an empty list means every job your search returns is a match.
]

# If ANY of these appears in the JOB TITLE (or URL slug), skip without opening.
# Editable live in the UI.
exclude_title_keywords = [
    # e.g. "intern", "sales", "telecaller" - roles you never want.
]

# ---------------------------------------------------------------- your answers
# Fill these in - they feed the canned answers below.
_notice = "REPLACE ME: e.g. Immediately, or 30 days"
_current_ctc = "0"                 # current annual salary / CTC
_expected_ctc = "0"                # expected annual salary / CTC
_total_experience = "0"            # total years of professional experience
_skill_experience = "0"            # years with a specific skill/tool
_location = "REPLACE ME: your city"
_links = "Portfolio: https://YOUR-PORTFOLIO.example | GitHub: https://github.com/YOUR-USERNAME"

# Auto-answers for the apply chatbot's questions. The FIRST regex
# (case-insensitive) matching the question wins.
# - Text questions: the answer is typed in.
# - Radio/chip questions: the bot picks the option whose label matches the
#   answer text (case-insensitive substring), so keep these short.
# Unknown questions notify + pause for manual input (and get logged to
# questions_log.csv, so recurring ones can become new entries here).
canned_answers = {
    r"notice period|when can you (start|join)|available|immediate":
        _notice,

    # ".{0,24}" so "current ANNUAL salary" and "expected yearly package" match
    # too - requiring the words to be adjacent misses most real phrasings.
    r"(current|present)\b.{0,24}?\b(ctc|salary|compensation|package)":
        _current_ctc,

    r"(expected|desired)\b.{0,24}?\b(ctc|salary|compensation|package)|salary expectation":
        _expected_ctc,

    # TOTAL/overall work experience. Checked first so it wins over the
    # skill-experience pattern below.
    r"total.*(work|professional|industry)?.*(experience|exp)|"
    r"(work|professional|industry).*(experience|exp)|"
    r"overall.*(experience|exp)|how many years.*(work|working)":
        _total_experience,

    # Experience with a specific SKILL/tool (e.g. "years of experience in
    # Python").
    r"(years|yrs).*(experience|exp)|experience.*(years|yrs)":
        _skill_experience,

    r"current location|where are you (located|based)":
        _location,

    r"willing to relocate|relocation|work from office|wfo":
        "Yes",

    r"portfolio|github|personal website":
        _links,

    r"why (should|do).*(hire|hired|join|fit)":
        "REPLACE ME: what you build, 2-3 projects you have shipped and what "
        "you did on them, the stack you work with, and your availability.",
}

# Easy-apply-only mode (also a toggle in the UI): when the apply chatbot
# question drawer appears, do NOT answer or pause - save the job (title,
# company, URL, JD) to question_jobs.csv for later manual review, close it,
# and move on to jobs that apply without questions.
easy_apply_only = False

# Sleep mode (also a toggle in the UI): when the bot would otherwise need
# your attention (unknown chatbot question, stuck drawer, unconfirmed
# submission), it does NOT pause - it saves the job to sleep_jobs.csv
# (title, company, url, jd, what it needed) and moves on to the next one.
# Review that sheet whenever you're back.
sleep_mode = False

import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where sleep-mode parked jobs get saved (opens in Excel)
sleep_jobs_path = os.path.join(_BASE_DIR, "sleep_jobs.csv")

# Where question-jobs get saved in easy-apply-only mode (opens in Excel)
question_jobs_path = os.path.join(_BASE_DIR, "question_jobs.csv")

# Where "apply on company site" jobs get saved (always; opens in Excel)
external_jobs_path = os.path.join(_BASE_DIR, "external_jobs.csv")

# Max applications to submit in one run (0 = unlimited).
# Set this to 1 for your first run so you can watch one application land.
max_applications = 0

# Pause and ask "continue?" after this many applications (0 = never ask)
batch_size = 0

# Seconds to wait between actions (keep >= 2 to look human)
action_delay = 2

# Logs always land next to this file
log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")
