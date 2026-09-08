"""
LinkedIn Auto Applier - Configuration

⚠️  PERSONAL DETAILS: Search for "⚠️ FILL_IN" below and replace every one
with your real information before the first run.

Tuned for: Fresh graduate (0 YOE) in India targeting SDE / Backend / ML /
DevOps / Full Stack roles. Rate-limit settings are calibrated for 2-3 runs
per day totalling ~70 LinkedIn applications.
"""

# Keywords to look for in the job description (case-insensitive, whole-word,
# hyphen- and plural-tolerant: "llm" also matches "LLMs").
# One match = apply. Empty list = apply to everything your filters return.
# Also editable live in the UI.
keywords = [
    "python", "django", "flask", "fastapi",
    "java", "spring boot",
    "javascript", "react", "node",
    "c++", "cpp",
    "machine learning", "deep learning", "data science", "nlp",
    "tensorflow", "pytorch",
    "devops", "docker", "kubernetes", "aws", "gcp", "azure", "cloud",
    "ci/cd", "terraform",
    "software engineer", "software developer", "sde",
    "backend", "full stack", "fullstack",
    "api", "microservice",
    "sql", "mongodb", "postgresql",
]

# If ANY of these appears in the JOB TITLE, skip. Editable live in the UI.
# Excludes senior roles (you're a fresh grad) and non-tech roles.
exclude_title_keywords = [
    "senior", "sr.", "lead", "staff", "principal", "manager", "director", "vp",
    "head of", "architect",
    "sales", "marketing", "hr", "recruiter", "teacher", "telecaller",
    "bde", "business development", "content writer", "graphic designer",
    "chartered accountant", "ca ", "support executive",
]

# ---------------------------------------------------------------- your answers
# ⚠️ FILL_IN: Replace every value below with YOUR real details.
# The bot refuses to start if placeholders survive.
_years = "0"                      # total years of professional experience
_months = "0"                     # additional months, if asked separately
_notice = "0"                     # notice period in days (0 = can join immediately)
_current_ctc = "0"                # current annual salary / CTC (0 for freshers)
_expected_ctc = "500000"               # expected annual salary / CTC (or a real figure like "400000")
_city = "Jaipur, India"             # e.g. "Delhi, India" or "Bangalore, Karnataka"
_phone = "8824271797"            # e.g. "9876543210"
_linkedin = "https://www.linkedin.com/in/aditya-saini-136041316/"         # e.g. "https://www.linkedin.com/in/your-name/"
_portfolio = " "        # e.g. "https://your-portfolio.dev" or your GitHub URL
_github = "https://github.com/adityasankhala"           # e.g. "https://github.com/your-username"
# "No" means "I do NOT need sponsorship" — applies to Indian nationals applying
# within India. Change to "Yes" if you're applying abroad and need a visa.
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

    r"(degree|education|qualification)":
        "Bachelor",

    r"(gpa|cgpa|grade|percentage)":
        "0",

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

    r"cover letter":
        "I am a final-year student passionate about technology and eager to "
        "contribute to your team. With hands-on experience in Python, ML, and "
        "full-stack development through personal projects, I am ready to start "
        "immediately and grow with your organization.",
}

# Easy-apply-only mode (also a toggle in the UI): when the Easy Apply form has
# a question the bot can't answer, do NOT pause - save the job to
# question_jobs.csv, dismiss it, and move on.
# Set True for unattended runs so it never blocks waiting for you.
easy_apply_only = True

import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where question-jobs get saved in easy-apply-only mode (opens in Excel)
question_jobs_path = os.path.join(_BASE_DIR, "question_jobs.csv")

# Where external-apply (non Easy Apply) jobs get saved (always)
external_jobs_path = os.path.join(_BASE_DIR, "external_jobs.csv")

# Max applications to submit in one run (0 = unlimited).
# Set to 35 to stay under LinkedIn's ~33-app throttle threshold with margin.
# Run 2-3 times/day for ~70-100 LinkedIn applications total.
max_applications = 35

# Pause and ask "continue?" after this many applications (0 = never ask)
batch_size = 0

# Seconds to wait between actions (LinkedIn is bot-hostile: keep >= 2).
action_delay = 3

# Extra seconds to wait after each SUBMITTED application (0 = none). Submissions,
# not page views, are what the apply flow rate-limits, so spacing those out is
# what actually keeps a long run alive. The wait happens after the job tab is
# closed, not while it sits open.
# 30s is aggressive but sustainable for 35-app bursts spaced 6+ hours apart.
post_apply_delay = 30

# Stop the run after this many apply attempts fail back-to-back (0 = never stop).
# LinkedIn throttles the Easy Apply flow after a burst of applications: it simply
# stops serving the form, so every subsequent job fails. Without this the bot
# would walk the rest of the queue against a wall.
failure_circuit_breaker = 5

log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")
