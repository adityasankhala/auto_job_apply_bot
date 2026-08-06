"""
Naukri Auto Applier - bot logic

Flow:
1. Open Chrome (own profile) -> you log in to naukri.com and run your search.
2. Bot collects every job link from the results pages.
3. Per job: open in its own tab -> title/keyword checks -> click Apply ->
   answer the apply-chatbot drawer's questions (canned answers; pauses for
   unknown ones) -> confirm success -> next job.
   "Apply on company site" jobs are skipped.

Terminal mode:  python3 -m naukri_bot.main   |   UI:  python3 -m naukri_bot.app
"""

import csv
import os
import re
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException

from naukri_bot.browser import create_session
from naukri_bot.notify import notify
from naukri_bot import config


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


def log_question(url: str, title: str, qtype: str, question: str, answer: str = "") -> None:
    append_csv(config.questions_log_path,
               ["timestamp", "title", "url", "type", "question", "answer"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, url, qtype, question, answer])


def already_seen_urls() -> set[str]:
    """Every URL ever logged - the bot never opens the same link twice."""
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
    # Trailing "s?" so a keyword also matches its plural: "llm" hits "LLMs",
    # "embedding" hits "embeddings", "api" hits "APIs". Without it the
    # trailing boundary rejects the plural outright and the job is skipped.
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


class NeedsAttention(Exception):
    """Raised at would-pause moments when sleep mode is on."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def attention(reason: str, prompt: str) -> None:
    """A pause that needs the user - unless sleep mode is on, in which case
    process_job catches NeedsAttention and parks the job instead."""
    if config.sleep_mode:
        raise NeedsAttention(reason)
    input(prompt)


def canned_answer_for(question: str) -> str | None:
    for pattern, answer in config.canned_answers.items():
        if re.search(pattern, question, re.IGNORECASE):
            return answer
    return None


# ---------------------------------------------------------------- collection

JOB_LINK_RE = re.compile(r"/job-listings-")


def collect_listing_links(driver) -> list[str]:
    links = []
    for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/job-listings-']"):
        href = (a.get_attribute("href") or "").split("?")[0]
        if JOB_LINK_RE.search(href) and href not in links:
            links.append(href)
    return links


def go_to_next_page(driver) -> bool:
    """Naukri paginates with a Next link/button at the bottom of the results."""
    for el in driver.find_elements(By.CSS_SELECTOR, "a, button"):
        try:
            # STRICT match: letters-only text must be exactly "next" — otherwise
            # job titles like "Next.js Developer" get clicked (in new tabs, forever)
            text = re.sub(r"[^a-z]", "", (el.text or "").strip().lower())
            if not visible(el) or text != "next":
                continue
            if (el.get_attribute("href") or "") and "/job-listings-" in (el.get_attribute("href") or ""):
                continue  # never a job link
            if el.get_attribute("disabled") is not None:
                return False
            klass = el.get_attribute("class") or ""
            if "disabled" in klass:
                return False
            click(driver, el)
            time.sleep(config.action_delay + 1)
            return True
        except Exception:
            continue
    return False


def gather_links(driver) -> list[str]:
    print("Collecting job links from results pages...")
    results_tab = driver.current_window_handle
    all_links: list[str] = []
    stale_rounds = 0
    while True:
        before = len(all_links)
        all_links.extend(l for l in collect_listing_links(driver) if l not in all_links)
        print(f"   ...{len(all_links)} job links so far")
        # close any stray tabs a mis-click may have opened
        for handle in driver.window_handles:
            if handle != results_tab:
                driver.switch_to.window(handle)
                driver.close()
        driver.switch_to.window(results_tab)
        # guard: if two "next" clicks in a row produced no new links, stop
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

    kept = []
    for l in all_links:
        word = url_excluded(l)
        if word:
            log_result(l, "", f"skipped - excluded title word '{word}' (from url)")
            print(f"⏭️  Excluded without opening ('{word}'): {l.rsplit('/', 1)[-1][:70]}")
        else:
            kept.append(l)
    print(f"{len(kept)} left after removing already-seen and excluded ones.\n")
    return kept


# ---------------------------------------------------------------- applying

def find_apply_button(driver):
    """Apply button on a Naukri job page.
    Returns (element, 'apply'|'applied'|'external'|'not_found')."""
    try:
        el = driver.find_element(By.CSS_SELECTOR, "#apply-button")
        if visible(el):
            return el, "apply"
    except NoSuchElementException:
        pass
    for el in driver.find_elements(By.CSS_SELECTOR, "button, a"):
        if not visible(el):
            continue
        text = (el.text or "").strip().lower()
        if text == "applied":
            return el, "applied"
        if "company site" in text and "apply" in text:
            return el, "external"
        if text in ("apply", "i am interested", "apply now"):
            return el, "apply"
    return None, "not_found"


def get_company(driver) -> str:
    for sel in ("[class*='comp-name'] a", "[class*='comp-name']",
                "[class*='jd-header'] a[href*='careers']", "[class*='companyInfo'] a"):
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            text = (el.text or "").strip().split("\n")[0]
            if text and len(text) < 80:
                return text
    return ""


def save_job_to_sheet(path: str, driver, url: str, title: str, jd: str,
                      reason: str = "") -> None:
    """Park a job in a spreadsheet (question / external / sleep) for later."""
    append_csv(path,
               ["timestamp", "title", "company", "url", "reason", "jd"],
               [time.strftime("%Y-%m-%d %H:%M:%S"), title, get_company(driver),
                url, reason, " ".join(jd.split())[:3000]])


# ---- the apply chatbot drawer (the side question area) ----

DRAWER_SEL = "[class*='chatbot_Drawer'], [class*='chatbot_drawer'], [class*='_chatBot']"


def find_drawer(driver):
    for el in driver.find_elements(By.CSS_SELECTOR, DRAWER_SEL):
        if visible(el):
            return el
    return None


def drawer_question(drawer) -> str:
    """Latest bot message = the current question."""
    msgs = drawer.find_elements(By.CSS_SELECTOR, "[class*='botMsg'], [class*='botItem'], li, p")
    for el in reversed(msgs):
        text = (el.text or "").strip()
        if text and len(text) > 3:
            return text[:300]
    return (drawer.text or "").strip()[:300]


def answer_in_drawer(driver, drawer, answer: str) -> bool:
    """Try to place `answer` into the drawer's current input and send it."""
    # 1) radio / chip options: pick the one whose label matches the answer
    options = [el for el in drawer.find_elements(
        By.CSS_SELECTOR, "label, [class*='chip'], [class*='Chip']") if visible(el)]
    for opt in options:
        if answer.lower() in (opt.text or "").strip().lower():
            click(driver, opt)
            break
    else:
        # 2) free-text input (contenteditable div or input/textarea)
        box = None
        for sel in ("[contenteditable='true']", "input[type='text']", "textarea", "input:not([type])"):
            for el in drawer.find_elements(By.CSS_SELECTOR, sel):
                if visible(el):
                    box = el
                    break
            if box is not None:
                break
        if box is None:
            return False
        click(driver, box)
        if box.tag_name in ("input", "textarea"):
            box.clear()
            box.send_keys(answer)
        else:
            driver.execute_script(
                "arguments[0].innerText = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                box, answer)
        time.sleep(0.5)

    # send: the drawer's send/save button
    for el in drawer.find_elements(By.CSS_SELECTOR, "[class*='sendMsg'], [class*='send'], button"):
        text = (el.text or "").strip().lower()
        if visible(el) and (("send" in (el.get_attribute("class") or "").lower()) or text in ("save", "send", "submit", "")):
            click(driver, el)
            time.sleep(1)
            return True
    return False


def handle_chatbot(driver, url: str, title: str, timeout: int = 120) -> None:
    """Answer drawer questions until the drawer closes (max ~15 rounds)."""
    last_question = ""
    for _ in range(15):
        drawer = find_drawer(driver)
        if drawer is None:
            return  # drawer closed - done
        question = drawer_question(drawer)
        if question == last_question:
            time.sleep(1.5)
            drawer = find_drawer(driver)
            if drawer is None:
                return
            question = drawer_question(drawer)
            if question == last_question:
                # not progressing - needs the human
                log_question(url, title, "chatbot", question, "[stuck]")
                notify("Naukri Bot", f"Chatbot question on: {title}. Answer it in the browser!")
                attention("chatbot stuck",
                          f"⚠️  Chatbot needs you ('{question[:80]}...'). Answer in the browser, "
                          "then press ENTER/Continue... ")
                last_question = ""
                continue
        last_question = question

        answer = canned_answer_for(question)
        if answer and answer_in_drawer(driver, drawer, answer):
            log_question(url, title, "chatbot", question, f"[auto] {answer[:60]}")
            print(f"✍️  Chatbot: '{question[:60]}...' → {answer[:40]}")
        else:
            log_question(url, title, "chatbot", question, "[manual]")
            notify("Naukri Bot", f"Chatbot question on: {title}. Answer it in the browser!")
            print(f"⚠️  Unknown chatbot question: {question[:100]}")
            attention(f"unknown question: {question[:80]}",
                      "Answer it in the browser, then press ENTER/Continue... ")
        time.sleep(config.action_delay)


def applied_successfully(driver) -> bool:
    body = ""
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        pass
    return "successfully applied" in body or "application sent" in body or \
        any(visible(el) and (el.text or "").strip().lower() == "applied"
            for el in driver.find_elements(By.CSS_SELECTOR, "button, #already-applied"))


def _process_job_inner(driver, url: str, ctx: dict) -> str:
    driver.get(url)
    time.sleep(config.action_delay + 1)

    try:
        h1 = driver.find_element(By.CSS_SELECTOR, "h1")
        title = h1.text.strip() if h1 is not None else ""
    except Exception:
        title = ""
    if not title:
        title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
    ctx["title"] = title

    bad_word = title_excluded(title)
    if bad_word:
        log_result(url, title, f"skipped - excluded title word '{bad_word}'")
        print(f"⏭️  Excluded ('{bad_word}' in title): {title}")
        return "skipped"

    jd = driver.find_element(By.TAG_NAME, "body").text
    ctx["jd"] = jd
    if not description_matches(jd):
        log_result(url, title, "skipped - no keyword match")
        print(f"⏭️  No keyword match: {title}")
        return "skipped"

    btn, state = find_apply_button(driver)
    if state == "applied":
        log_result(url, title, "skipped - already applied")
        print(f"⏭️  Already applied: {title}")
        return "skipped"
    if state == "external":
        save_job_to_sheet(config.external_jobs_path, driver, url, title, jd)
        log_result(url, title, "skipped - apply on company site")
        print(f"📋 External application — saved to spreadsheet: {title}")
        return "skipped"
    if btn is None:
        log_result(url, title, "failed - apply button not found")
        print(f"❌ Apply button not found: {title}")
        return "skipped"

    click(driver, btn)
    time.sleep(config.action_delay + 1)

    # the side question drawer appears for some jobs - handle it if so
    if find_drawer(driver) is not None and config.easy_apply_only:
        save_job_to_sheet(config.question_jobs_path, driver, url, title, jd)
        log_result(url, title, "skipped - has questions (easy apply only)")
        print(f"📋 Has questions — saved to spreadsheet, moving on: {title}")
        return "skipped"
    handle_chatbot(driver, url, title)

    # confirm
    end = time.time() + 10
    while time.time() < end:
        if applied_successfully(driver):
            log_result(url, title, "applied")
            print(f"✅ applied: {title}")
            return "applied"
        if find_drawer(driver) is not None:
            if config.easy_apply_only:
                save_job_to_sheet(config.question_jobs_path, driver, url, title, jd)
                log_result(url, title, "skipped - has questions (easy apply only)")
                print(f"📋 Has questions — saved to spreadsheet, moving on: {title}")
                return "skipped"
            handle_chatbot(driver, url, title)
        time.sleep(1)

    notify("Naukri Bot", f"Couldn't confirm submission: {title}")
    attention("unconfirmed submission",
              "Couldn't confirm the application went through. Check the browser, finish "
              "if needed, then press ENTER/Continue... ")
    log_result(url, title, "applied (manual check)")
    print(f"✅ applied (manual check): {title}")
    return "applied"


def process_job(driver, url: str) -> str:
    """Wraps the job flow so sleep mode can park attention-needing jobs."""
    ctx: dict = {}
    try:
        return _process_job_inner(driver, url, ctx)
    except NeedsAttention as e:
        title = ctx.get("title", url)
        save_job_to_sheet(config.sleep_jobs_path, driver, url, title, ctx.get("jd", ""),
                          reason=e.reason)
        log_result(url, title, f"skipped - needs attention ({e.reason}) [sleep mode]")
        print(f"😴 Needs attention ({e.reason}) — saved to sleep list, moving on: {title}")
        return "skipped"


# ---------------------------------------------------------------- main loop

# Markers from the shipped config.py files. If any of these survive into a run
# they get typed into real applications sent to real companies.
PLACEHOLDER_MARKERS = (
    "REPLACE ME", "YOUR-PORTFOLIO", "YOUR-USERNAME", "YOUR CITY",
    "YOUR PHONE", "YOUR-PROFILE", "YOUR STATE",
)


def check_config() -> None:
    """Refuse to start while config.py still holds placeholder answers."""
    problems = []
    for name in ("cover_letter", "interest_answer"):
        value = getattr(config, name, "") or ""
        if any(m in value for m in PLACEHOLDER_MARKERS):
            problems.append(f"config.{name} is still the shipped placeholder")

    for pattern, answer in (getattr(config, "canned_answers", None) or {}).items():
        if isinstance(answer, str) and any(m in answer for m in PLACEHOLDER_MARKERS):
            problems.append(f"canned answer for /{pattern[:38]}/ is still a placeholder")

    if problems:
        raise RuntimeError(
            "Edit config.py before running - the following would be sent to "
            "employers as-is:\n  - " + "\n  - ".join(problems)
        )

    if not getattr(config, "keywords", None):
        print("\u26a0\ufe0f  config.keywords is empty - EVERY job your search returns "
              "will be treated as a match.")


def apply_loop(driver, all_links: list[str]) -> int:
    check_config()
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
            for handle in driver.window_handles:
                if handle != results_tab:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(results_tab)
        hooks.on_progress(i, total, applied)
        if config.batch_size and applied - batch_mark >= config.batch_size:
            batch_mark = applied
            notify("Naukri Bot", f"Batch done — {applied} applied. Continue?")
            input(f"🎯 Batch complete — {applied} applied so far, {total - i} jobs left. "
                  f"Press ENTER/Continue for the next {config.batch_size}... ")
        time.sleep(config.action_delay)

    print(f"\nDone. Applied to {applied} listings this run.")
    print(f"History: {config.log_csv_path}")
    return applied


def main():
    driver, wait, actions = create_session()
    driver.get("https://www.naukri.com/")

    input(
        "\nLog in to Naukri and run your job search (keyword, experience, filters),\n"
        "then press ENTER to start applying... "
    )

    all_links = gather_links(driver)
    apply_loop(driver, all_links)
    input("Press ENTER to close the browser... ")
    driver.quit()


if __name__ == "__main__":
    main()
