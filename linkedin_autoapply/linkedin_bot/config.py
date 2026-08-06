"""
LinkedIn Auto Applier - Configuration

Edit EVERYTHING in this file before your first run. Every answer below is a
placeholder and none of them are usable as-is.
"""

# Keywords to look for in the job description (case-insensitive, whole-word,
# hyphen- and plural-tolerant: "llm" also matches "LLMs").
# One match = apply. Empty list = apply to everything your filters return.
# Also editable live in the UI.
keywords = [
    # ADD YOUR OWN - e.g. "python", "react", "machine learning", "figma".
    # WARNING: an empty list means every job your search returns is a match.
]

# If ANY of these appears in the JOB TITLE, skip. Editable live in the UI.
exclude_title_keywords = [
    # e.g. "intern", "sales", "teacher" - roles you never want.
]

# ---------------------------------------------------------------- your answers
# Fill these in. They feed the canned answers below, so each value lives in
# exactly one place.
_years = "0"                      # total years of professional experience
_months = "0"                     # additional months, if asked separately
_notice = "0"                     # notice period in days
_current_ctc = "0"                # current annual salary / CTC
_expected_ctc = "0"               # expected annual salary / CTC
_city = "YOUR CITY, YOUR STATE"   # typed into location typeaheads
_phone = "YOUR PHONE NUMBER"
_linkedin = "https://www.linkedin.com/in/YOUR-PROFILE/"
_portfolio = "https://YOUR-PORTFOLIO.example"
_github = "https://github.com/YOUR-USERNAME"
# "No" means "I do NOT need sponsorship" - it answers sponsorship questions
# verbatim, so set it to whatever is true for you.
_visa = "No"

# Auto-answers for Easy Apply form questions. The FIRST regex
# (case-insensitive) matching a field's label wins.
# - Text/number fields: the answer is typed in. If a suggestion dropdown opens
#   (city, company, school), the matching suggestion is clicked automatically.
# - Dropdowns/radios: the option whose label matches the answer (substring) is
#   picked, so keep those short (e.g. "Yes", "0", "4").
# Unknown required fields notify + pause (or park the job in easy-only mode).
canned_answers = {
    # LinkedIn often splits total experience across a years dropdown and a
    # months dropdown. These go FIRST so they win over the generic pattern.
    r"total years.*experience|years of professional experience":
        _years,

    r"additional months.*experience|months of experience":
        _months,

    r"how many years.*(experience|work)|years of (work )?experience":
        _years,

    r"notice period":
        _notice,

    # ".{0,24}" so "current ANNUAL salary / ctc" or "expected yearly
    # compensation" still match - requiring the two words to be adjacent
    # silently misses every "annual" phrasing.
    r"(current|present)\b.{0,24}?\b(ctc|salary|compensation|package)":
        _current_ctc,

    r"(expected|desired)\b.{0,24}?\b(ctc|salary|compensation|package)|salary expectation":
        _expected_ctc,

    r"(current )?(city|location)":
        _city,

    r"willing to relocate|relocation|commut":
        "Yes",

    # "authorized to work" -> Yes; a visa *sponsorship* question is the
    # opposite, so it gets its own entry above this one (first match wins).
    r"require (visa|sponsorship)|need sponsorship|visa sponsorship":
        _visa,

    r"work authorization|authorized to work|legally|eligible to work|visa":
        "Yes",

    r"start immediately|available to (start|join)|immediate":
        "Yes",

    r"portfolio|personal website|website url":
        _portfolio,

    r"github":
        _github,

    r"linkedin profile":
        _linkedin,

    r"phone|mobile":
        _phone,

    r"english|hindi|language proficiency":
        "Professional",
}

# Easy-apply-only mode (also a toggle in the UI): when the Easy Apply form has
# a question the bot can't answer, do NOT pause - save the job to
# question_jobs.csv, dismiss it, and move on.
easy_apply_only = False

import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where question-jobs get saved in easy-apply-only mode (opens in Excel)
question_jobs_path = os.path.join(_BASE_DIR, "question_jobs.csv")

# Where external-apply (non Easy Apply) jobs get saved (always)
external_jobs_path = os.path.join(_BASE_DIR, "external_jobs.csv")

# Max applications to submit in one run (0 = unlimited).
# Set this to 1 for your first run so you can watch one application land.
max_applications = 0

# Pause and ask "continue?" after this many applications (0 = never ask)
batch_size = 0

# Seconds to wait between actions (LinkedIn is bot-hostile: keep >= 2).
# A 45-minute burst of ~33 applications at delay=3 got the Easy Apply flow gated
# server-side for hours, so the unattended runner uses a larger value than this.
action_delay = 2

# Extra seconds to wait after each SUBMITTED application (0 = none). Submissions,
# not page views, are what the apply flow rate-limits, so spacing those out is
# what actually keeps a long run alive. The wait happens after the job tab is
# closed, not while it sits open.
post_apply_delay = 45

# Stop the run after this many apply attempts fail back-to-back (0 = never stop).
# LinkedIn throttles the Easy Apply flow after a burst of applications: it simply
# stops serving the form, so every subsequent job fails. Without this the bot
# would walk the rest of the queue against a wall.
failure_circuit_breaker = 4

log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")
