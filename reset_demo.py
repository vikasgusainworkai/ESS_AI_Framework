#!/usr/bin/env python3
"""
Reset the demo to its starting state (run this before every demo):
  * restores the buggy app/user_service.py and removes the regression tests
  * resets the user list (data/users.json) and puts the tickets back on the board (ESS-201..203 in 'To Do')
  * creates the git repo with a baseline commit on `main` (first run) or switches back to it
"""
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent


def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p


if shutil.which("git") is None:
    sys.exit("git is not installed / not on PATH. Install Git for Windows from https://git-scm.com and retry.")

# 1) git: make sure we are on a clean `main`
if not (ROOT / ".git").exists():
    if git("init", "-b", "main", check=False).returncode != 0:  # older git
        git("init")
        git("checkout", "-b", "main")
    print("✔ created git repository")
else:
    # Discard uncommitted changes ONLY in app/ and tests/ - any edits you made elsewhere
    # (playbook, agent, server...) are kept.
    git("checkout", "HEAD", "--", "app", "tests", check=False)
    if git("checkout", "main", check=False).returncode != 0:
        sys.exit("Could not switch to main. Commit or stash your changes, then run this again.")
    branches = git("branch", "--list", "fix/*", check=False).stdout.split()
    for b in [x for x in branches if x != "*"]:
        git("branch", "-D", b, check=False)
    print("✔ switched back to main and removed old fix/* branches")

# 2) files: buggy app + no regression tests (+ clean up the old calculator demo if it is still around)
for legacy in ("app/calculator.py", "tests/test_calculator.py", "demo_assets/calculator_buggy.py"):
    if (ROOT / legacy).exists():
        (ROOT / legacy).unlink()
(ROOT / "app" / "user_service.py").write_text(
    (ROOT / "demo_assets" / "user_service_buggy.py").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
for f in (ROOT / "tests").glob("test_ess_*.py"):
    f.unlink()
print("✔ restored buggy app/user_service.py")

# 3) data + tickets: back to seed
shutil.copyfile(ROOT / "data" / "seed_users.json", ROOT / "data" / "users.json")
shutil.copyfile(ROOT / "jira_lite" / "seed_tickets.json", ROOT / "jira_lite" / "tickets.json")
print("✔ reset users (EMP1, EMP2, EMP3, EMP10, EMP11) and tickets (ESS-201, 202, 203 are in 'To Do')")

# 4) baseline commit
if not git("config", "user.name", check=False).stdout.strip():
    git("config", "user.name", "ESS Demo")
if not git("config", "user.email", check=False).stdout.strip():
    git("config", "user.email", "ess-demo@example.com")
git("add", "-A")
if git("diff", "--cached", "--quiet", check=False).returncode != 0:
    git("commit", "-m", "Baseline: ESS demo user management app")
    print("✔ baseline commit created")
print("\nReady.\n  terminal 1: python jira_lite/server.py   -> http://127.0.0.1:5055  (ticket board)"
      "\n  terminal 2: python app/server.py         -> http://127.0.0.1:5070  (the app with the bugs)"
      "\n  terminal 3: python agent/ess_agent.py    (the agent)")
