"""
Wellfound Auto Applier - Configuration
Edit EVERYTHING in this file before running: keywords, answers, and the
ChatGPT URL are examples/placeholders you must replace with your own.
"""

# Keywords to look for in the job description (case-insensitive, whole-word).
# One match = apply. Empty list = apply to everything your filters return.
# Also editable live in the UI while the bot runs.
keywords = [
    # ADD YOUR OWN - e.g. "python", "react", "digital marketing", "figma".
    # WARNING: an empty list means the bot applies to EVERY job your filters
    # return, so fill this in before your first run.
]

# If ANY of these appears in the JOB TITLE (or URL slug), skip without opening.
# Also editable live in the UI.
exclude_title_keywords = [
    # e.g. "sales", "intern", "telecaller", "support" - roles you never want,
    # matched against the job title / URL slug. Fine to leave empty.
]

# ---------------------------------------------------------------- ChatGPT
# When True: the bot opens your ChatGPT chat/project in a tab of its Chrome
# window, sends each job description there, and pastes the reply into
# "What interests you about working for this company?".
# Setup: create a ChatGPT project with instructions like "You will receive a
# job description. Reply ONLY with a ready-to-paste first-person answer to
# 'What interests you about working for this company?', 3-4 sentences,
# specific to the company." Then open a chat in it and paste its URL below.
# If GPT fails or is disabled, interest_answer is used instead.
use_chatgpt = False

# URL of the ChatGPT chat/project to use (copy from the address bar).
chatgpt_url = "https://chatgpt.com/"

# What gets sent to ChatGPT ({jd} is replaced with the job description).
gpt_prompt = "{jd}"

# Fallback (or only, when use_chatgpt = False) answer for the interest
# question. {company} is replaced with the company name from the page.
# WRITE YOUR OWN - mention your real projects; generic answers get ignored.
interest_answer = (
    "REPLACE ME: what draws you to {company}, 2-3 concrete projects you have "
    "shipped, the stack you work with, and that you can start immediately."
)

# Max applications to submit in one run (0 = unlimited)
max_applications = 0

# Seconds to wait between actions
action_delay = 2

# Logs always land next to this file
import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")
