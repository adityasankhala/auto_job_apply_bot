"""
Internshala Auto Applier - Chrome session setup

Chrome 136+ blocks automation on your real default profile directory, so the
bot uses its own persistent profile at ~/.internshala_bot_profile. Log in to
Internshala once in that window and the session persists across runs.
"""

import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait

BOT_PROFILE_DIR = os.path.expanduser("~/.internshala_bot_profile")


def create_session():
    options = Options()
    options.add_argument(f"--user-data-dir={BOT_PROFILE_DIR}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    wait = WebDriverWait(driver, 10)
    actions = ActionChains(driver)
    return driver, wait, actions
