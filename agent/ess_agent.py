#!/usr/bin/env python3
"""
ESS AI Workflow Agent - live demo of the ESS AI Framework for Vibe Coders.

  Ticket -> Understand -> Plan -> Developer approval -> Reproduce (red) -> Fix (green)
         -> Developer REVIEWS the diff -> Git commit -> Ticket update (In Review)

Modes
  --mode offline   scripted playbook (default; no API key, never fails in a meeting)
  --mode ai        real model call (needs `pip install anthropic` + ANTHROPIC_API_KEY)

Run:  python agent/ess_agent.py            (asks approval before changing code AND before committing)
      python agent/ess_agent.py --yes      (auto-approve both gates)
      python agent/ess_agent.py --fast     (no demo pauses)
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offline_playbook import PLAYBOOKS  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass
if os.name == "nt":  # enable ANSI colours in the Windows terminal
    os.system("")

ROOT = Path(__file__).resolve().parent.parent
JIRA = os.environ.get("JIRA_LITE_URL", "http://127.0.0.1:5055")
APP_URL = os.environ.get("USER_APP_URL", "http://127.0.0.1:5070")
MODEL = os.environ.get("ESS_MODEL", "claude-sonnet-5-5")
AGENT_NAME = "ESS AI Agent"
SPEED = 1.0


# ----------------------------------------------------------------------------- UI helpers
def paint(code, s):
    return f"\033[{code}m{s}\033[0m"


bold = lambda s: paint("1", s)        # noqa: E731
dim = lambda s: paint("2", s)         # noqa: E731
red = lambda s: paint("91", s)        # noqa: E731
green = lambda s: paint("92", s)      # noqa: E731
yellow = lambda s: paint("93", s)     # noqa: E731
blue = lambda s: paint("94", s)       # noqa: E731
cyan = lambda s: paint("96", s)       # noqa: E731


def pause(sec=0.8):
    time.sleep(sec * SPEED)


def banner(n, total, title, stage):
    print()
    print(cyan("━" * 80))
    print(f"{bold(cyan(f'STEP {n}/{total}'))}  {bold(title)}   {dim('· framework: ' + stage)}")
    print(cyan("━" * 80))
    pause(0.6)


def say(msg):
    print(f"  {blue('ESS AI ▸')} {msg}")
    pause(0.5)


def ok(msg):
    print(f"  {green('✔')} {msg}")


def warn(msg):
    print(f"  {yellow('!')} {msg}")


def fail(msg, code=1):
    print(f"\n  {red('✘')} {msg}\n")
    sys.exit(code)


def wrap(text, indent="    ", width=76):
    return textwrap.fill(str(text), width=width, initial_indent=indent, subsequent_indent=indent)


def bullets(items, mark="•", indent="    "):
    for it in items:
        print(textwrap.fill(str(it), width=76, initial_indent=f"{indent}{mark} ", subsequent_indent=indent + "  "))


# ----------------------------------------------------------------------------- tracker client
def api(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(JIRA + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def comment(tid, body):
    api("POST", f"/api/tickets/{tid}/comments", {"author": AGENT_NAME, "body": body})


def pick_ticket(tid):
    if tid:
        return api("GET", f"/api/tickets/{tid}")
    order = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3}
    bugs = [t for t in api("GET", "/api/tickets") if t["type"] == "Bug" and t["status"] == "To Do"]
    if not bugs:
        fail("No open bugs in 'To Do'. Run  python reset_demo.py  to reset the demo.")
    return sorted(bugs, key=lambda t: order.get(t["priority"], 9))[0]


def show_ticket(t):
    print(f"  {bold(cyan(t['id']))}  {red(t['type'])} · {yellow(t['priority'])}   {bold(t['title'])}")
    print(f"  {dim('Reporter: ' + t['reporter'] + '   Component: ' + t.get('component', '-'))}")
    print(f"\n  {bold('Description')}\n{wrap(t['description'])}")
    if t.get("steps"):
        print(f"\n  {bold('Steps to reproduce')}")
        bullets(t["steps"], mark="→")
    print(f"\n  {bold('Expected')}  {t['expected']}")
    print(f"  {bold('Actual')}    {t['actual']}")
    print(f"\n  {bold('Acceptance criteria')}")
    bullets(t["acceptance_criteria"], mark="☐")


# ----------------------------------------------------------------------------- code + tests + git
def read_sources():
    out = {}
    for folder in ("app", "tests"):
        for p in sorted((ROOT / folder).rglob("*.py")):
            text = p.read_text(encoding="utf-8")
            if text.strip():
                out[p.relative_to(ROOT).as_posix()] = text
    return out


def func_range(text, name):
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, node.end_lineno
    return None


def show_code(rel, text, focus=None):
    print(f"  {bold(rel)}")
    for i, line in enumerate(text.splitlines(), 1):
        hot = focus and focus[0] <= i <= focus[1]
        num = f"{i:>3} │ "
        print("   " + (yellow(num + line) if hot else dim(num) + line))
    print()


def run_tests():
    """Run the whole suite. Returns (passed?, output, one-line summary)."""
    p = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    out = (p.stdout + p.stderr).strip()
    ran = re.search(r"Ran (\d+) tests?", out)
    n = int(ran.group(1)) if ran else 0
    if p.returncode == 0:
        summary = f"{n} tests passed"
    else:
        bad = re.search(r"FAILED \((.*?)\)", out)
        summary = f"{n} tests run, FAILED ({bad.group(1) if bad else 'errors'})"
    return p.returncode == 0, out, summary


TEST_LINE = re.compile(r"^(\w+) \([\w.]+\) \.\.\. (ok|FAIL|ERROR)$")


def failure_reasons(out):
    """One line per failing test: the last line of its traceback (e.g. 'AssertionError: 3 != 3.5')."""
    body = out.rsplit("\n" + "-" * 70 + "\nRan ", 1)[0]
    reasons = []
    for block in re.split(r"\n={20,}\n", "\n" + body):
        block = block.strip()
        m = re.match(r"(?:FAIL|ERROR): (\w+) \(", block)
        if m:
            lines = [l for l in block.splitlines() if l.strip()]
            msg = next((l for l in lines if re.match(r"^[A-Za-z_.]*(Error|Exception)\b", l.strip())), lines[-1])
            reasons.append((m.group(1), msg.strip()))
    return reasons


def show_test_output(out):
    """Compact view: one line per test, then the reason for every failure."""
    for line in out.splitlines():
        m = TEST_LINE.match(line.strip())
        if m:
            name, status = m.group(1), m.group(2)
            colour = green if status == "ok" else red
            print(f"    {colour('✔' if status == 'ok' else '✘')} {name:<58} {colour(status)}")
    for name, why in failure_reasons(out):
        print(f"      {dim('↳ ' + name + ':')} {yellow(why)}")


def git(*args, check=True, input_text=None):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", input=input_text)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout.strip()


def ensure_git_identity():
    if not git("config", "user.name", check=False):
        git("config", "user.name", "ESS AI Agent")
    if not git("config", "user.email", check=False):
        git("config", "user.email", "ess-ai-agent@example.com")


def ensure_main():
    """Every ticket gets its own branch cut from main, so fixes never stack on each other."""
    if git("rev-parse", "--abbrev-ref", "HEAD", check=False) != "main":
        try:
            git("checkout", "main")
        except RuntimeError as e:
            fail(f"Could not switch to main ({e}). Commit or stash your changes, or run  python reset_demo.py")


def discard_changes(branch, paths):
    """Developer rejected the change: undo ONLY the files the agent wrote (never your own edits)."""
    git("reset", "-q", "--", *paths, check=False)
    for rel in paths:
        if git("ls-files", "--error-unmatch", rel, check=False):  # tracked -> restore from git
            git("checkout", "-q", "--", rel, check=False)
        elif (ROOT / rel).exists():                                 # new file the agent created
            (ROOT / rel).unlink()
    git("checkout", "-q", "main", check=False)
    git("branch", "-D", branch, check=False)


def safe_path(rel):
    rel = rel.replace("\\", "/")
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or p.parts[0] not in ("app", "tests") or p.suffix != ".py":
        raise ValueError(f"Refusing to write outside app/ or tests/ (or non-.py): {rel}")
    return ROOT / p


def materialize(f):
    """Full new text of a file entry: either complete `content`, or small `replace` patches
    ({"old": ..., "new": ...}) applied to the file as it is on disk right now."""
    if "content" in f:
        return f["content"]
    text = safe_path(f["path"]).read_text(encoding="utf-8")
    for r in f["replace"]:
        if text.count(r["old"]) != 1:
            raise RuntimeError(f"Patch for {f['path']} does not apply cleanly - did the file change? "
                               f"Run  python reset_demo.py  and try again.")
        text = text.replace(r["old"], r["new"])
    return text


def write_files(files):
    for f in files:
        path = safe_path(f["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(materialize(f), encoding="utf-8", newline="\n")
        ok(f"wrote {bold(f['path'])}")


def slug(text, n=5):
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "-".join(words)[:40]


# ----------------------------------------------------------------------------- AI mode
AI_SYSTEM = """You are the ESS AI engineering agent. Follow the ESS AI Framework rules:
- Understand the existing code first. Do not redesign or refactor.
- Make the smallest safe change that satisfies the ticket's acceptance criteria.
- Add ONE regression test file named tests/test_<ticket id lowercased, '-' replaced by '_'>.py (unittest style)
  that fails before the fix and passes after it.
- Only create or modify .py files under app/ and tests/. Never touch anything else.
- Do not invent business rules. List anything unclear under "unknowns".
- Reply with ONE JSON object and nothing else, using exactly this schema:
{"analysis": {"root_cause": str, "evidence": [str], "unknowns": [str]},
 "plan": [str],
 "files": [{"path": str, "content": str}],   // COMPLETE file contents, not diffs
 "branch_slug": str,                          // 2-4 lowercase words joined by '-', e.g. "divide-decimal-and-zero"
 "commit_title": str,                         // imperative, <= 70 chars, without the ticket id
 "summary": [str]}                            // 2-4 short bullets for the commit body
"""


def solve_ai(ticket, sources, baseline_out, previous_failure=None):
    try:
        import anthropic
    except ImportError:
        fail("AI mode needs the SDK:  pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        fail("Set ANTHROPIC_API_KEY (use an ESS-approved, company-managed key).")
    code = "\n\n".join(f"### {p}\n```python\n{t}\n```" for p, t in sources.items())
    user = f"TICKET:\n{json.dumps(ticket, indent=2, ensure_ascii=False)}\n\nCODE:\n{code}\n\nBASELINE TEST RUN:\n{baseline_out}\n"
    if previous_failure:
        user += f"\nYOUR PREVIOUS ATTEMPT FAILED THE TESTS. Fix it. Failure output:\n{previous_failure}\n"
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=6000, system=AI_SYSTEM,
                                 messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        fail("The model did not return JSON.")
    result = json.loads(m.group(0))
    result.setdefault("focus", None)
    return result


def solve_offline(ticket):
    pb = PLAYBOOKS.get(ticket["id"])
    if not pb:
        fail(f"Offline mode only has a playbook for {', '.join(PLAYBOOKS)}. Use --mode ai for {ticket['id']}.")
    return pb


# ----------------------------------------------------------------------------- main workflow
def main():
    global SPEED
    ap = argparse.ArgumentParser(description="ESS AI workflow demo agent")
    ap.add_argument("--mode", choices=["offline", "ai"], default="offline")
    ap.add_argument("--ticket", help="ticket id (default: highest-priority open bug)")
    ap.add_argument("--yes", action="store_true", help="auto-approve the plan")
    ap.add_argument("--fast", action="store_true", help="no demo pauses")
    args = ap.parse_args()
    SPEED = 0 if args.fast else 1.0
    started = time.time()
    TOTAL = 8

    if not (ROOT / ".git").exists():
        fail("No git repo yet. Run  python reset_demo.py  first.")
    ensure_main()
    try:
        api("GET", "/api/tickets")
    except (urllib.error.URLError, ConnectionError):
        fail(f"Cannot reach the tracker at {JIRA}. Start it:  python jira_lite/server.py")

    print()
    print(bold(cyan("  ESS  AI  FRAMEWORK  ·  LIVE  WORKFLOW  DEMO")))
    print(dim(f"  mode: {args.mode}" + ("  (scripted playbook - no API call)" if args.mode == "offline" else f"  (model: {MODEL})")))

    # ---- 1. read the ticket --------------------------------------------------------------
    banner(1, TOTAL, "Read the bug from the tracker", "Requirement")
    ticket = pick_ticket(args.ticket)
    tid = ticket["id"]
    say(f"Picked the highest-priority open bug: {bold(tid)}")
    print()
    show_ticket(ticket)
    api("PATCH", f"/api/tickets/{tid}", {"status": "In Progress", "assignee": AGENT_NAME})
    comment(tid, "Picked up by the ESS AI Agent. Reading the code and preparing a plan - no code changed yet.")
    print()
    ok(f"{tid} moved to {bold('In Progress')} on the board")

    # ---- 2. understand the code ----------------------------------------------------------
    banner(2, TOTAL, "Read and understand the existing code", "Understand")
    sources = read_sources()
    say("Reading the project before changing anything...")
    focus_info = PLAYBOOKS.get(tid, {}).get("focus") if args.mode == "offline" else None
    for rel, text in sources.items():
        if rel.startswith("app/"):
            focus = None
            if focus_info and rel != focus_info[0]:
                print(f"  {bold(rel)}  {dim(f'({len(text.splitlines())} lines read - not related to this bug)')}\n")
                continue
            if focus_info:
                focus = func_range(text, focus_info[1])
            show_code(rel, text, focus)
    say("Running the existing tests to get a baseline...")
    base_ok, base_out, base_sum = run_tests()
    show_test_output(base_out)
    print()
    (ok if base_ok else warn)(f"Baseline: {bold(base_sum)}")
    if base_ok:
        say("All green - but none of these tests cover the scenario in the ticket.")

    # ---- 3. analyse + plan + approval ----------------------------------------------------
    banner(3, TOTAL, "Analyse the bug and propose a plan", "Plan → Developer approval")
    say("Analysing..." if args.mode == "offline" else f"Asking {MODEL} to analyse the ticket and code...")
    solution = solve_offline(ticket) if args.mode == "offline" else solve_ai(ticket, sources, base_out)
    if args.mode == "offline":
        pause(1.2)
    a = solution["analysis"]
    print(f"\n  {bold('Root cause')}\n{wrap(a['root_cause'])}")
    print(f"\n  {bold('Evidence')}")
    bullets(a["evidence"])
    print(f"\n  {bold('UNKNOWNs')}")
    bullets(a.get("unknowns") or ["none identified"], mark="?")
    print(f"\n  {bold('Implementation plan')}")
    for i, step in enumerate(solution["plan"], 1):
        print(textwrap.fill(step, width=76, initial_indent=f"    {i}. ", subsequent_indent="       "))
    print(f"\n  {bold('Files to change')}")
    bullets([f["path"] for f in solution["files"]], mark="→")
    print()
    comment(tid, "Analysis ready.\nRoot cause: " + a["root_cause"] + "\nWaiting for developer approval before any code change.")

    if args.yes:
        ok("Plan auto-approved (--yes)")
    else:
        answer = input(f"  {bold(yellow('DEVELOPER APPROVAL'))}  Approve this plan and let the agent implement it? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            comment(tid, "Plan not approved by the developer. No code was changed.")
            api("PATCH", f"/api/tickets/{tid}", {"status": "To Do", "assignee": "Unassigned"})
            fail("Plan not approved. Nothing was changed.", code=0)
        ok("Plan approved by the developer")
    comment(tid, "Plan approved by the developer. Implementing now.")

    # ---- 4. reproduce (red) --------------------------------------------------------------
    banner(4, TOTAL, "Reproduce the bug with a failing regression test", "Test first")
    test_files = [f for f in solution["files"] if f["path"].startswith("tests/")]
    app_files = [f for f in solution["files"] if f["path"].startswith("app/")]
    other = [f for f in solution["files"] if f not in test_files + app_files]
    if other:
        fail(f"Refusing to write files outside app/ and tests/: {[f['path'] for f in other]}")
    write_files(test_files)
    say("Running the new tests against the UNFIXED code - they should fail...")
    red_ok, red_out, red_sum = run_tests()
    show_test_output(red_out)
    print()
    if red_ok:
        warn("The new tests already pass - they do not reproduce the bug. Review them before trusting this fix.")
    else:
        ok(f"Bug reproduced: {bold(red(red_sum))}")
        comment(tid, f"Bug reproduced with new regression tests (before the fix): {red_sum}")

    # ---- 5. fix (green) ------------------------------------------------------------------
    banner(5, TOTAL, "Implement the fix and run the tests", "Code → Test → Evidence")
    attempts = 3 if args.mode == "ai" else 1
    green_ok, green_out, green_sum = False, "", ""
    for attempt in range(1, attempts + 1):
        write_files(app_files)
        say("Running the full test suite...")
        green_ok, green_out, green_sum = run_tests()
        show_test_output(green_out)
        print()
        if green_ok:
            ok(f"All tests passing: {bold(green(green_sum))}")
            comment(tid, f"Fix applied. Full test suite is green: {green_sum}")
            break
        warn(f"Tests failed: {green_sum}")
        if attempt < attempts:
            say(f"Sending the failure back to the AI (attempt {attempt + 1}/{attempts}) - the feedback loop...")
            solution = solve_ai(ticket, read_sources(), base_out, previous_failure=green_out)
            test_files = [f for f in solution["files"] if f["path"].startswith("tests/")]
            app_files = [f for f in solution["files"] if f["path"].startswith("app/")]
            write_files(test_files)
    if not green_ok:
        comment(tid, "Fix attempt failed the tests. Leaving the change uncommitted for a developer to review.\n" + green_sum)
        fail("Tests are still failing - not committing. Check the output above.")

    # ---- 6. developer reviews the diff ---------------------------------------------------
    banner(6, TOTAL, "Review the changes before anything is committed", "Git diff → Developer review")
    ensure_git_identity()
    branch = f"fix/{tid}-{solution.get('branch_slug') or slug(solution['commit_title'], 4)}"
    git("checkout", "-B", branch)
    ok(f"on branch {bold(branch)}")
    paths = [f["path"] for f in solution["files"]]
    git("add", "--", *paths)  # only what the agent wrote - never unrelated edits of yours
    print(f"\n  {bold('Changed files')}")
    for line in git("diff", "--cached", "--stat", "--", *paths).splitlines():
        print("    " + line.strip())
    print(f"\n  {bold('Diff')}")
    for line in git("diff", "--cached", "--unified=3", "--", *[x for x in paths if x.startswith("app/")]).splitlines():
        if line.startswith(("diff ", "index ", "--- ", "+++ ")):
            continue
        colour = green if line.startswith("+") else red if line.startswith("-") else dim if line.startswith("@@") else (lambda s: s)
        print("    " + colour(line))
    print(f"\n  {dim('(new test files: ' + ', '.join(f['path'] for f in test_files) + ' - see the Source Control panel for the full diff)')}")
    print()
    full_diff = git("diff", "--cached", "--unified=3", "--", *paths)
    changes = {
        "branch": branch,
        "commit": "not committed yet",
        "tests": green_sum,
        "files": [f["path"] for f in solution["files"]],
        "diff": "\n".join(l for l in full_diff.splitlines() if not l.startswith("index "))[:20000],
    }
    api("PATCH", f"/api/tickets/{tid}", {"changes": changes})
    comment(tid, f"Fix is ready and tests are green ({green_sum}). Waiting for the developer to review the diff - nothing is committed yet.")
    say(f"The change is staged but NOT committed. Check the app at {APP_URL} and the diff above.")
    if args.yes:
        ok("Changes auto-approved (--yes)")
    else:
        answer = input(f"  {bold(yellow('REVIEW BEFORE COMMIT'))}  Looks good - commit these changes? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            discard_changes(branch, paths)
            comment(tid, "Changes rejected in review. Nothing was committed and the working tree was restored.")
            api("PATCH", f"/api/tickets/{tid}", {"status": "To Do", "assignee": "Unassigned", "changes": None})
            fail("Changes not approved. Nothing was committed; the code is back to the original.", code=0)
        ok("Changes approved by the developer")

    # ---- 7. commit -----------------------------------------------------------------------
    banner(7, TOTAL, "Commit to git", "Commit")
    body = "\n".join(f"- {s}" for s in solution["summary"])
    prepared = "offline playbook" if args.mode == "offline" else MODEL
    message = (f"{tid}: {solution['commit_title']}\n\n{body}\n\n"
               f"Tests: {green_sum} (unittest)\n"
               f"Prepared by the ESS AI Agent ({prepared}); reviewed by the developer before commit.\n")
    git("commit", "-F", "-", "--", *paths, input_text=message)
    sha = git("rev-parse", "--short", "HEAD")
    ok(f"Committed {bold(sha)}  {solution['commit_title']}")
    print()
    for line in git("log", "-1", "--format=%an <%ae>%n%ad", "--date=format:%Y-%m-%d %H:%M").splitlines():
        print("    " + dim(line))
    print()
    for line in message.splitlines():
        print("    " + line)

    # ---- 8. update the ticket ------------------------------------------------------------
    banner(8, TOTAL, "Update the ticket for human review", "PR → Review")
    files_changed = ", ".join(f["path"] for f in solution["files"])
    comment(tid, (f"Fix committed and ready for review.\n\nRoot cause: {a['root_cause']}\n\n"
                  f"Changed: {files_changed}\nTests: {green_sum}\nBranch: {branch}\nCommit: {sha}\n\n"
                  "AI prepared the change. A human reviewer approves the merge and release."))
    changes["commit"] = sha
    api("PATCH", f"/api/tickets/{tid}", {"status": "In Review", "changes": changes})
    ok(f"{tid} moved to {bold('In Review')} - open the card to see the diff, then Approve it")
    say("The AI prepares the change. A human approves the release.")

    elapsed = time.time() - started
    print()
    print(green("═" * 80))
    print(bold(green(f"  DONE  ·  {tid} fixed, tested ({green_sum}) and committed as {sha}  ·  {elapsed:0.0f}s")))
    print(green("═" * 80))
    print(dim("  Next: approve the card on the board, or open a Pull Request from branch " + branch + ".\n"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  interrupted")
        sys.exit(130)
