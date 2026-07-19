"""
ChatGPT-tab integration.

Enable with config.use_chatgpt = True, then — after clicking "Open Chrome" —
open a second tab in the bot's Chrome window, go to chatgpt.com, and open the
chat/project you want answers to come from. Leave that tab open; the bot
finds it by URL, never closes it, and reuses the same conversation so your
project's custom instructions/context apply to every answer.

Per job: switches to the ChatGPT tab, types the prompt (JD included) into the
composer, sends it, waits for the reply to finish streaming, reads the last
assistant message, and switches back to the job tab.
"""

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from wellfound_bot import config

COMPOSER = "#prompt-textarea"
ASSISTANT_MSG = "[data-message-author-role='assistant']"
STOP_BUTTON = "button[data-testid='stop-button']"


def _find_gpt_tab(driver) -> str | None:
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = ""
        try:
            url = driver.current_url or ""
        except Exception:
            continue
        if "chatgpt.com" in url or "chat.openai.com" in url:
            return handle
    return None


def _open_gpt_tab(driver) -> str:
    """Open config.chatgpt_url in a new tab and wait for the composer."""
    driver.switch_to.new_window("tab")
    driver.get(config.chatgpt_url)
    end = time.time() + 30
    while time.time() < end:
        if driver.find_elements(By.CSS_SELECTOR, COMPOSER):
            return driver.current_window_handle
        time.sleep(1)
    raise RuntimeError(
        "ChatGPT tab opened but no composer appeared — are you logged in to "
        "chatgpt.com in the bot's Chrome profile?")


def ask_gpt(driver, jd: str, timeout: int = 120) -> str | None:
    """Send the JD to the ChatGPT tab (opening it if needed), return the reply."""
    job_tab = driver.current_window_handle
    gpt_tab = _find_gpt_tab(driver)
    if gpt_tab is None:
        driver.switch_to.window(job_tab)
        gpt_tab = _open_gpt_tab(driver)

    try:
        driver.switch_to.window(gpt_tab)

        # remember the current last reply's text — message COUNT is unreliable
        # in long chats (ChatGPT virtualizes the thread), text identity is not
        prior = driver.find_elements(By.CSS_SELECTOR, ASSISTANT_MSG)
        prev_last = (prior[-1].text or "").strip() if prior else ""

        # newlines would send the message early; collapse all whitespace
        prompt = re.sub(r"\s+", " ", config.gpt_prompt.format(jd=jd[:8000])).strip()

        composer = driver.find_element(By.CSS_SELECTOR, COMPOSER)
        composer.click()
        time.sleep(0.3)
        composer.send_keys(prompt)
        time.sleep(0.5)
        composer.send_keys(Keys.ENTER)

        # wait for a new assistant message to appear and finish streaming
        end = time.time() + timeout
        last_text, stable = "", 0
        while time.time() < end:
            time.sleep(0.8)
            msgs = driver.find_elements(By.CSS_SELECTOR, ASSISTANT_MSG)
            if not msgs:
                continue
            text = (msgs[-1].text or "").strip()
            if text == prev_last:
                continue  # reply hasn't started rendering yet
            stable = stable + 1 if (text and text == last_text) else 0
            last_text = text
            if not text:
                continue
            streaming = any(el.is_displayed() for el in
                            driver.find_elements(By.CSS_SELECTOR, STOP_BUTTON))
            # normal path: streaming indicator gone + text stable for ~1.6s
            if not streaming and stable >= 2:
                return text
            # fallback: text unchanged for ~6s — accept even if the streaming
            # indicator is misbehaving (it sometimes never clears)
            if stable >= 8:
                return text
        return last_text or None
    finally:
        driver.switch_to.window(job_tab)
