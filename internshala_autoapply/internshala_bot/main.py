"""
Internshala Auto Applier - entry point

Flow:
1. Opens Chrome with your normal profile (already logged in to Internshala).
2. You set your filters manually, then press ENTER in the terminal.
3. Bot collects every listing link from the results pages, then for each job:
   detail page -> keyword check on JD -> Apply now -> Proceed to application
   -> fill cover letter -> Submit.
   If the form has custom employer questions, it logs them, sends a
   notification, and pauses so you can answer manually before it submits.

Run from the repo root:  python3 -m internshala_bot.main
"""

import csv
import os
import re
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from internshala_bot.browser import create_session
from internshala_bot.notify import notify
from internshala_bot import config


# ---------------------------------------------------------------- UI hooks
# The Tkinter app (app.py) replaces `hooks`; the terminal entry point uses the
# defaults. Module-level print/input are shadowed so every message and every
# manual-action pause in the bot flow routes through the hooks.
import builtins


class Hooks:
    def log(self, msg: str) -> None:
        builtins.print(msg)

    def confirm(self, prompt: str) -> None:
        """Block until the user says they've done the manual step."""
        builtins.input(prompt)

    def wait_if_paused(self) -> None:
        pass

    def on_progress(self, done: int, total: int, applied: int) -> None:
        pass


hooks = Hooks()


def print(*args, **kwargs):  # noqa: A001 - deliberate shadow of builtins
    hooks.log(" ".join(str(a) for a in args))


def input(prompt: str = ""):  # noqa: A001 - deliberate shadow of builtins
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


def log_external(url: str, title: str, external_url: str) -> None:
    append_csv(getattr(config, "external_jobs_path",
                       os.path.join(os.path.dirname(config.log_csv_path), "external_jobs.csv")),
               ["timestamp", "title", "url", "external_url"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, url, external_url])


def log_question(url: str, title: str, qtype: str, question: str, options: str = "") -> None:
    append_csv(config.questions_log_path,
               ["timestamp", "title", "url", "type", "question", "options"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, url, qtype, question, options])


def already_seen_urls() -> set[str]:
    """Every URL ever logged (applied, skipped, failed, error) - the bot never
    opens the same link twice across runs."""
    urls = set()
    if os.path.exists(config.log_csv_path):
        with open(config.log_csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                urls.add(row.get("url", ""))
    return urls


# ---------------------------------------------------------------- helpers

def current_url(driver) -> str:
    """driver.current_url can be None after manual navigation; never let
    'x in None' crash the run."""
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
    """Whole-word, case-insensitive match so short keywords like 'rag' or
    'git' don't fire inside words like 'storage' or 'digital'."""
    # Trailing "s?" so a keyword also matches its plural: "llm" hits "LLMs",
    # "embedding" hits "embeddings", "api" hits "APIs". Without it the
    # trailing boundary rejects the plural outright and the job is skipped.
    pattern = r"(?<![a-z0-9])" + re.escape(word.lower()) + r"s?(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def description_matches(description: str) -> bool:
    if not config.keywords:
        return True  # empty list = apply to everything
    # Also match hyphenated variants: "full-stack" should hit keyword "full stack"
    dehyphenated = description.replace("-", " ")
    return any(
        contains_word(description, kw) or contains_word(dehyphenated, kw)
        for kw in config.keywords
    )


def title_excluded(title: str) -> str | None:
    """Return the matched exclude word if the job title contains one."""
    for word in config.exclude_title_keywords:
        if contains_word(title, word):
            return word
    return None


def url_excluded(url: str) -> str | None:
    """The job title is embedded in the URL slug, so excluded jobs can be
    skipped without ever opening them."""
    slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
    return title_excluded(slug)


def get_jd_text(driver) -> str:
    """Job description text, scoped to the detail container so navbar/menu
    words don't cause false keyword matches."""
    for selector in (".internship_details", ".detail_view", ".individual_internship"):
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            if el.text.strip():
                return el.text
        except NoSuchElementException:
            continue
    return driver.find_element(By.TAG_NAME, "body").text


def find_apply_button(driver):
    """Find the Apply now / Easy Apply button on a detail page.
    Returns (element, state) where state is 'apply' or 'applied'."""
    candidates = driver.find_elements(
        By.CSS_SELECTOR,
        "button, a.btn, #easy_apply_button, .top_apply_now_cta"
    )
    for el in candidates:
        if not visible(el):
            continue
        text = (el.text or "").strip().lower()
        if text in ("applied", "already applied"):
            return el, "applied"
        if "apply" in text and "applied" not in text:
            # .top_apply_now_cta sits on the wrapper <div> as well as the real
            # <button> inside it, and the wrapper comes first in document order.
            # A native click on the wrapper still lands on the button, but a JS
            # click fires on the wrapper itself, which has no handler - so drill
            # down to the actual clickable element.
            if el.tag_name.lower() not in ("button", "a", "input"):
                inner = [i for i in el.find_elements(
                    By.CSS_SELECTOR, "button, a.btn, input[type='submit']") if visible(i)]
                if inner:
                    return inner[0], "apply"
            return el, "apply"
    return None, "not_found"


def click(driver, el) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    time.sleep(0.5)
    if getattr(config, "js_clicks", False):
        # A JS click never touches window focus, so Chrome stays in the
        # background instead of jumping to the front on every button.
        driver.execute_script("arguments[0].click();", el)
        return
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


def form_is_open(driver) -> bool:
    """The application is reachable either as its own /application/form/ page
    or as an Easy Apply modal on the job page, where the URL never changes."""
    if "/application/form" in current_url(driver):
        return True
    return any(visible(el) for el in driver.find_elements(By.CSS_SELECTOR, "input#submit"))


def external_redirect(driver) -> str:
    """Jobs that are applied to on the company's own site pop up a
    'You will be redirected to another website' modal instead of a form.
    Returns the outside URL when that popup is open, else ''."""
    for a in driver.find_elements(By.CSS_SELECTOR, "a.proceed-cta"):
        if visible(a):
            return a.get_attribute("href") or "unknown"
    # Fall back to the wording, in case the class changes.
    for h in driver.find_elements(By.CSS_SELECTOR, ".modal-content h4, .modal-body h4"):
        if visible(h) and "redirected to another website" in (h.text or "").lower():
            return "unknown"
    return ""


def close_modal(driver) -> None:
    for btn in driver.find_elements(
        By.CSS_SELECTOR, ".modal-content button.close, .modal-content [data-dismiss='modal']"
    ):
        if visible(btn):
            click(driver, btn)
            time.sleep(0.5)
            return


def wait_for_form_or_external(driver, timeout: int = 20) -> tuple[str, str]:
    """After clicking Apply, wait for one of three outcomes. Returns
    ('form', ''), ('external', outside_url) or ('timeout', '')."""
    end = time.time() + timeout
    while time.time() < end:
        outside = external_redirect(driver)
        if outside:
            return "external", outside
        if form_is_open(driver):
            return "form", ""
        # Intermediate resume page / modal on the way to the real form.
        for btn in driver.find_elements(By.CSS_SELECTOR, "button.proceed-btn"):
            if visible(btn):
                click(driver, btn)
                time.sleep(config.action_delay)
                break
        time.sleep(1)
    return ("form", "") if form_is_open(driver) else ("timeout", "")


# ---------------------------------------------------------------- form filling

def get_form(driver):
    """Return (container, submit).

    The submit button normally sits inside a <form>, but the Easy Apply modal
    renders it in a plain .easy_apply_footer container with no ancestor form,
    which used to raise before anything got filled. Fall back to the nearest
    modal body, then to the submit's own container."""
    submit = driver.find_element(By.CSS_SELECTOR, "input#submit")
    for xpath in (
        "./ancestor::form",
        "./ancestor::*[contains(@class, 'modal-content') or contains(@class, 'modal-body')]",
        "./ancestor::*[contains(@class, 'easy_apply') or contains(@class, 'application')]",
        "./ancestor::div[2]",
    ):
        try:
            return submit.find_element(By.XPATH, xpath), submit
        except NoSuchElementException:
            continue
    return submit.find_element(By.XPATH, "./.."), submit


def fill_cover_letters(driver, form) -> None:
    """Cover letter (and similar) boxes are Quill rich-text editors."""
    for editor in form.find_elements(By.CSS_SELECTOR, ".ql-editor"):
        if not visible(editor):
            continue
        if editor.text.strip():
            continue  # already has content
        driver.execute_script(
            "arguments[0].innerHTML = '<p>' + arguments[1] + '</p>';"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            editor, config.cover_letter,
        )
        time.sleep(0.5)


def label_for(driver, el) -> str:
    """Best-effort question text for an input: nearest form-group/label above it."""
    script = """
        var el = arguments[0];
        var node = el.closest('.form-group, .form_group, .additional_question, .assessment_question, fieldset');
        if (node) {
            var lbl = node.querySelector('label, .label, .question, legend');
            if (lbl && lbl.innerText.trim()) return lbl.innerText.trim();
            var txt = node.innerText.trim();
            if (txt) return txt.split('\\n')[0];
        }
        if (el.labels && el.labels.length) return el.labels[0].innerText.trim();
        return el.getAttribute('placeholder') || el.getAttribute('name') || '';
    """
    try:
        return (driver.execute_script(script, el) or "").strip()[:300]
    except Exception:
        return ""


def find_custom_questions(driver, form) -> list[dict]:
    """Return unanswered custom inputs as dicts: {el, type, question, options}."""
    questions = []

    for el in form.find_elements(By.CSS_SELECTOR, "textarea, input[type='text'], input[type='number']"):
        if not visible(el) or (el.get_attribute("value") or "").strip():
            continue
        questions.append({"el": el, "type": "text", "question": label_for(driver, el), "options": ""})

    # Empty rich-text editors other than ones we filled
    for el in form.find_elements(By.CSS_SELECTOR, ".ql-editor"):
        if visible(el) and not el.text.strip():
            questions.append({"el": el, "type": "richtext", "question": label_for(driver, el), "options": ""})

    # Radio / checkbox groups with nothing selected
    groups: dict[str, list] = {}
    for el in form.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox']"):
        if visible(el):
            groups.setdefault(el.get_attribute("name") or "unnamed", []).append(el)
    for name, els in groups.items():
        if any(e.is_selected() for e in els):
            continue
        opts = " | ".join(filter(None, (label_for(driver, e) for e in els)))[:300]
        qtype = "radio" if els[0].get_attribute("type") == "radio" else "checkbox"
        questions.append({"el": els[0], "type": qtype,
                          "question": label_for(driver, els[0]) or name, "options": opts})

    return questions


def canned_answer_for(question: str) -> str | None:
    for pattern, answer in config.canned_answers.items():
        if re.search(pattern, question, re.IGNORECASE):
            return answer
    return None


def fill_answer(driver, el, qtype: str, answer: str) -> None:
    if qtype == "richtext":
        driver.execute_script(
            "arguments[0].innerHTML = '<p>' + arguments[1] + '</p>';"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            el, answer,
        )
    else:
        el.clear()
        el.send_keys(answer)
    time.sleep(0.5)


def submit_application(driver, url: str, title: str) -> str:
    """Fill and submit the application form. Returns the status string."""
    form, submit = get_form(driver)
    fill_cover_letters(driver, form)

    unanswered = []
    for q in find_custom_questions(driver, form):
        answer = None
        if q["type"] in ("text", "richtext"):
            answer = canned_answer_for(q["question"])
        if answer:
            fill_answer(driver, q["el"], q["type"], answer)
            log_question(url, title, q["type"], q["question"], "[auto-answered]")
            print(f"✍️  Auto-answered: {q['question'][:80]}")
        else:
            log_question(url, title, q["type"], q["question"], q["options"])
            unanswered.append(q)

    if unanswered:
        notify("Internshala Bot", f"Custom questions on: {title}. Fill them in the browser!")
        print(f"\n⚠️  {len(unanswered)} unanswered question(s) on '{title}' — logged to {config.questions_log_path}")
        for q in unanswered:
            print(f"   - [{q['type']}] {q['question']}")
        input("Answer them in the browser, then press ENTER here to submit... ")

    if not form_is_open(driver):
        return "applied (submitted manually)"

    form, submit = get_form(driver)  # re-find, DOM may have changed
    click(driver, submit)

    if wait_for_submit_success(driver):
        return "applied"

    # Neither a success popup nor a page change: submission likely blocked
    notify("Internshala Bot", f"Submit blocked on: {title}. Finish it manually!")
    input("Submit didn't go through (required field?). Fix & submit in browser, then press ENTER... ")
    return "applied (manual finish)"


def wait_for_submit_success(driver, timeout: int = 12) -> bool:
    """Submission success shows either a 'submitted' popup/toast or navigates
    away from the form (e.g. to the recommended-jobs page)."""
    end = time.time() + timeout
    while time.time() < end:
        # Form page navigated away, or the Easy Apply modal closed.
        if not form_is_open(driver):
            return True
        for el in driver.find_elements(
            By.CSS_SELECTOR,
            "#success_modal, #success_modal_dual_button, .success_toast, "
            ".general_toast, .internshala-modal, .modal.in, .modal.show"
        ):
            try:
                if el.is_displayed() and "submit" in el.text.lower():
                    return True
            except Exception:
                continue
        time.sleep(1)
    return False


# ---------------------------------------------------------------- main loop

def collect_listing_links(driver) -> list[str]:
    links = []
    anchors = driver.find_elements(
        By.CSS_SELECTOR, "a[href*='/job/detail/'], a[href*='/internship/detail/']"
    )
    for a in anchors:
        href = a.get_attribute("href")
        if href and href not in links and "trainings.internshala" not in href:
            links.append(href)
    return links


def go_to_next_page(driver) -> bool:
    try:
        next_url = driver.find_element(By.CSS_SELECTOR, "link[rel='next']").get_attribute("href")
    except NoSuchElementException:
        return False
    if not next_url:
        return False
    driver.get(next_url)
    time.sleep(config.action_delay)
    return True


def process_job(driver, url: str) -> str:
    """Runs inside a fresh tab (opened/closed by the caller)."""
    driver.get(url)
    time.sleep(config.action_delay)

    try:
        h1 = driver.find_element(By.CSS_SELECTOR, "h1")
        title = h1.text.strip() if h1 is not None else ""
    except Exception:
        title = ""
    if not title:
        # fall back to the URL slug, which contains the job title
        title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")

    bad_word = title_excluded(title)
    if bad_word:
        log_result(url, title, f"skipped - excluded title word '{bad_word}'")
        print(f"⏭️  Excluded ('{bad_word}' in title): {title}")
        return "skipped"

    if not description_matches(get_jd_text(driver)):
        log_result(url, title, "skipped - no keyword match")
        print(f"⏭️  No keyword match: {title}")
        return "skipped"

    apply_btn, state = find_apply_button(driver)
    if state == "applied":
        log_result(url, title, "skipped - already applied")
        print(f"⏭️  Already applied: {title}")
        return "skipped"
    if state == "not_found":
        log_result(url, title, "failed - apply button not found")
        print(f"❌ Apply button not found: {title}")
        return "failed"

    click(driver, apply_btn)
    time.sleep(config.action_delay)

    outcome, outside_url = wait_for_form_or_external(driver)

    if outcome == "external":
        # Applying happens on the company's own site - close the popup, park the
        # job for manual follow-up, and move on without pausing.
        close_modal(driver)
        log_external(url, title, outside_url)
        log_result(url, title, "skipped - external application")
        print(f"🔗 Applies on the company's site — parked in {os.path.basename(config.external_jobs_path)}: {title}")
        return "skipped"

    if outcome == "timeout":
        notify("Internshala Bot", f"Stuck before the form on: {title}")
        input("Couldn't reach the application form. Get it open in the browser and press ENTER (or just press ENTER to skip)... ")
        if not form_is_open(driver):
            log_result(url, title, "failed - never reached application form")
            return "failed"

    status = submit_application(driver, url, title)
    log_result(url, title, status)
    print(f"✅ {status}: {title}")
    return "applied"


def gather_links(driver) -> list[str]:
    """Collect all listing links from the current (filtered) results page,
    dropping already-applied and title-excluded ones."""
    results_url = current_url(driver)
    all_links: list[str] = []
    while True:
        all_links.extend(l for l in collect_listing_links(driver) if l not in all_links)
        if not go_to_next_page(driver):
            break
    # Return the results tab to page 1 (walking rel=next can end on a
    # past-the-last page that renders as "Bad Request")
    driver.get(results_url)
    print(f"\nCollected {len(all_links)} listings from results pages.")

    if getattr(config, "skip_already_seen", False):
        done = already_seen_urls()
        before = len(all_links)
        all_links = [l for l in all_links if l not in done]
        if before - len(all_links):
            print(f"⏭️  {before - len(all_links)} links already seen in previous runs - not opening them again.")

    kept = []
    for l in all_links:
        word = url_excluded(l)
        if word:
            log_result(l, "", f"skipped - excluded title word '{word}' (from url)")
            print(f"⏭️  Excluded without opening ('{word}'): {l.rsplit('/', 1)[-1][:70]}")
        else:
            kept.append(l)
    all_links = kept
    print(f"{len(all_links)} left after removing already-applied and excluded ones.\n")
    return all_links


def apply_loop(driver, all_links: list[str]) -> int:
    """Process every link; returns the number of applications submitted."""
    results_tab = driver.current_window_handle

    applied = 0
    batch_mark = 0
    total = len(all_links)
    for i, url in enumerate(all_links, start=1):
        hooks.wait_if_paused()
        if config.max_applications and applied >= config.max_applications:
            print(f"Hit max_applications ({config.max_applications}), stopping.")
            break
        limit = config.max_applications or "∞"
        print(f"\n[{i}/{total} — {total - i} left | applied {applied}/{limit}]")
        # Each job opens in its own tab (like the manual flow) and the tab is
        # closed afterwards, leaving the results tab untouched.
        driver.switch_to.new_window("tab")
        try:
            if process_job(driver, url) == "applied":
                applied += 1
        except Exception as e:
            tb = traceback.format_exc()
            print(f"❌ Error on {url}: {e}\n{tb}")
            with open(os.path.join(os.path.dirname(config.log_csv_path), "errors.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {url}\n{tb}\n")
            log_result(url, "", f"error - {type(e).__name__}: {e}")
        finally:
            # Close the job tab (plus any extra tabs the site opened) and
            # return to the results tab.
            for handle in driver.window_handles:
                if handle != results_tab:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(results_tab)
        hooks.on_progress(i, total, applied)
        if config.batch_size and applied - batch_mark >= config.batch_size:
            batch_mark = applied
            notify("Internshala Bot", f"Batch done — {applied} applied. Continue?")
            input(f"🎯 Batch complete — {applied} applied so far, {total - i} jobs left. "
                  f"Press ENTER/Continue for the next {config.batch_size}... ")
        time.sleep(config.action_delay)

    print(f"\nDone. Applied to {applied} listings this run.")
    print(f"History: {config.log_csv_path}")
    print(f"Questions log: {config.questions_log_path}")
    return applied


def main():
    driver, wait, actions = create_session()
    driver.get("https://internshala.com/")

    input(
        "\nSet your filters on Internshala (profile, location, salary, etc.),\n"
        "then come back here and press ENTER to start applying... "
    )

    all_links = gather_links(driver)
    apply_loop(driver, all_links)
    input("Press ENTER to close the browser... ")
    driver.quit()


if __name__ == "__main__":
    main()
