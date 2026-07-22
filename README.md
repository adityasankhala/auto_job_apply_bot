# Wellfound Auto Applier

A desktop app that auto-applies to startup jobs on [Wellfound](https://wellfound.com)
(formerly AngelList Talent) — with an optional twist: it can send each job
description to **your own ChatGPT chat** in a browser tab and paste the reply
into "What interests you about working for this company?", giving every
application a personalized answer with **no API key and no API cost**.

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![selenium](https://img.shields.io/badge/selenium-4.x-green)

## Features

- **Tkinter UI** — Open Chrome → log in + set filters → Start Applying.
  Pause/resume, live stats, color-coded log.
- **ChatGPT-tab integration (optional)** — the bot drives a chatgpt.com tab in
  its own browser: types the JD into your project chat, waits for the reply to
  finish streaming, and pastes it into the application. Your project's custom
  instructions shape every answer. Falls back to a canned answer on failure.
- **Keyword matching** — whole-word, hyphen-tolerant; one match in the JD =
  apply. Editable live in the UI. Empty list = apply to everything.
- **Bad-title filter** — excluded words are checked against the URL slug, so
  unwanted jobs are skipped without even opening them. Editable live.
- **Handles Wellfound's apply flow** — the job-page Apply button, the
  application modal, the location-mismatch question (auto-selects
  "I can relocate to…" + the first location option), disabled-form states,
  "not accepting applications from your location" rejections, and
  external-application jobs (skipped).
- **Human-in-the-loop** — anything it can't resolve produces a desktop
  notification and a pause; you fix it in the browser and click Continue.
- **😴 Sleep mode** — walk away and let it run: instead of pausing, jobs that
  need your attention are parked in `sleep_jobs.csv` (title, company, URL,
  JD, and what it needed) and the bot moves straight on to the next one.
- **History & dedupe** — every job logged to `applied_history.csv`; links seen
  in ANY previous run are never opened again.
- **Crash-proof** — per-job error isolation, full tracebacks in `errors.log`.

## Setup

Requires Python 3.10+ with tkinter, and Google Chrome.

```bash
git clone <this-repo>
cd wellfound_autoapply
pip install -r requirements.txt
```

**Then edit `wellfound_bot/config.py`** — keywords, the interest answer, and
(optionally) your ChatGPT project URL. All values are placeholders.

## Run

```bash
python3 -m wellfound_bot.app     # UI (recommended)
python3 -m wellfound_bot.main    # or terminal mode
```

1. Click **Open Chrome**. The bot uses its own Chrome profile
   (`~/.wellfound_bot_profile`) because Chrome 136+ blocks automation on your
   default profile — log in to Wellfound (and chatgpt.com, if using GPT) once
   in that window; logins persist.
2. Set your job filters on wellfound.com/jobs. Tip: tick *"Hide jobs which
   require me to apply on the company's website"*.
3. Click **Start Applying**.

## ChatGPT setup (optional but recommended)

1. On chatgpt.com, create a **project** with instructions like: *"You will
   receive a job description. Reply ONLY with a ready-to-paste, first-person,
   3-4 sentence answer to 'What interests you about working for this
   company?', specific to what the company does."*
2. Open a chat inside the project and copy its URL into `chatgpt_url`.
3. Set `use_chatgpt = True`. The bot opens/finds that tab itself and never
   closes it. Start a fresh chat every session or two — very long chats make
   ChatGPT slower.

## How it decides

```
collect all job links (scroll + pagination)
└─ skip: seen in any previous run, or excluded word in the URL slug
open each job in its own tab
└─ skip: excluded word in title, no keyword in JD, already applied,
         external application, "not accepting applications" banner
Apply → modal → auto-resolve location question if present
→ ChatGPT round-trip (or canned answer) → fill → Send application → ✕ → next
```

## Notes

- Desktop notifications use macOS `osascript`; other platforms still get the
  terminal bell and the flashing Continue button.
- Wellfound's markup changes occasionally; selectors live near the top of
  `wellfound_bot/main.py`.
- Use responsibly. Keep `action_delay` ≥ 2, review what you're applying to,
  and remember automated use may be against Wellfound's terms of service —
  this tool exists for personal productivity, and you are responsible for how
  you use it.

## License

MIT
