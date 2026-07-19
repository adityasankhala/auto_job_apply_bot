"""
Wellfound Auto Applier - bot logic

Flow:
1. Open Chrome (own profile) -> you log in to wellfound.com and set filters.
2. Bot collects every job link from the results (scrolling / next pages).
3. Per job: open in its own tab -> title/keyword checks -> fill the
   "What interests you about working for this company?" box -> Apply.
   Jobs that require applying on the company's website are skipped.

Terminal mode:  python3 -m wellfound_bot.main   |   UI:  python3 -m wellfound_bot.app
"""

import csv
import os
import re
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException

from wellfound_bot.browser import create_session
from wellfound_bot.notify import notify
from wellfound_bot import config


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
    pattern = r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def description_matches(description: str) -> bool:
    if not config.keywords:
        return True  # empty list = apply to everything
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


def url_excluded(url: str) -> str | None:
    slug = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0].replace("-", " ")
    return title_excluded(slug)


def click(driver, el) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    time.sleep(0.5)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)


# ---------------------------------------------------------------- collection

JOB_LINK_RE = re.compile(r"/jobs/\d+-")


def collect_listing_links(driver) -> list[str]:
    links = []
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/']"):
        href = a.get_attribute("href") or ""
        if JOB_LINK_RE.search(href):
            href = href.split("?")[0]
            if href not in links:
                links.append(href)
    return links


def load_all_results(driver) -> list[str]:
    """Scroll to load lazy results; follow 'next page' links when present."""
    links: list[str] = []
    while True:
        # scroll until no new links appear on this page
        stable_rounds = 0
        while stable_rounds < 3:
            before = len(links)
            links.extend(l for l in collect_listing_links(driver) if l not in links)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            stable_rounds = stable_rounds + 1 if len(links) == before else 0
        print(f"   ...{len(links)} job links so far")

        # numbered/next pagination, if any
        next_el = None
        for sel in ("a[rel='next']", "a[aria-label='Next']", "button[aria-label='Next']"):
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if visible(el) and el.get_attribute("disabled") is None:
                    next_el = el
                    break
            if next_el:
                break
        if not next_el:
            break
        click(driver, next_el)
        time.sleep(config.action_delay + 1)
    return links


def gather_links(driver) -> list[str]:
    print("Collecting job links (scrolling through results)...")
    all_links = load_all_results(driver)
    print(f"\nCollected {len(all_links)} job links.")

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
    print(f"{len(kept)} left after removing already-applied and excluded ones.\n")
    return kept


# ---------------------------------------------------------------- applying

def get_company_name(driver) -> str:
    for sel in ("a[href^='/company/'] h2", "a[href^='/company/']", "h1 ~ * a[href*='/company/']"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            text = (el.text or "").strip().split("\n")[0]
            if text and len(text) < 60:
                return text
    return ""


def get_interest_answer(driver, company: str, jd: str) -> str:
    if config.use_chatgpt:
        try:
            from wellfound_bot.gpt import ask_gpt
            print("🤖 Asking ChatGPT...")
            answer = ask_gpt(driver, jd)
            if answer:
                print(f"🤖 GPT answered ({len(answer)} chars).")
                return answer
            print("⚠️  ChatGPT returned nothing, using fallback answer.")
        except Exception as e:
            print(f"⚠️  ChatGPT failed ({e}), using fallback answer.")
    return config.interest_answer.format(company=company or "this company")


# the real application form's submit: slide-in variant or modal variant
SUBMIT_SEL = ("button[data-test='JobApplicationModal--SubmitButton'], "
              "button[data-test='JobDescriptionSlideIn--SubmitButton']")


def find_submit(driver):
    for el in driver.find_elements(By.CSS_SELECTOR, SUBMIT_SEL):
        if visible(el):
            return el
    return None


def find_page_apply(driver):
    """The plain Apply button on the job page that OPENS the application modal.
    Returns (element, 'apply'|'applied'|'not_found')."""
    for el in driver.find_elements(
            By.CSS_SELECTOR, "button[class*='applyButton'], button[data-test='Button']"):
        if not visible(el):
            continue
        text = (el.text or "").strip().lower()
        if text in ("apply", "applied"):
            return el, text
    return None, "not_found"


def form_scope(driver, submit):
    try:
        return submit.find_element(By.XPATH, "./ancestor::form")
    except Exception:
        return driver


def set_textarea(driver, textarea, text: str) -> None:
    """React-compatible instant fill (send_keys is unreliable/slow for long
    multi-paragraph text)."""
    driver.execute_script(
        "const t = arguments[0], v = arguments[1];"
        "const setter = Object.getOwnPropertyDescriptor("
        "  window.HTMLTextAreaElement.prototype, 'value').set;"
        "setter.call(t, v);"
        "t.dispatchEvent(new Event('input', {bubbles: true}));"
        "t.dispatchEvent(new Event('change', {bubbles: true}));",
        textarea, text,
    )
    time.sleep(0.5)


def modal_scope(driver):
    """The open application modal — the page can contain a hidden duplicate of
    the form (slide-in variant), so queries must be scoped to the modal."""
    for el in driver.find_elements(By.CSS_SELECTOR, "[data-test='JobApplication-Modal']"):
        if visible(el):
            return el
    return None


def resolve_location_blocker(driver) -> bool:
    """On the location-mismatch question: pick 'I can relocate to…' and the
    first option in the location dropdown."""
    scope = modal_scope(driver) or driver

    radios = scope.find_elements(
        By.CSS_SELECTOR, "input[name='qualification.location.action'][value='relocate_to']")
    if not radios:
        return False
    radio = radios[0]

    def radio_selected() -> bool:
        try:
            return radio.is_selected()
        except Exception:
            return False

    def select_radio() -> bool:
        if radio_selected():
            return True
        # try every strategy until the radio actually reports selected
        attempts = [
            lambda: driver.execute_script("arguments[0].click();", radio),
            lambda: radio.click(),
        ]
        # its own label, resolved via the radio's actual id (duplicates exist)
        rid = radio.get_attribute("id") or ""
        if rid:
            labels = scope.find_elements(By.CSS_SELECTOR, f"label[for='{rid}']")
            if labels:
                attempts.append(lambda: click(driver, labels[0]))
        attempts.append(lambda: driver.execute_script(
            "const r = arguments[0];"
            "const setter = Object.getOwnPropertyDescriptor("
            "  window.HTMLInputElement.prototype, 'checked').set;"
            "setter.call(r, true);"
            "r.dispatchEvent(new Event('click', {bubbles: true}));"
            "r.dispatchEvent(new Event('input', {bubbles: true}));"
            "r.dispatchEvent(new Event('change', {bubbles: true}));",
            radio))
        for attempt in attempts:
            try:
                attempt()
            except Exception:
                pass
            time.sleep(0.8)
            if radio_selected():
                return True
        return False

    if not select_radio():
        print("⚠️  Couldn't select the relocate radio")

    # location react-select: if it has no value yet, open it and pick option 1
    for c in scope.find_elements(By.CSS_SELECTOR, ".select__control"):
        if not visible(c):
            continue
        if c.find_elements(By.CSS_SELECTOR, ".select__single-value"):
            break  # already has a value
        click(driver, c)
        time.sleep(1.5)
        # the dropdown menu can render outside the modal (portal) — search globally
        options = driver.find_elements(By.CSS_SELECTOR, ".select__option")
        if options:
            click(driver, options[0])
            time.sleep(0.5)
        break

    # picking the location can re-render the form and reset the radio — re-verify
    time.sleep(0.5)
    select_radio()
    return radio_selected()


def has_qualification_blockers(driver) -> bool:
    """Eligibility questions (e.g. location mismatch radios) that disable the
    form until answered. Presence check only — the styled radio inputs are
    visually hidden, so is_displayed() would miss them."""
    scope = modal_scope(driver) or driver
    return bool(scope.find_elements(By.CSS_SELECTOR, "input[name^='qualification']"))


def close_slide_in(driver) -> None:
    """Click the ✕ on the job slide-in after applying; ESC as fallback."""
    for sel in ("button[aria-label*='close' i]", "[data-test*='close' i]",
                "button[class*='close' i]"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            if visible(el):
                click(driver, el)
                time.sleep(0.5)
                return
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass


def page_says_applied(driver) -> bool:
    """Only buttons / applied-classed elements count — the sidebar nav has an
    'Applied' link on every page that must NOT match."""
    for el in driver.find_elements(By.CSS_SELECTOR, "button, div[class*='applied' i]"):
        try:
            if visible(el) and (el.text or "").strip().lower() in ("applied", "application submitted"):
                return True
        except Exception:
            continue
    return False


def process_job(driver, url: str) -> str:
    driver.get(url)
    time.sleep(config.action_delay + 1)

    try:
        h1 = driver.find_element(By.CSS_SELECTOR, "h1")
        title = h1.text.strip() if h1 is not None else ""
    except Exception:
        title = ""
    if not title:
        title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")

    bad_word = title_excluded(title)
    if bad_word:
        log_result(url, title, f"skipped - excluded title word '{bad_word}'")
        print(f"⏭️  Excluded ('{bad_word}' in title): {title}")
        return "skipped"

    jd = driver.find_element(By.TAG_NAME, "body").text
    if not description_matches(jd):
        log_result(url, title, "skipped - no keyword match")
        print(f"⏭️  No keyword match: {title}")
        return "skipped"

    # the application form may already be open (slide-in) or need the page
    # Apply button clicked first (modal)
    submit = find_submit(driver)
    if submit is None:
        apply_btn, state = find_page_apply(driver)
        if state == "applied":
            log_result(url, title, "skipped - already applied")
            print(f"⏭️  Already applied: {title}")
            return "skipped"
        if apply_btn is None:
            if re.search(r"apply on (the )?company", jd, re.IGNORECASE):
                log_result(url, title, "skipped - apply on company website")
                print(f"⏭️  External application: {title}")
            else:
                log_result(url, title, "failed - apply button not found")
                print(f"❌ Apply button not found: {title}")
            return "skipped"
        click(driver, apply_btn)
        end = time.time() + 10
        while time.time() < end and submit is None:
            time.sleep(1)
            submit = find_submit(driver)
        if submit is None:
            log_result(url, title, "failed - application modal did not open")
            print(f"❌ Application modal did not open: {title}")
            return "skipped"
        time.sleep(1.5)  # let the modal's qualification warnings render

    # hard rejection: company not accepting applications from this location
    scope = modal_scope(driver) or driver
    for el in scope.find_elements(By.CSS_SELECTOR, "[class*='fieldError']"):
        if visible(el) and "not accepting applications" in (el.text or "").lower():
            log_result(url, title, "skipped - not accepting applications from location")
            print(f"⏭️  Not accepting applications from your location: {title}")
            close_slide_in(driver)
            return "skipped"

    # eligibility questions (location etc.) disable the form until answered
    if submit.get_attribute("disabled") is not None and has_qualification_blockers(driver):
        print("📍 Location question — selecting 'I can relocate to…' + first dropdown option")
        resolve_location_blocker(driver)
        time.sleep(1)
        submit = find_submit(driver) or submit
    if submit.get_attribute("disabled") is not None and has_qualification_blockers(driver):
        notify("Wellfound Bot", f"Eligibility question on: {title}. Answer it in the browser!")
        input("⚠️  Couldn't auto-answer the eligibility question. Answer it in "
              "the browser (don't submit), then press ENTER/Continue... ")
        submit = find_submit(driver) or submit

    company = get_company_name(driver)
    answer = get_interest_answer(driver, company, jd)

    # fill every enabled, empty textarea in the form
    scope = form_scope(driver, submit)
    for t in scope.find_elements(By.TAG_NAME, "textarea"):
        if visible(t) and t.get_attribute("disabled") is None \
           and not (t.get_attribute("value") or "").strip():
            set_textarea(driver, t, answer)

    if submit.get_attribute("disabled") is not None:
        # the blocker may have rendered after the first check — try again now
        if has_qualification_blockers(driver):
            print("📍 Location question (late) — selecting 'I can relocate to…' + first option")
            resolve_location_blocker(driver)
            time.sleep(1)
            submit = find_submit(driver) or submit
            # textareas may only now be enabled — fill them
            scope = form_scope(driver, submit)
            for t in scope.find_elements(By.TAG_NAME, "textarea"):
                if visible(t) and t.get_attribute("disabled") is None \
                   and not (t.get_attribute("value") or "").strip():
                    set_textarea(driver, t, answer)

    if submit.get_attribute("disabled") is not None:
        notify("Wellfound Bot", f"Form still blocked on: {title}")
        input("⚠️  The Send button is still disabled — finish the form in the browser "
              "(don't submit), then press ENTER/Continue... ")
        submit = find_submit(driver) or submit

    click(driver, submit)
    time.sleep(config.action_delay + 1)

    # success check: button gone/disabled/"Applied", or an applied marker
    end = time.time() + 10
    while time.time() < end:
        try:
            if not visible(submit) or (submit.text or "").strip().lower() == "applied" \
               or submit.get_attribute("disabled") is not None:
                break
        except Exception:
            break  # stale button = form replaced = submitted
        if page_says_applied(driver):
            break
        time.sleep(1)
    else:
        notify("Wellfound Bot", f"Couldn't confirm submission: {title}")
        input("Couldn't confirm the application went through. Check the browser, "
              "finish it if needed, then press ENTER/Continue... ")
        log_result(url, title, "applied (manual check)")
        print(f"✅ applied (manual check): {title}")
        return "applied"

    close_slide_in(driver)
    log_result(url, title, "applied")
    print(f"✅ applied: {title}")
    return "applied"


# ---------------------------------------------------------------- main loop

def apply_loop(driver, all_links: list[str]) -> int:
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
        driver.switch_to.new_window("tab")
        try:
            if process_job(driver, url) == "applied":
                applied += 1
        except NoSuchWindowException:
            log_result(url, "", "skipped - job tab was closed")
            print(f"⏭️  Job tab was closed (manually?), moving on: {url.rsplit('/', 1)[-1][:60]}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"❌ Error on {url}: {e}\n{tb}")
            with open(os.path.join(os.path.dirname(config.log_csv_path), "errors.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {url}\n{tb}\n")
            log_result(url, "", f"error - {type(e).__name__}: {e}")
        finally:
            # close job tabs, but never the ChatGPT tab
            for handle in driver.window_handles:
                if handle == results_tab:
                    continue
                driver.switch_to.window(handle)
                if "chatgpt.com" in current_url(driver) or "chat.openai.com" in current_url(driver):
                    continue
                driver.close()
            driver.switch_to.window(results_tab)
        hooks.on_progress(i, total, applied)
        if config.batch_size and applied - batch_mark >= config.batch_size:
            batch_mark = applied
            notify("Wellfound Bot", f"Batch done — {applied} applied. Continue?")
            input(f"🎯 Batch complete — {applied} applied so far, {total - i} jobs left. "
                  f"Press ENTER/Continue for the next {config.batch_size}... ")
        time.sleep(config.action_delay)

    print(f"\nDone. Applied to {applied} listings this run.")
    print(f"History: {config.log_csv_path}")
    return applied


def main():
    driver, wait, actions = create_session()
    driver.get("https://wellfound.com/jobs")

    input(
        "\nLog in to Wellfound and set your job filters "
        "(tip: tick 'Hide jobs which require me to apply on the company's website'),\n"
        "then press ENTER to start applying... "
    )

    all_links = gather_links(driver)
    apply_loop(driver, all_links)
    input("Press ENTER to close the browser... ")
    driver.quit()


if __name__ == "__main__":
    main()
