"""
Wellfound Auto Applier - Configuration

⚠️  PERSONAL DETAILS: Search for "⚠️ FILL_IN" below and replace every one
with your real information before the first run.

Tuned for: Fresh graduate (0 YOE) in India targeting startup roles —
SDE, Backend, ML, DevOps, Full Stack.
"""

# Keywords to look for in the job description (case-insensitive, whole-word).
# One match = apply. Empty list = apply to everything your filters return.
# Also editable live in the UI while the bot runs.
keywords = [
    "python", "django", "flask", "fastapi",
    "java", "spring boot",
    "javascript", "react", "node",
    "c++", "cpp",
    "machine learning", "deep learning", "data science", "nlp",
    "tensorflow", "pytorch",
    "devops", "docker", "kubernetes", "aws", "gcp", "azure", "cloud",
    "software engineer", "software developer", "sde",
    "backend", "full stack", "fullstack",
    "api", "microservice",
    "sql", "mongodb", "postgresql",
]

# If any of these are present, the job must also have one of these words in the TITLE.
# Empty list = no strict title requirement.
require_title_keywords = [
    "software engineer", "software developer", "sde", "backend", "frontend",
    "full stack", "fullstack", "ml engineer", "machine learning", "data scientist",
    "data engineer", "ai engineer", "devops", "sre", "web developer", "app developer",
    "android", "ios", "react", "python"
]

# If ANY of these appears in the JOB TITLE (or URL slug), skip without opening.
# Also editable live in the UI.
exclude_title_keywords = [
    "senior", "sr.", "lead", "staff", "principal", "manager", "director", "vp",
    "head of", "architect",
    "sales", "marketing", "hr", "recruiter", "teacher", "telecaller",
    "bde", "business development", "content writer", "graphic designer",
    "chartered accountant", "support executive",
]

# Max years of experience allowed. Jobs requesting more than this will be skipped.
# 0-2 covers freshers/entry-level.
max_experience = 2

# ---------------------------------------------------------------- ChatGPT
# When True: the bot opens your ChatGPT chat/project in a tab of its Chrome
# window, sends each job description there, and pastes the reply into
# "What interests you about working for this company?".
# Set to False — we use a smart template below instead (no ChatGPT needed).
use_chatgpt = False

# URL of the ChatGPT chat/project to use (copy from the address bar).
chatgpt_url = "https://chatgpt.com/"

# What gets sent to ChatGPT ({jd} is replaced with the job description).
gpt_prompt = "{jd}"

# ⚠️ FILL_IN: Replace this with YOUR real answer. Mention your actual projects,
# tech stack, and what excites you. Generic answers get ignored by startups.
# {company} is replaced with the company name from the page.
interest_answer = (
    "I'm drawn to {company} because of the technical challenges and growth "
    "opportunities your team offers. As a final-year CS student, I've built "
    "projects using Python, Django, React, and ML — including a full-stack "
    "e-commerce application with secure authentication and an ML-powered "
    "recommendation engine. "
    "I'm eager to contribute my skills in full-stack development and data "
    "science to your team and can start immediately."
)

# Sleep mode (also a toggle in the UI): when the bot would otherwise need
# your attention (unanswerable eligibility question, form stuck disabled,
# unconfirmed submission), it does NOT pause - it saves the job to
# sleep_jobs.csv (title, company, url, jd, what it needed) and moves on to
# the next one. Review that sheet whenever you're back.
# Set True for unattended runs.
sleep_mode = True

import os
sleep_jobs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sleep_jobs.csv")

# Max applications to submit in one run (0 = unlimited)
# Wellfound is less throttle-aggressive than LinkedIn, so 50 is safe.
max_applications = 50

# Pause and ask "continue?" after this many applications (0 = never ask)
batch_size = 0

# Seconds to wait between actions
action_delay = 2

# Logs always land next to this file
import os
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_csv_path = os.path.join(_BASE_DIR, "applied_history.csv")
questions_log_path = os.path.join(_BASE_DIR, "questions_log.csv")

