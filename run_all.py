#!/usr/bin/env python3
"""
Auto Job Applier — Multi-Bot Orchestrator

Runs LinkedIn and/or Wellfound bots sequentially with proper pacing.
Designed for a daily routine of 100+ applications.

Usage:
    python3 run_all.py                    # run both bots sequentially
    python3 run_all.py --linkedin-only    # just LinkedIn
    python3 run_all.py --wellfound-only   # just Wellfound
    python3 run_all.py --summary          # just print today's stats
    python3 run_all.py --role ml          # LinkedIn with ML-focused search
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LINKEDIN_DIR = os.path.join(ROOT, "linkedin_autoapply")
WELLFOUND_DIR = os.path.join(ROOT, "wellfound_autoapply")

# Auto-detect the venv python
VENV_PYTHON = os.path.join(ROOT, ".venv", "bin", "python3")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable  # fallback to current python


def banner(text: str) -> None:
    width = 70
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n")


def run_bot(name: str, cwd: str, args: list[str]) -> int:
    """Run a bot subprocess and stream its output."""
    banner(f"🚀 Starting {name}")
    print(f"   Working dir: {cwd}")
    print(f"   Command: {VENV_PYTHON} {' '.join(args)}")
    print()

    try:
        result = subprocess.run(
            [VENV_PYTHON] + args,
            cwd=cwd,
            timeout=7200,  # 2 hour max per bot
        )
        if result.returncode == 0:
            print(f"\n✅ {name} finished successfully.")
        elif result.returncode == 2:
            print(f"\n⚠️  {name} aborted — not logged in. Run the GUI first to log in:")
            if "linkedin" in name.lower():
                print(f"   cd {cwd} && {VENV_PYTHON} -m linkedin_bot.app")
            else:
                print(f"   cd {cwd} && {VENV_PYTHON} -m wellfound_bot.app")
        else:
            print(f"\n⚠️  {name} exited with code {result.returncode}")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"\n⏰ {name} timed out after 2 hours.")
        return -1
    except FileNotFoundError:
        print(f"\n❌ Python not found at {VENV_PYTHON}")
        print("   Run: python3 -m venv .venv --system-site-packages && source .venv/bin/activate && pip install selenium")
        return -1
    except Exception as e:
        print(f"\n❌ {name} failed: {e}")
        return -1


def run_linkedin(role: str = "general", limit: int = 35) -> int:
    """Run LinkedIn autorun with specified role and limit."""
    args = [
        "-m", "linkedin_bot.autorun",
        "--role", role,
        "--limit", str(limit),
    ]
    return run_bot("LinkedIn Auto Applier", LINKEDIN_DIR, args)


def run_wellfound(limit: int = 50) -> int:
    """Run Wellfound in terminal mode."""
    args = ["-m", "wellfound_bot.main"]
    return run_bot("Wellfound Auto Applier", WELLFOUND_DIR, args)


def print_summary() -> None:
    """Print today's application summary from all CSV logs."""
    # Import here to avoid dependency issues
    sys.path.insert(0, ROOT)
    try:
        from daily_summary import generate_summary
        generate_summary()
    except ImportError:
        print("❌ daily_summary.py not found. Run from the project root.")
    except Exception as e:
        print(f"❌ Summary failed: {e}")


def main():
    ap = argparse.ArgumentParser(
        description="Auto Job Applier — run LinkedIn and/or Wellfound bots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_all.py                       Run both bots
  python3 run_all.py --linkedin-only       LinkedIn only
  python3 run_all.py --wellfound-only      Wellfound only
  python3 run_all.py --role ml --limit 20  LinkedIn ML jobs, max 20
  python3 run_all.py --summary             Today's stats only
        """
    )
    ap.add_argument("--linkedin-only", action="store_true",
                    help="Run only LinkedIn bot")
    ap.add_argument("--wellfound-only", action="store_true",
                    help="Run only Wellfound bot")
    ap.add_argument("--summary", action="store_true",
                    help="Just print today's application summary")
    ap.add_argument("--role", default="general",
                    choices=["general", "sde", "backend", "ml", "devops", "fullstack"],
                    help="LinkedIn search role theme (default: general)")
    ap.add_argument("--limit", type=int, default=35,
                    help="LinkedIn max applications per run (default: 35)")
    ap.add_argument("--wf-limit", type=int, default=50,
                    help="Wellfound max applications per run (default: 50)")
    args = ap.parse_args()

    if args.summary:
        print_summary()
        return

    banner("🎯 Auto Job Applier — Daily Run")
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Python: {VENV_PYTHON}")

    run_linkedin_flag = not args.wellfound_only
    run_wellfound_flag = not args.linkedin_only

    results = {}

    if run_linkedin_flag:
        results["LinkedIn"] = run_linkedin(args.role, args.limit)
        if run_wellfound_flag:
            print("\n⏳ Cooling down for 30 seconds before Wellfound...")
            time.sleep(30)

    if run_wellfound_flag:
        results["Wellfound"] = run_wellfound(args.wf_limit)

    # Final summary
    banner("📊 Run Complete")
    for name, code in results.items():
        status = "✅ OK" if code == 0 else f"⚠️  Exit code {code}"
        print(f"   {name}: {status}")

    print("\n   Running daily summary...")
    print_summary()


if __name__ == "__main__":
    main()
