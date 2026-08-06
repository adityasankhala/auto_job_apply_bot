# LinkedIn Auto Applier

A desktop app that auto-applies to jobs on
[LinkedIn](https://www.linkedin.com/jobs) via Easy Apply. It walks the
multi-step application form, fills what it has been taught, and submits — while
you watch a live log and can pause at any point. Jobs it can't answer honestly
are parked in a spreadsheet instead of guessed at.

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![selenium](https://img.shields.io/badge/selenium-4.x-green)

## Features

- **Tkinter UI** — Open Chrome → log in + set your search → Start Applying.
  Pause/resume between jobs, live stats, colour-coded log.
- **Multi-step form walker** — fills each pane, advances Next → Review →
  Submit, and re-finds elements as the dialog re-renders itself between steps.
- **Typeahead-aware** — city and company fields are suggestion dropdowns, not
  plain text: typing alone leaves them invalid and blocks Next. The bot types,
  waits for the suggestion list, and clicks the matching entry.
- **Canned answers** — regex → answer pairs for the questions LinkedIn asks over
  and over (notice period, expected CTC, work authorisation, years *and* months
  of experience). First matching pattern wins.
- **Keyword matching that reads the whole description** — LinkedIn collapses
  long posts behind "See more", and the hidden half is where the tech stack
  usually lives. The bot expands it and falls back to `textContent`, so nothing
  below the fold is missed. Matching is whole-word, hyphen- and plural-tolerant
  (`llm` matches "LLMs").
- **Two spreadsheets instead of dead ends** — jobs with questions it can't
  answer go to `question_jobs.csv`; jobs that apply on the company's own site go
  to `external_jobs.csv`. Neither stops the run.
- **Rate-limit aware** — LinkedIn gates the Easy Apply flow server-side after a
  burst of submissions. `post_apply_delay` spaces applications out (after the
  job tab closes, not while it idles), and `failure_circuit_breaker` stops the
  run once apply attempts start failing back-to-back instead of walking the rest
  of the queue into a wall.
- **Unattended mode** — `autorun.py` runs with no human present: question-jobs
  are parked rather than waited on, and progress is written to `autorun.log`.

## Setup

Requires Python 3.10+ with tkinter, and Google Chrome. Selenium is the only
third-party dependency.

```bash
git clone https://github.com/RishiDixit-7404/Auto-job-Applier-.git
cd Auto-job-Applier-/linkedin_autoapply
pip install -r requirements.txt
```

> Use the **same** interpreter for `pip` and `python3`. If `python3 -m
> linkedin_bot.app` reports a missing module right after a successful install,
> that mismatch is why.

**Then edit `linkedin_bot/config.py`.** Everything in it is a placeholder:

| Setting | What to do |
|---|---|
| `keywords` | Add yours. **Empty means every job matches.** |
| `exclude_title_keywords` | Titles you never want. |
| `_years`, `_months`, `_notice` | Your real experience and notice period. |
| `_current_ctc`, `_expected_ctc` | Your real figures — these go into applications. |
| `_city`, `_phone`, `_linkedin`, `_portfolio`, `_github` | Your details. |
| `max_applications` | Set to `1` for your first run. |

## Run

```bash
python3 -m linkedin_bot.app       # UI (recommended)
python3 -m linkedin_bot.main      # terminal mode
python3 -m linkedin_bot.autorun --limit 1   # unattended, capped
```

1. Click **Open Chrome**. The bot uses its own Chrome profile because Chrome
   136+ blocks automation on your default one — log in to LinkedIn once in that
   window; the session persists.
2. Set up your job search with the filters you want. **Tick "Easy Apply"** — the
   bot can only complete Easy Apply postings.
3. Click **Start Applying**.

For `autorun`, paste your own search URL into `SEARCH_URL` in
`linkedin_bot/autorun.py`, or pass `--url`.

## Output files

All written next to `config.py`, and all git-ignored:

| File | Contents |
|---|---|
| `applied_history.csv` | Every job seen, with status and reason |
| `questions_log.csv` | Every form question encountered |
| `question_jobs.csv` | Jobs parked because a question couldn't be answered |
| `external_jobs.csv` | Jobs that apply on the company's own site |
| `errors.log` | Full tracebacks |

## Notes

- **LinkedIn is bot-hostile.** Keep `action_delay` at 2 or more and leave
  `post_apply_delay` alone unless you know what you're doing — roughly 33
  applications in 45 minutes was enough to get the Easy Apply flow gated
  server-side for hours.
- LinkedIn ships UI changes constantly, including a component-based rewrite with
  hashed class names. Selectors are grouped near the top of `linkedin_bot/main.py`.
- Desktop notifications use macOS `osascript`; other platforms still get the
  terminal bell and the flashing Continue button.
- Use responsibly. Automated use may be against LinkedIn's terms of service;
  read what you're applying to, and you are responsible for how you use this.

## License

MIT
