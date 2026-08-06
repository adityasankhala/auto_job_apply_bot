"""
LinkedIn Auto Applier - Tkinter UI

Run:  python3 -m linkedin_bot.app  

Flow: Open Chrome -> log in + set filters on linkedin.com -> Start Applying.
Pause/Resume works between jobs. When a form needs a manual answer, the
"I've answered — Continue" button lights up; answer in the browser, then click it.
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

from linkedin_bot import config
from linkedin_bot import main as bot
from linkedin_bot.browser import create_session

# palette (light mode)
BG = "#f4f5f7"
PANEL = "#ffffff"
FIELD = "#eef0f4"
FG = "#1f2430"
DIM = "#6b7280"
GREEN = "#15803d"
YELLOW = "#b45309"
RED = "#b91c1c"
BLUE = "#1d4ed8"


class UIHooks(bot.Hooks):
    def __init__(self, app: "App"):
        self.app = app

    def log(self, msg: str) -> None:
        self.app.q.put(("log", msg))

    def confirm(self, prompt: str) -> None:
        self.app.q.put(("confirm", prompt))
        self.app.continue_event.clear()
        self.app.continue_event.wait()

    def wait_if_paused(self) -> None:
        while self.app.paused:
            time.sleep(0.3)

    def on_progress(self, done: int, total: int, applied: int) -> None:
        self.app.q.put(("progress", (done, total, applied)))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.continue_event = threading.Event()
        self.paused = False
        self.driver = None

        bot.hooks = UIHooks(self)
        self._build()
        self.root.after(100, self._poll)

    # ---------------------------------------------------------------- UI

    def _build(self):
        r = self.root
        r.title("LinkedIn Auto Applier")
        r.geometry("860x640")
        r.configure(bg=BG)
        r.minsize(700, 500)

        header = tk.Frame(r, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(header, text="LinkedIn Auto Applier", bg=BG, fg=FG,
                 font=("Helvetica", 20, "bold")).pack(side="left")
        self.stats = tk.Label(header, text="processed 0/0  ·  applied 0", bg=BG,
                              fg=DIM, font=("Menlo", 12))
        self.stats.pack(side="right", pady=4)

        # buttons row
        btns = tk.Frame(r, bg=BG)
        btns.pack(fill="x", padx=16, pady=6)

        def mkbtn(text, cmd, color=FIELD, fg=FG):
            b = tk.Button(btns, text=text, command=cmd, bg=color, fg=fg,
                          activebackground=color, activeforeground=fg,
                          highlightbackground=BG, relief="flat",
                          font=("Helvetica", 13, "bold"), padx=14, pady=6)
            b.pack(side="left", padx=(0, 8))
            return b

        self.btn_chrome = mkbtn("1 · Open Chrome", self.open_chrome)
        self.btn_start = mkbtn("2 · Start Applying", self.start)
        self.btn_pause = mkbtn("⏸ Pause", self.toggle_pause)
        self.btn_continue = mkbtn("I've answered — Continue ▶", self.do_continue)
        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="disabled")
        self.btn_continue.config(state="disabled")

        tk.Label(btns, text="Batch:", bg=BG, fg=DIM,
                 font=("Helvetica", 12)).pack(side="left", padx=(12, 2))
        self.batch_entry = tk.Entry(btns, width=4, bg=FIELD, fg=FG, relief="flat",
                                    font=("Menlo", 12), insertbackground=FG,
                                    justify="center")
        self.batch_entry.insert(0, str(config.batch_size))
        self.batch_entry.pack(side="left")
        self.batch_entry.bind("<KeyRelease>", self._sync_batch)

        self.easy_var = tk.BooleanVar(value=config.easy_apply_only)
        tk.Checkbutton(btns, text="Easy apply only", variable=self.easy_var,
                       command=self._sync_easy, bg=BG, fg=FG, selectcolor=FIELD,
                       activebackground=BG, activeforeground=FG,
                       font=("Helvetica", 12)).pack(side="left", padx=(12, 0))

        # keyword boxes
        kw = tk.Frame(r, bg=PANEL)
        kw.pack(fill="x", padx=16, pady=6)
        tk.Label(kw, text="Must-have JD keywords (at least ONE must appear; empty = apply to all; live):",
                 bg=PANEL, fg=DIM, font=("Helvetica", 12)).pack(anchor="w", padx=10, pady=(8, 2))
        self.good_words = tk.Text(kw, height=3, bg=FIELD, fg=FG, insertbackground=FG,
                                  relief="flat", font=("Menlo", 12), wrap="word",
                                  padx=8, pady=6)
        self.good_words.pack(fill="x", padx=10, pady=(0, 6))
        self.good_words.insert("1.0", ", ".join(config.keywords))
        self.good_words.bind("<KeyRelease>", self._sync_good_words)

        tk.Label(kw, text="Bad title words (any match in the title = skip; live):",
                 bg=PANEL, fg=DIM, font=("Helvetica", 12)).pack(anchor="w", padx=10, pady=(4, 2))
        self.bad_words = tk.Text(kw, height=3, bg=FIELD, fg=FG, insertbackground=FG,
                                 relief="flat", font=("Menlo", 12), wrap="word",
                                 padx=8, pady=6)
        self.bad_words.pack(fill="x", padx=10, pady=(0, 10))
        self.bad_words.insert("1.0", ", ".join(config.exclude_title_keywords))
        self.bad_words.bind("<KeyRelease>", self._sync_bad_words)

        # log pane
        self.logbox = scrolledtext.ScrolledText(
            r, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
            font=("Menlo", 12), state="disabled", padx=10, pady=8)
        self.logbox.pack(fill="both", expand=True, padx=16, pady=6)
        for tag, color in (("green", GREEN), ("yellow", YELLOW),
                           ("red", RED), ("blue", BLUE), ("dim", DIM)):
            self.logbox.tag_config(tag, foreground=color)

        self.status = tk.Label(r, text="Click “Open Chrome” to begin.", bg=BG, fg=DIM,
                               anchor="w", font=("Helvetica", 12))
        self.status.pack(fill="x", padx=16, pady=(0, 10))

        r.protocol("WM_DELETE_WINDOW", self._on_close)

    def _log(self, msg: str):
        tag = None
        if "✅" in msg or "✍️" in msg:
            tag = "green"
        elif "⏭" in msg or "skipped" in msg:
            tag = "dim"
        elif "⚠️" in msg:
            tag = "yellow"
        elif "❌" in msg or "error" in msg.lower():
            tag = "red"
        elif msg.strip().startswith("["):
            tag = "blue"
        self.logbox.config(state="normal")
        self.logbox.insert("end", msg.rstrip() + "\n", tag)
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    def _set_status(self, text, color=DIM):
        self.status.config(text=text, fg=color)

    # ---------------------------------------------------------------- actions

    def open_chrome(self):
        self.btn_chrome.config(state="disabled")
        self._set_status("Opening Chrome…")

        def work():
            try:
                driver, _, _ = create_session()
                driver.get("https://www.linkedin.com/jobs/")
                self.driver = driver
                self.q.put(("chrome_ready", None))
            except Exception as e:
                self.q.put(("chrome_failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def start(self):
        if not self.driver:
            return
        self._sync_bad_words()
        self._sync_good_words()
        self._sync_batch()
        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        self._set_status("Collecting listings…", BLUE)

        def work():
            try:
                links = bot.gather_links(self.driver)
                applied = bot.apply_loop(self.driver, links)
                self.q.put(("done", applied))
            except Exception as e:
                self.q.put(("run_failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.btn_pause.config(text="▶ Resume", fg=YELLOW)
            self._set_status("Paused — will stop before the next job.", YELLOW)
        else:
            self.btn_pause.config(text="⏸ Pause", fg=FG)
            self._set_status("Running…", GREEN)

    def do_continue(self):
        self.btn_continue.config(state="disabled", fg=FG)
        self._set_status("Running…", GREEN)
        self.continue_event.set()

    def _sync_bad_words(self, _event=None):
        words = [w.strip().lower() for w in
                 self.bad_words.get("1.0", "end").replace("\n", ",").split(",")]
        config.exclude_title_keywords = [w for w in words if w]

    def _sync_easy(self):
        config.easy_apply_only = self.easy_var.get()

    def _sync_batch(self, _event=None):
        try:
            config.batch_size = max(0, int(self.batch_entry.get().strip() or 0))
        except ValueError:
            config.batch_size = 0

    def _sync_good_words(self, _event=None):
        words = [w.strip().lower() for w in
                 self.good_words.get("1.0", "end").replace("\n", ",").split(",")]
        config.keywords = [w for w in words if w]

    # ---------------------------------------------------------------- queue pump

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._log(data)
                elif kind == "confirm":
                    self._log("⚠️  " + data.strip())
                    self.btn_continue.config(state="normal", fg=YELLOW)
                    self._set_status("Waiting for you — answer in the browser, "
                                     "then click “I've answered — Continue”.", YELLOW)
                    self.root.lift()
                elif kind == "progress":
                    done, total, applied = data
                    self.stats.config(
                        text=f"processed {done}/{total}  ·  left {total - done}  ·  applied {applied}")
                elif kind == "chrome_ready":
                    self.btn_start.config(state="normal")
                    self._set_status("Chrome is open — log in and set filters on "
                                     "linkedin.com, then click “Start Applying”.", GREEN)
                elif kind == "chrome_failed":
                    self.btn_chrome.config(state="normal")
                    self._log("❌ Chrome failed to open: " + data)
                    self._set_status("Chrome failed to open — see log.", RED)
                elif kind == "done":
                    self.btn_start.config(state="normal")
                    self.btn_pause.config(state="disabled")
                    self._set_status(f"Run complete — {data} applications submitted. "
                                     "You can change filters and start again.", GREEN)
                elif kind == "run_failed":
                    self.btn_start.config(state="normal")
                    self.btn_pause.config(state="disabled")
                    self._log("❌ Run failed: " + data)
                    self._set_status("Run failed — see log.", RED)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _on_close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
