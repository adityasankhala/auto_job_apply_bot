# Naukri Auto Applier

A desktop app that auto-applies to jobs on [Naukri](https://www.naukri.com).
Naukri's apply flow often opens a **chatbot drawer** that asks questions before
it will submit — this bot answers the ones it has been taught, and parks the
rest instead of guessing.

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![selenium](https://img.shields.io/badge/selenium-4.x-green)

## Features

- **Tkinter UI** — Open Chrome → log in + set your search → Start Applying.
  Pause/resume between jobs, live stats, colour-coded log.
- **Apply-chatbot answering** — Naukri asks its questions in a conversational
  drawer, one at a time. The bot reads each question, matches it against your
  canned answers, types or picks the option, and continues the conversation.
- **Keyword matching** — whole-word, hyphen- and plural-tolerant (`llm` matches
  "LLMs"). One hit in the description is enough. Editable live in the UI.
- **Bad-title filter** — excluded words are checked against the URL slug first,
  so unwanted roles are skipped without opening the page.
- **Easy-apply-only mode** — when the question drawer appears, don't answer and
  don't wait: save the job to `question_jobs.csv` and move on to jobs that apply
  in one click. Good for clearing volume fast.
- **Sleep mode** — walk away and let it run. Anything that would need you (an
  unknown question, a stuck drawer, an unconfirmed submit) is parked in
  `sleep_jobs.csv` with what it needed, instead of pausing the run.
- **External applications parked** — jobs that redirect to the company's own
  site go to `external_jobs.csv` rather than being attempted.
- **Refuses to run half-configured** — the bot stops with a list of what still
  needs editing rather than sending placeholder text to employers.
- **History** — every job (applied, skipped, failed, and why) lands in
  `applied_history.csv`.

## Setup

Requires Python 3.10+ with tkinter, and Google Chrome. Selenium is the only
third-party dependency.

```bash
git clone https://github.com/RishiDixit-7404/Auto-job-Applier-.git
cd Auto-job-Applier-/naukri_autoapply
pip install -r requirements.txt
```

> Use the **same** interpreter for `pip` and `python3`. If `python3 -m
> naukri_bot.app` reports a missing module right after a successful install,
> that mismatch is why.

**Then edit `naukri_bot/config.py`.** The bot will refuse to start until you do:

| Setting | What to do |
|---|---|
| `keywords` | Add yours. **Empty means every job matches.** |
| `exclude_title_keywords` | Titles you never want. |
| `_notice`, `_total_experience`, `_skill_experience` | Your real figures. |
| `_current_ctc`, `_expected_ctc` | Your real numbers — these go into applications. |
| `_location`, `_links` | Your city, portfolio and GitHub. |
| `max_applications` | Set to `1` for your first run. |

## Run

```bash
python3 -m naukri_bot.app     # UI (recommended)
python3 -m naukri_bot.main    # or terminal mode
```

1. Click **Open Chrome**. The bot uses its own Chrome profile
   (`~/.naukri_bot_profile`) because Chrome 136+ blocks automation on your
   default profile — log in to Naukri once in that window; it persists.
2. Set your search and filters on naukri.com.
3. Click **Start Applying**.

## How it decides

```
collect every job link from the search results
└─ skip: excluded word in the URL slug
open each job in its own tab
├─ skip: excluded word in the title
├─ skip: no keyword in the description
├─ skip: already applied
└─ Apply
   ├─ applies straight away        → done
   ├─ chatbot drawer appears       → answer known questions, or park the job
   │                                  (easy-apply-only / sleep mode)
   └─ redirects to company site    → park in external_jobs.csv
```

## Output files

All written next to `config.py`, and all git-ignored:

| File | Contents |
|---|---|
| `applied_history.csv` | Every job seen, with status and reason |
| `questions_log.csv` | Every chatbot question encountered |
| `question_jobs.csv` | Jobs parked in easy-apply-only mode |
| `sleep_jobs.csv` | Jobs parked in sleep mode, with what they needed |
| `external_jobs.csv` | Jobs that apply on the company's own site |
| `errors.log` | Full tracebacks |

## Notes

- Naukri's chatbot wording changes often; the question patterns live in
  `canned_answers` and are plain regexes — add to them as you meet new questions.
  `questions_log.csv` is there to tell you which ones keep coming up.
- Desktop notifications use macOS `osascript`; other platforms still get the
  terminal bell and the flashing Continue button.
- Use responsibly. Keep `action_delay` at 2 or more, read what you're applying
  to, and remember automated use may be against Naukri's terms of service — you
  are responsible for how you use this.

## License

MIT
