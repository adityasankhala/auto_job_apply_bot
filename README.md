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
- **Or park it and keep going.** If you'd rather not be interrupted, sleep mode
  and easy-apply-only mode write those jobs to a spreadsheet — with the question
  it got stuck on, or the outside URL to apply at — and move on. You work
  through the sheet later instead of babysitting the run.
- **Zero API cost.** Everything runs through your own logged-in browser
  session. No API keys, no tokens, no per-application billing. The Wellfound
  bot even personalizes answers by driving your own ChatGPT tab.
- **It won't run half-configured.** Every `config.py` ships as placeholders, and
  the bot refuses to start while they're still in place — it lists what needs
  editing rather than pasting `REPLACE ME` into a real application.
- **Full history.** Every job — applied, skipped, or failed, and why — is
  logged to a CSV, so nothing is a black box and no job is a mystery later.
- **You decide the volume.** Batch mode applies to N jobs, then stops and asks
  before continuing. Quality over spray-and-pray.

## The bots

| Platform | Folder | Highlights |
|---|---|---|
| [Internshala](https://internshala.com) | [`internshala_autoapply/`](internshala_autoapply/) | Canned answers for recurring employer questions, cover-letter autofill, external-application jobs parked to a sheet instead of attempted |
| [LinkedIn](https://www.linkedin.com/jobs) | [`linkedin_autoapply/`](linkedin_autoapply/) | Multi-step Easy Apply form walker, typeahead-aware city fields, rate-limit pacing with a failure circuit breaker, unattended `autorun` mode |
| [Naukri](https://www.naukri.com) | [`naukri_autoapply/`](naukri_autoapply/) | Apply-chatbot auto-answering, easy-apply-only mode, sleep mode that parks attention-needing jobs into spreadsheets instead of pausing |
| [Wellfound](https://wellfound.com) | [`wellfound_autoapply/`](wellfound_autoapply/) | ChatGPT-tab integration for personalized "why this company" answers, location-question auto-resolution, sleep mode |

Each folder is self-contained — its own README, config, and requirements — so
you only set up the one you actually need. They share the same shape: same UI,
same keyword filtering, same CSV history, so learning one is learning all four.

## Quick start

Pick the bot for the platform you want — each folder is independent.

```bash
git clone https://github.com/RishiDixit-7404/Auto-job-Applier-.git
cd Auto-job-Applier-/internshala_autoapply
# or: linkedin_autoapply | naukri_autoapply | wellfound_autoapply
pip install -r requirements.txt
```

**Then edit the bot's `config.py` before your first run.** Every value in it is
a placeholder — the keywords, and especially the text that gets pasted into
your applications. Running it unedited means applying to everything your filters
return with `REPLACE ME` sitting in the answer box.

```bash
python3 -m internshala_bot.app     # Tkinter UI (recommended)
python3 -m internshala_bot.main    # or terminal mode
```

(Swap `internshala_bot` for `linkedin_bot`, `naukri_bot` or `wellfound_bot`
depending on the folder you picked.)

Set `max_applications = 1` for the first run and watch one application land
before letting it loose. Each folder's README has the full setup —
[Internshala](internshala_autoapply/README.md) ·
[LinkedIn](linkedin_autoapply/README.md) ·
[Naukri](naukri_autoapply/README.md) ·
[Wellfound](wellfound_autoapply/README.md).

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

I built this because I was fed up.

Fed up of filling the same form for the hundredth time. Fed up of retyping my
name, my email, my phone number, my "why do you want to work here" — and then
hearing nothing back. Not getting selected is hard enough; spending your whole
day on the part that isn't even the hard part is worse. Those were hours I
should have spent building things, and they were going into copy and paste.

So this exists for exactly one reason: **to automate the applying, so you can
get on with the getting hired.** That's the whole purpose. Nothing more
clever than that.

Use it to get a job. Genuinely — that's what it's for.

If you have suggestions, mail me or open an issue. If something's broken at my
end, raise a PR, or just mail me and I'll fix it. And if this script helps you
land something — **please tell me.** That would make all the 3 AM debugging
worth it, and honestly it's the only thank-you I'm after.

All the best for your journey.

**Peace.** 🍀

## License

[MIT](LICENSE)
