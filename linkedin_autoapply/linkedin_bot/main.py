"""
LinkedIn Auto Applier - bot logic (Easy Apply)

Flow:
1. Open Chrome (own profile) -> you log in to linkedin.com and set up your
   job search (keywords, filters; the "Easy Apply" filter is recommended).
2. Bot collects every job link from the results pages.
3. Per job: open in its own tab -> title/keyword checks -> Easy Apply ->
   walk the multi-step form (fill known fields from canned answers ->
   Next -> Review -> Submit). Unknown required fields notify + pause
   (or park the job in easy-apply-only mode). Non-Easy-Apply jobs are
   saved to the external-jobs sheet and skipped.

Terminal mode:  python3 -m linkedin_bot.main   |   UI:  python3 -m linkedin_bot.app
"""

import csv
import os
import re
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    NoSuchWindowException,
    StaleElementReferenceException,
)

from linkedin_bot.browser import create_session
from linkedin_bot.notify import notify
from linkedin_bot import config


# ---------------------------------------------------------------- UI hooks

import builtins


class Hooks:
    def log(self, msg: str) -> None:
        builtins.print(msg)

    def confirm(self, prompt: str) -> None:
        builtins.input(prompt)

    def wait_if_paused(self) -> None:
        pass

    def on_progress(self, done: int, total: int, applied: int) -> None:
        pass


hooks = Hooks()


def print(*args, **kwargs):  # noqa: A001 - deliberate shadow
    hooks.log(" ".join(str(a) for a in args))


def input(prompt: str = ""):  # noqa: A001 - deliberate shadow
    hooks.confirm(str(prompt))
    return ""


# ---------------------------------------------------------------- logging

def append_csv(path: str, header: list[str], row: list[str]) -> None:
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(header)
        writer.writerow(row)


def log_result(url: str, title: str, status: str) -> None:
    append_csv(config.log_csv_path,
               ["timestamp", "title", "url", "status"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, url, status])


def log_question(url: str, title: str, question: str, answer: str = "") -> None:
    append_csv(config.questions_log_path,
               ["timestamp", "title", "url", "question", "answer"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, url, question, answer])


# Outcomes that genuinely settle a job - it should never be opened again.
# Transient failures (form never opened, driver timeouts, unconfirmed submits) are
# deliberately NOT listed: if LinkedIn throttles the apply flow mid-run, or the
# driver hiccups, those jobs must stay retryable instead of being burned forever.
SETTLED_STATUSES = (
    "applied",
    "skipped - no keyword match",
    "skipped - already applied",
    "skipped - excluded title word",
    "skipped - has questions",
    "skipped - external application",
)


def already_seen_urls() -> set[str]:
    urls = set()
    if os.path.exists(config.log_csv_path):
        with open(config.log_csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row.get("status") or "").startswith(SETTLED_STATUSES):
                    urls.add(row.get("url", ""))
    return urls


# ---------------------------------------------------------------- helpers

def current_url(driver) -> str:
    try:
        return driver.current_url or ""
    except Exception:
        return ""


def visible(el) -> bool:
    try:
        return el.is_displayed()
    except Exception:
        return False


def contains_word(text: str, word: str) -> bool:
    # Trailing "s?" so a keyword matches its plural: "llm" hits "LLMs",
    # "embedding" hits "embeddings", "api" hits "APIs". Without it the trailing
    # boundary rejects the plural outright, which silently loses AI/ML jobs
    # whose descriptions only ever say "LLMs" or "AI agents".
    pattern = r"(?<![a-z0-9])" + re.escape(word.lower()) + r"s?(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def description_matches(description: str) -> bool:
    if not config.keywords:
        return True
    dehyphenated = description.replace("-", " ")
    return any(
        contains_word(description, kw) or contains_word(dehyphenated, kw)
        for kw in config.keywords
    )


def title_excluded(title: str) -> str | None:
    for word in config.exclude_title_keywords:
        if contains_word(title, word):
            return word
    return None


def click(driver, el) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    time.sleep(0.5)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


def canned_answer_for(question: str) -> str | None:
    for pattern, answer in config.canned_answers.items():
        if re.search(pattern, question, re.IGNORECASE):
            return answer
    return None


# ---------------------------------------------------------------- collection

# LinkedIn's jobs UI is server-driven (SDUI) and ships hashed CSS class names
# ("f77699bb", "_99bcde05", ...) that change on every deploy, so nothing here may
# key off a class. Every selector below leans on something semantic instead:
# componentkey, data-testid, aria-label, or the URL. Old-UI selectors are kept
# as trailing fallbacks so the bot still works if LinkedIn serves the old layout.

JOB_LINK_RE = re.compile(r"/jobs/view/(\d+)")

# Result cards are click-only <div role="button"> elements - they carry no href.
# Their job id lives in componentkey="job-card-component-ref-<jobId>".
CARD_SEL = "[componentkey^='job-card-component-ref-']"
# The scrollable results column (also used by the details pane, so pick by card count).
LIST_PANE_SEL = "[data-testid='lazy-column']"


def canonical_job_url(href: str) -> str | None:
    m = JOB_LINK_RE.search(href or "")
    return f"https://www.linkedin.com/jobs/view/{m.group(1)}/" if m else None


def job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def card_ids(driver) -> list[str]:
    """Job ids of every card currently rendered in the results list."""
    ids = driver.execute_script("""
        var out = [], seen = {};
        document.querySelectorAll(arguments[0]).forEach(function (el) {
            var m = (el.getAttribute('componentkey') || '').match(/(\\d+)$/);
            if (m && !seen[m[1]]) { seen[m[1]] = 1; out.push(m[1]); }
        });
        return out;
    """, CARD_SEL)
    return ids or []


def results_pane(driver):
    """The lazy-column that actually holds the job cards."""
    try:
        return driver.execute_script("""
            var panes = [].slice.call(document.querySelectorAll(arguments[0]));
            var cardSel = arguments[1];
            panes.sort(function (a, b) {
                return b.querySelectorAll(cardSel).length - a.querySelectorAll(cardSel).length;
            });
            return (panes.length && panes[0].querySelectorAll(cardSel).length) ? panes[0] : null;
        """, LIST_PANE_SEL, CARD_SEL)
    except Exception:
        return None


def collect_listing_links(driver) -> list[str]:
    """Cards render lazily, so scroll the results column until the id count settles."""
    ids = card_ids(driver)
    pane = results_pane(driver)
    if pane is not None:
        stale = 0
        for _ in range(25):
            driver.execute_script(
                "arguments[0].scrollTop = Math.min("
                "arguments[0].scrollTop + arguments[0].clientHeight * 0.8,"
                "arguments[0].scrollHeight);", pane)
            time.sleep(0.9)
            found = card_ids(driver)
            stale = stale + 1 if len(found) <= len(ids) else 0
            if len(found) > len(ids):
                ids = found
            if stale >= 3:
                break

    links = [job_url(i) for i in ids]
    # old-UI fallback: cards that are real anchors
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/view/']"):
        url = canonical_job_url(a.get_attribute("href"))
        if url and url not in links:
            links.append(url)
    return links


def go_to_next_page(driver) -> bool:
    """The real next-page control is data-testid='pagination-controls-next-button-*'.
    Note aria-label='Next' is NOT it - that's the AI-suggestions carousel arrow,
    which is why a class/aria-only match silently spins on page 1 forever."""
    for sel in ("button[data-testid='pagination-controls-next-button-visible']",
                "button[data-testid^='pagination-controls-next-button']",
                "button[aria-label='View next page']"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            if visible(el) and el.get_attribute("disabled") is None:
                click(driver, el)
                time.sleep(config.action_delay + 2)
                return True

    # numbered indicators: click whichever follows the one marked aria-current
    try:
        nxt = driver.execute_script("""
            var btns = [].slice.call(
                document.querySelectorAll("[data-testid^='pagination-indicator-']"));
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].getAttribute('aria-current') === 'true') return btns[i + 1] || null;
            }
            return null;
        """)
        if nxt is not None and visible(nxt):
            click(driver, nxt)
            time.sleep(config.action_delay + 2)
            return True
    except Exception:
        pass

    try:
        active = driver.find_element(By.CSS_SELECTOR,
                                     ".artdeco-pagination__indicator--number.active, li.active[data-test-pagination-page-btn]")
        nxt = active.find_element(By.XPATH, "following-sibling::li[1]//button")
        if visible(nxt):
            click(driver, nxt)
            time.sleep(config.action_delay + 2)
            return True
    except NoSuchElementException:
        pass
    return False


def gather_links(driver) -> list[str]:
    print("Collecting job links from results pages...")
    all_links: list[str] = []
    stale_rounds = 0
    while True:
        before = len(all_links)
        all_links.extend(l for l in collect_listing_links(driver) if l not in all_links)
        print(f"   ...{len(all_links)} job links so far")
        stale_rounds = stale_rounds + 1 if len(all_links) == before else 0
        if stale_rounds >= 2:
            print("   (no new links after next-page clicks — stopping collection)")
            break
        if not go_to_next_page(driver):
            break
    print(f"\nCollected {len(all_links)} job links.")

    done = already_seen_urls()
    before = len(all_links)
    all_links = [l for l in all_links if l not in done]
    if before - len(all_links):
        print(f"⏭️  {before - len(all_links)} links already seen in previous runs - not opening them again.")
    print(f"{len(all_links)} left to process.\n")
    return all_links


# ---------------------------------------------------------------- job page

def get_company(driver) -> str:
    for sel in (".job-details-jobs-unified-top-card__company-name a",
                ".job-details-jobs-unified-top-card__company-name",
                "a[href*='/company/']"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            text = (el.text or "").strip().split("\n")[0]
            if text and len(text) < 80:
                return text
    return ""


def get_title(driver) -> str:
    """The SDUI job page has no <h1> at all - the job title is a plain <p> with a
    hashed class. document.title ("<title> | <company> | LinkedIn") is the stable
    source; the h1 lookup stays as an old-UI fallback."""
    try:
        head = (driver.title or "").split(" | ")[0].strip()
        if head and head.lower() not in ("linkedin", "jobs"):
            return head
    except Exception:
        pass
    for sel in ("h1", "[data-sdui-screen] p"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            text = (el.text or "").strip()
            if text:
                return text.split("\n")[0]
    return ""


# The description lives in #JobDetails_AboutTheJob_<jobId>, also reachable by its
# SDUI component name. Falling back to whole-page text makes keyword matching
# meaningless (nav/sidebar/footer match almost anything), so that is logged loudly.
JD_SELECTORS = (
    "[id^='JobDetails_AboutTheJob_']",
    "[data-sdui-component$='aboutTheJob']",
    "#job-details",
    ".jobs-description",
    "[class*='jobs-description']",
)


SEE_MORE_SEL = (
    "button.jobs-description__footer-button, "
    "button[aria-label*='see more' i], "
    "button[aria-label*='Click to see more' i], "
    ".inline-show-more-text__button, "
    ".show-more-less-html__button"
)


def expand_jd(driver) -> None:
    """LinkedIn collapses long descriptions behind 'See more'. Selenium's .text
    only returns *rendered* text, so everything below the fold is invisible to
    keyword matching until the block is expanded."""
    for btn in driver.find_elements(By.CSS_SELECTOR, SEE_MORE_SEL):
        if visible(btn):
            try:
                click(driver, btn)
                time.sleep(0.4)
            except Exception:
                pass
            break


def get_jd_text(driver) -> str:
    expand_jd(driver)
    for sel in JD_SELECTORS:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            if visible(el) and (el.text or "").strip():
                # Belt and braces: if the block is still clipped, textContent
                # carries the full description even when .text does not.
                full = (el.get_attribute("textContent") or "").strip()
                return full if len(full) > len(el.text) else el.text
    print("⚠️  Couldn't find the job-description block — keyword matching will run "
          "against the whole page, which matches nearly everything.")
    return driver.find_element(By.TAG_NAME, "body").text


def save_job_to_sheet(path: str, driver, url: str, title: str, jd: str) -> None:
    append_csv(path,
               ["timestamp", "title", "company", "url", "jd"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, get_company(driver),
                url, " ".join(jd.split())[:3000]])


# Easy Apply is now an <a>, not a <button>: aria-label="Easy Apply to this job",
# href=".../jobs/view/<id>/apply/?openSDUIApplyFlow=true".
EASY_APPLY_SEL = ("a[aria-label*='Easy Apply'], a[href*='openSDUIApplyFlow'], "
                  "button[aria-label*='Easy Apply'], button.jobs-apply-button, "
                  "button[class*='jobs-apply']")
ANY_APPLY_SEL = "a[aria-label*='pply'], button[aria-label*='pply']"
# Present only on jobs already applied to (replaces the apply control).
APPLIED_SEL = "[componentkey='AppliedHowYouFitSlot']"


def find_apply_target(driver):
    """Returns (target, 'easy'|'external'|'applied'|'not_found').

    For 'easy' the target is the apply URL when we have one, because the SDUI flow
    only opens by navigation - clicking the anchor is a no-op (verified). Old-UI
    buttons come back as elements instead.
    """
    if driver.find_elements(By.CSS_SELECTOR, APPLIED_SEL):
        return None, "applied"

    for el in driver.find_elements(By.CSS_SELECTOR, EASY_APPLY_SEL):
        if not visible(el):
            continue
        label = ((el.get_attribute("aria-label") or "") + " " + (el.text or "")).lower()
        if "easy apply" in label or "opensduiapplyflow" in (el.get_attribute("href") or "").lower():
            return (el.get_attribute("href") or el), "easy"

    for el in driver.find_elements(By.CSS_SELECTOR, ANY_APPLY_SEL):
        if not visible(el):
            continue
        label = ((el.get_attribute("aria-label") or "") + " " + (el.text or "")).lower()
        if "easy apply" in label:
            return (el.get_attribute("href") or el), "easy"
        if "apply" in label and "resource" not in label:
            return el, "external"

    return None, "not_found"


# ---------------------------------------------------------------- Easy Apply modal

MODAL_SEL = "[role='dialog'], .jobs-easy-apply-modal, div[class*='jobs-easy-apply']"


def find_modal(driver):
    for el in driver.find_elements(By.CSS_SELECTOR, MODAL_SEL):
        if visible(el):
            return el
    return None


def open_easy_apply(driver, target) -> bool:
    """Open the Easy Apply dialog. The SDUI flow ignores clicks on its anchor
    (both native and scripted), so navigating to the apply URL is the only thing
    that actually opens it. Returns True once the dialog is on screen."""
    if isinstance(target, str):
        driver.get(target)
    else:
        click(driver, target)
    for _ in range(20):
        time.sleep(0.75)
        if find_modal(driver) is not None:
            return True
    return False


def application_confirmed(driver) -> bool:
    """Did LinkedIn actually acknowledge the submission?"""
    if driver.find_elements(By.CSS_SELECTOR, APPLIED_SEL):
        return True
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return False
    return any(s in body for s in ("application sent", "your application was sent",
                                   "application submitted", "done applying"))


def field_label(driver, el) -> str:
    script = """
        var el = arguments[0];
        if (el.labels && el.labels.length) return el.labels[0].innerText;
        var id = el.getAttribute('id');
        if (id) {
            var l = document.querySelector("label[for='" + CSS.escape(id) + "']");
            if (l) return l.innerText;
        }
        var g = el.closest('fieldset, .fb-dash-form-element, [class*="form-element"], div');
        if (g) {
            var lbl = g.querySelector('label, legend, span[aria-hidden="true"]');
            if (lbl) return lbl.innerText;
        }
        return el.getAttribute('placeholder') || el.getAttribute('aria-label') || '';
    """
    try:
        return (driver.execute_script(script, el) or "").strip()[:300]
    except Exception:
        return ""


def el_text(el) -> str:
    """Element text, tolerating a re-render between find and read."""
    try:
        return (el.text or "").strip()
    except StaleElementReferenceException:
        return ""
    except Exception:
        return ""


TYPEAHEAD_OPTION_SEL = (
    "[role='listbox'] [role='option'], [role='option'], "
    ".basic-typeahead__selectable, [data-testid*='typeahead'] li"
)


def pick_typeahead_option(driver, answer: str) -> bool:
    """City / location fields are typeaheads, not <select>s: typing the text is
    not enough. Until a suggestion is actually clicked the field stays invalid
    and Next stays disabled, so the whole application stalls. Returns True when
    an option was picked. No open suggestion list = not a typeahead = no-op."""
    time.sleep(0.8)
    opts = [o for o in driver.find_elements(By.CSS_SELECTOR, TYPEAHEAD_OPTION_SEL)
            if visible(o)]
    if not opts:
        return False
    # Prefer the suggestion that actually names the city: LinkedIn's option
    # text is usually longer than what was typed (it appends the country), so
    # match on the first comma-separated segment rather than the whole string.
    head = answer.split(",")[0].strip().lower()
    best = next((o for o in opts if head and head in el_text(o).lower()), opts[0])
    try:
        click(driver, best)
        time.sleep(0.5)
        return True
    except Exception:
        return False


def fill_modal_fields(driver, modal, url: str, title: str) -> list[str]:
    """Fill what we can; return labels of required fields we couldn't answer.

    The SDUI dialog re-renders itself as fields are filled, so any element handle
    can go stale mid-loop. Every interaction below is therefore individually
    guarded - a stale handle skips that one field instead of aborting the job.
    """
    unanswered = []

    # text / numeric inputs and textareas
    for el in modal.find_elements(By.CSS_SELECTOR,
                                  "input[type='text'], input[type='number'], input:not([type]), textarea"):
        try:
            if not visible(el) or (el.get_attribute("value") or "").strip():
                continue
            label = field_label(driver, el)
            answer = canned_answer_for(label)
            if answer:
                el.clear()
                el.send_keys(answer)
                time.sleep(0.4)
                if pick_typeahead_option(driver, answer):
                    print(f"   ↳ picked suggestion for '{label[:50]}'")
                log_question(url, title, label, f"[auto] {answer[:50]}")
                print(f"✍️  '{label[:60]}' → {answer[:40]}")
            else:
                unanswered.append(label or "unlabelled text field")
        except StaleElementReferenceException:
            continue

    # dropdowns
    for sel_el in modal.find_elements(By.TAG_NAME, "select"):
        try:
            if not visible(sel_el):
                continue
            try:
                current = sel_el.get_attribute("value") or ""
                first_opt = sel_el.find_elements(By.TAG_NAME, "option")[0].get_attribute("value") or ""
                if current and current != first_opt:
                    continue  # already answered
            except StaleElementReferenceException:
                continue
            except Exception:
                pass
            label = field_label(driver, sel_el)
            answer = canned_answer_for(label)
            picked = False
            if answer:
                for opt in sel_el.find_elements(By.TAG_NAME, "option"):
                    # read the text once - clicking re-renders the dialog and
                    # invalidates `opt`, so it cannot be read again afterwards
                    opt_text = el_text(opt)
                    if opt_text and answer.lower() in opt_text.lower():
                        opt.click()
                        picked = True
                        log_question(url, title, label, f"[auto] {opt_text[:50]}")
                        print(f"✍️  '{label[:60]}' → {opt_text[:40]}")
                        time.sleep(0.4)
                        break
            if not picked and answer is None:
                unanswered.append(label or "unlabelled dropdown")
        except StaleElementReferenceException:
            continue

    # radio groups (fieldsets)
    for fs in modal.find_elements(By.CSS_SELECTOR, "fieldset"):
        try:
            if not visible(fs):
                continue
            radios = fs.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if not radios or any(r.is_selected() for r in radios):
                continue
            label = field_label(driver, fs)
            answer = canned_answer_for(label)
            picked = False
            if answer:
                for r in radios:
                    r_label = field_label(driver, r)
                    if answer.lower() in r_label.lower():
                        rid = r.get_attribute("id")
                        targets = fs.find_elements(By.CSS_SELECTOR, f"label[for='{rid}']") if rid else []
                        click(driver, targets[0] if targets else r)
                        picked = True
                        log_question(url, title, label, f"[auto] {r_label[:40]}")
                        print(f"✍️  '{label[:60]}' → {r_label[:40]}")
                        time.sleep(0.4)
                        break
            if not picked and answer is None:
                unanswered.append(label or "unlabelled radio question")
        except StaleElementReferenceException:
            continue

    return unanswered


def modal_next_button(modal):
    """Priority: Submit > Review > Next/Continue."""
    for aria in ("Submit application", "Review your application", "Continue to next step"):
        for el in modal.find_elements(By.CSS_SELECTOR, f"button[aria-label*='{aria}']"):
            if visible(el):
                return el, aria
    for el in modal.find_elements(By.TAG_NAME, "button"):
        text = (el.text or "").strip().lower()
        if visible(el) and text in ("submit application", "review", "next", "continue"):
            return el, text
    return None, ""


def modal_has_errors(modal) -> bool:
    for el in modal.find_elements(By.CSS_SELECTOR,
                                  ".artdeco-inline-feedback--error, [class*='inline-feedback--error']"):
        if visible(el):
            return True
    return False


def dismiss_post_submit(driver) -> None:
    for el in driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Dismiss'], button[aria-label*='ismiss']"):
        if visible(el):
            click(driver, el)
            time.sleep(0.5)
            return


def run_easy_apply(driver, target, url: str, title: str, jd: str) -> str:
    """Walk the multi-step Easy Apply dialog.
    Returns 'applied' | 'skipped-questions' | 'skipped-no-form' | 'uncertain'."""
    if not open_easy_apply(driver, target):
        print(f"❌ Easy Apply form never opened: {title}")
        return "skipped-no-form"

    submitted = False
    for _step in range(15):
        modal = find_modal(driver)
        if modal is None:
            time.sleep(1)
            modal = find_modal(driver)
            if modal is None:
                # A vanished dialog is NOT proof of success - only a Submit click,
                # confirmed by LinkedIn, counts. Guessing here used to log jobs as
                # applied that were never submitted.
                if submitted and application_confirmed(driver):
                    return "applied"
                if submitted:
                    print(f"⚠️  Submitted but no confirmation seen: {title}")
                    return "uncertain"
                print(f"⏭️  Apply dialog closed before submitting: {title}")
                return "skipped-no-form"

        if "application sent" in (modal.text or "").lower():
            dismiss_post_submit(driver)
            return "applied"

        unanswered = fill_modal_fields(driver, modal, url, title)

        if unanswered:
            for q in unanswered:
                log_question(url, title, q, "[manual]")
            if config.easy_apply_only:
                save_job_to_sheet(config.question_jobs_path, driver, url, title, jd)
                print(f"📋 Has unknown questions — saved to spreadsheet, moving on: {title}")
                return "skipped-questions"
            notify("LinkedIn Bot", f"Questions on: {title}. Answer them in the browser!")
            print(f"⚠️  {len(unanswered)} unknown question(s): " + "; ".join(q[:60] for q in unanswered))
            input("Answer them in the browser (don't close the dialog), then press ENTER/Continue... ")

        modal = find_modal(driver)
        if modal is None:
            if submitted and application_confirmed(driver):
                return "applied"
            return "uncertain" if submitted else "skipped-no-form"
        btn, kind = modal_next_button(modal)
        if btn is None:
            notify("LinkedIn Bot", f"Stuck in the apply form on: {title}")
            input("Can't find the Next/Submit button — advance it in the browser, then press ENTER/Continue... ")
            continue
        click(driver, btn)
        time.sleep(config.action_delay)

        modal = find_modal(driver)
        if modal is not None and modal_has_errors(modal):
            if config.easy_apply_only:
                save_job_to_sheet(config.question_jobs_path, driver, url, title, jd)
                print(f"📋 Form errors (missing answers) — saved to spreadsheet: {title}")
                return "skipped-questions"
            notify("LinkedIn Bot", f"Form errors on: {title}. Fix them in the browser!")
            input("The form shows validation errors — fix them in the browser, then press ENTER/Continue... ")

        if "submit" in kind.lower():
            submitted = True
            time.sleep(2)
            confirmed = application_confirmed(driver)
            dismiss_post_submit(driver)
            if confirmed or application_confirmed(driver):
                return "applied"
            print(f"⚠️  Clicked Submit but LinkedIn showed no confirmation: {title}")
            return "uncertain"

    return "skipped-questions"


# ---------------------------------------------------------------- per job

def process_job(driver, url: str) -> str:
    driver.get(url)
    time.sleep(config.action_delay + 1)

    title = get_title(driver) or url

    bad_word = title_excluded(title)
    if bad_word:
        log_result(url, title, f"skipped - excluded title word '{bad_word}'")
        print(f"⏭️  Excluded ('{bad_word}' in title): {title}")
        return "skipped"

    jd = get_jd_text(driver)
    if not description_matches(jd):
        log_result(url, title, "skipped - no keyword match")
        print(f"⏭️  No keyword match: {title}")
        return "skipped"

    target, state = find_apply_target(driver)
    if state == "applied":
        log_result(url, title, "skipped - already applied")
        print(f"⏭️  Already applied: {title}")
        return "skipped"
    if state == "external":
        save_job_to_sheet(config.external_jobs_path, driver, url, title, jd)
        log_result(url, title, "skipped - external application")
        print(f"📋 External application — saved to spreadsheet: {title}")
        return "skipped"
    if target is None:
        log_result(url, title, "failed - apply button not found")
        print(f"❌ Apply button not found: {title}")
        return "skipped"

    outcome = run_easy_apply(driver, target, url, title, jd)
    if outcome == "applied":
        log_result(url, title, "applied")
        print(f"✅ applied: {title}")
        return "applied"
    if outcome == "uncertain":
        log_result(url, title, "uncertain - submitted, no confirmation seen")
        return "uncertain"
    log_result(url, title, "skipped - has questions (easy apply only)"
               if outcome == "skipped-questions" else f"skipped - {outcome}")
    return outcome


# ---------------------------------------------------------------- main loop

def apply_loop(driver, all_links: list[str]) -> int:
    results_tab = driver.current_window_handle

    applied = 0
    batch_mark = 0
    consecutive_failures = 0
    total = len(all_links)
    for i, url in enumerate(all_links, start=1):
        hooks.wait_if_paused()
        if config.max_applications and applied >= config.max_applications:
            print(f"Hit max_applications ({config.max_applications}), stopping.")
            break
        # Circuit breaker: when LinkedIn throttles the apply flow it stops serving
        # the form entirely, so every remaining job would "fail" in a row. Bail out
        # rather than chewing through the whole queue against a wall.
        if consecutive_failures >= config.failure_circuit_breaker > 0:
            print(f"\n🛑 {consecutive_failures} apply attempts failed in a row — "
                  f"LinkedIn is very likely throttling the apply flow. Stopping here "
                  f"with {total - i + 1} job(s) untouched so they can be retried later.")
            notify("LinkedIn Bot", "Apply flow looks throttled — run stopped early.")
            break
        limit = config.max_applications or "∞"
        print(f"\n[{i}/{total} — {total - i} left | applied {applied}/{limit}]")
        driver.switch_to.new_window("tab")
        just_applied = False
        try:
            outcome = process_job(driver, url)
            if outcome == "applied":
                applied += 1
                consecutive_failures = 0
                just_applied = True
            elif outcome in ("skipped-no-form", "uncertain"):
                consecutive_failures += 1
            else:
                consecutive_failures = 0
        except NoSuchWindowException:
            log_result(url, "", "skipped - job tab was closed")
            print(f"⏭️  Job tab was closed (manually?), moving on: {url}")
        except Exception as e:
            consecutive_failures += 1
            tb = traceback.format_exc()
            print(f"❌ Error on {url}: {e}\n{tb}")
            with open(os.path.join(os.path.dirname(config.log_csv_path), "errors.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {url}\n{tb}\n")
            log_result(url, "", f"error - {type(e).__name__}: {e}")
        finally:
            for handle in driver.window_handles:
                if handle != results_tab:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(results_tab)

        # Submissions are what gets rate-limited, so space them out - but wait
        # *after* the job tab is closed, not while it sits open doing nothing.
        if just_applied and getattr(config, "post_apply_delay", 0) > 0:
            time.sleep(config.post_apply_delay)

        hooks.on_progress(i, total, applied)
        if config.batch_size and applied - batch_mark >= config.batch_size:
            batch_mark = applied
            notify("LinkedIn Bot", f"Batch done — {applied} applied. Continue?")
            input(f"🎯 Batch complete — {applied} applied so far, {total - i} jobs left. "
                  f"Press ENTER/Continue for the next {config.batch_size}... ")
        time.sleep(config.action_delay)

    print(f"\nDone. Applied to {applied} listings this run.")
    print(f"History: {config.log_csv_path}")
    return applied


def main():
    driver, wait, actions = create_session()
    driver.get("https://www.linkedin.com/jobs/")

    input(
        "\nLog in to LinkedIn and set up your job search (keywords + filters;\n"
        "tip: enable the 'Easy Apply' filter), then press ENTER to start applying... "
    )

    all_links = gather_links(driver)
    apply_loop(driver, all_links)
    input("Press ENTER to close the browser... ")
    driver.quit()


if __name__ == "__main__":
    main()
