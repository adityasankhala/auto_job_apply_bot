# Auto Job Applier

Job hunting is mostly clerical work. You find a listing, read it, decide in ten
seconds whether it's worth your time, and then spend five minutes retyping the
same name, the same email, the same "why do you want to work here" — over and
over, a few hundred times, until the hours you should have spent building
things are gone.

This repo automates the retyping. It does **not** automate the judgment.

Each bot drives a real Chrome window that you're logged into, reads each job
description, applies your filters, fills the form, and moves on — while you
watch a live log and can pause it at any moment. Anything it can't answer
honestly, it hands back to you.

## Principles

- **You stay in control.** You set the search filters yourself, in a real
  browser, on the site. The bot works through *your* results, not some
  scraped approximation of them.
- **Human-in-the-loop.** Any question the bot can't answer truthfully triggers
  a desktop notification and a pause. You answer it in the browser and click
  Continue. It never invents an answer about you.
- **Zero API cost.** Everything runs through your own logged-in browser
  session. No API keys, no tokens, no per-application billing. The Wellfound
  bot even personalizes answers by driving your own ChatGPT tab.
- **Nothing applied to twice.** Every job — applied, skipped, or failed, and
  why — is logged to a CSV. Links seen in any previous run are never reopened.
- **You decide the volume.** Batch mode applies to N jobs, then stops and asks
  before continuing. Quality over spray-and-pray.

## The bots

| Platform | Folder | Highlights |
|---|---|---|
| [Wellfound](https://wellfound.com) | [`wellfound_autoapply/`](wellfound_autoapply/) | ChatGPT-tab integration for personalized "why this company" answers, location-question auto-resolution, sleep mode |

More platforms to come. Each folder is self-contained — its own README,
config, and requirements — so you only set up the one you actually need.

## Quick start

```bash
git clone https://github.com/RishiDixit-7404/Auto-job-Applier-.git
cd Auto-job-Applier-/wellfound_autoapply
pip install -r requirements.txt
```

**Then edit `wellfound_bot/config.py` before your first run.** Every value in
it is a placeholder — the keywords, and especially the answer that gets pasted
into your applications. Running it unedited means applying to everything your
filters return with placeholder text in the answer box.

```bash
python3 -m wellfound_bot.app     # Tkinter UI (recommended)
python3 -m wellfound_bot.main    # or terminal mode
```

See [`wellfound_autoapply/README.md`](wellfound_autoapply/README.md) for the
full setup, including the optional ChatGPT integration.

## Requirements

Python 3.10+ with tkinter, and Google Chrome. The only third-party dependency
is Selenium — everything else is the standard library.

Each bot uses its own persistent Chrome profile (Chrome 136+ blocks automation
on your default one), so you log in to the job site once and the session
sticks across runs.

## Responsible use

These tools exist for personal productivity. A few things worth being honest
about:

- Automated use may be against a platform's terms of service. That's your call
  to make, and your risk to carry.
- Keep `action_delay` at 2 seconds or more. Hammering a site helps nobody.
- Read what you're applying to. An application you didn't mean to send is
  worse than one you never sent — it wastes a recruiter's time and yours.

## A note from the author

Created by an unemployed fresher at 3 AM — these bots exist because applying
to jobs manually was eating the hours I should have spent building things.

If you find bugs or have suggestions, **please raise a PR**. And to everyone
using this to land something — **all the best.** 🍀

## License

[MIT](LICENSE)
