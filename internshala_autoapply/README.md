# Internshala Auto Applier

A desktop app that auto-applies to internships and fresher jobs on
[Internshala](https://internshala.com). It reads each job description, applies
your keyword filters, fills the cover letter and any employer questions it has
been taught, and submits — while you watch a live log and can pause at any point.

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![selenium](https://img.shields.io/badge/selenium-4.x-green)

## Features

- **Tkinter UI** — Open Chrome → log in + set your filters → Start Applying.
  Pause/resume between jobs, live stats, colour-coded log.
- **Keyword matching** — whole-word and hyphen-tolerant, matched against the
  job description only (not the navigation chrome). One hit is enough. Editable
  live in the UI while a run is going.
- **Bad-title filter** — excluded words are checked against the URL slug first,
  so unwanted roles are skipped without even opening the page.
- **Canned answers** — regex → answer pairs for the custom questions employers
  ask ("share your portfolio", "rate yourself out of 10"). The first matching
  pattern wins. Anything unmatched pauses and asks you, and **every** question
  is logged to `questions_log.csv` so you can turn the recurring ones into new
  canned answers over time.
- **Handles both apply flows** — the classic `/application/form/` page and the
  newer Easy Apply modal, which never changes the URL.
- **External applications are parked, not attempted** — jobs that redirect to
  the company's own careers site pop up a "you will be redirected" dialog. The
  bot closes it and records the job in `external_jobs.csv` **with the outside
  URL**, so you have a ready-made list to work through by hand.
- **Stays in the background** — buttons are clicked via JavaScript, so Chrome
  doesn't grab focus every few seconds. Toggle with `js_clicks`.
- **History** — every job (applied, skipped, failed, and why) lands in
  `applied_history.csv`.
- **Crash-proof** — per-job error isolation with full tracebacks in `errors.log`;
  one bad listing never ends the run.

## Setup

Requires Python 3.10+ with tkinter, and Google Chrome. Selenium is the only
third-party dependency.

```bash
git clone https://github.com/RishiDixit-7404/Auto-job-Applier-.git
cd Auto-job-Applier-/internshala_autoapply
pip install -r requirements.txt
```

> Use the **same** interpreter for `pip` and `python3`. If `python3 -m
> internshala_bot.app` reports a missing module right after a successful
> install, that mismatch is why — try `python3 -m pip install -r
> requirements.txt`.

**Then edit `internshala_bot/config.py`.** Everything in it is a placeholder:

| Setting | What to do |
|---|---|
| `keywords` | Add yours. **Empty means every job matches.** |
| `exclude_title_keywords` | Roles you never want. Add `"internship"` here if you only want fresher jobs. |
| `cover_letter` | Replace entirely — it goes into real applications. |
| `canned_answers` | Replace the `REPLACE ME` answers and the portfolio/GitHub links. |
| `max_applications` | Set to `1` for your first run. |

## Run

```bash
python3 -m internshala_bot.app     # UI (recommended)
python3 -m internshala_bot.main    # or terminal mode
```

1. Click **Open Chrome**. The bot uses its own Chrome profile
   (`~/.internshala_bot_profile`) because Chrome 136+ blocks automation on your
   default profile — log in to Internshala once in that window; it persists.
2. Set your filters on internshala.com (category, location, work-from-home,
   fresher jobs vs internships) and get to the results page you want.
3. Click **Start Applying**.

## How it decides

```
collect every listing link (walking pagination)
└─ skip: excluded word in the URL slug
open each job in its own tab
├─ skip: excluded word in the title
├─ skip: no keyword in the job description
├─ skip: already applied (Internshala shows "Applied" on the page)
└─ Apply
   ├─ redirect dialog  → close it, park in external_jobs.csv, move on
   ├─ form / modal     → cover letter + canned answers → Submit
   └─ unknown question → notify, pause, you answer in the browser, Continue
```

## Output files

All written next to `config.py`, and all git-ignored:

| File | Contents |
|---|---|
| `applied_history.csv` | Every job seen, with status and reason |
| `questions_log.csv` | Every employer question encountered |
| `external_jobs.csv` | Jobs to apply for yourself, with the outside URL |
| `errors.log` | Full tracebacks |

## Notes

- Desktop notifications use macOS `osascript`; other platforms still get the
  terminal bell and the flashing Continue button.
- Internshala's markup changes from time to time; selectors are grouped near the
  top of `internshala_bot/main.py`.
- Use responsibly. Keep `action_delay` at 2 or more, read what you're applying
  to, and remember automated use may be against Internshala's terms of service —
  this exists for personal productivity and you are responsible for how you use it.

## License

MIT
