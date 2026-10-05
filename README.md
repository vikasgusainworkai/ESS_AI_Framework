# ESS AI Workflow Demo - User Management app

A live demo of an AI agent that **takes a ticket from a Jira-like board, fixes the bug, and asks a human to review before it commits**.

```
Ticket (To Do) -> read code -> plan -> developer approves plan -> failing test (red)
  -> fix -> passing tests (green) -> developer REVIEWS the diff -> git commit -> ticket "In Review" -> human approves -> Done
```

You watch it in three places at once:

| Window | URL / command | What you see |
|---|---|---|
| **Ticket board** | http://127.0.0.1:5055 | Card moves **To Do -> In Progress -> In Review -> Done**, agent comments appear live, and the card shows the exact diff the agent made |
| **The app (with bugs)** | http://127.0.0.1:5070 | User Management: EMPID, username, designation, **Edit / Delete** per row, **+** icon on top to add a user |
| **Terminal** | `python agent/ess_agent.py` | Every step the agent takes |

**Needs only Python 3.9+ and Git. Nothing to `pip install`.**

---

## Quick start (VS Code)

1. Open this folder in VS Code (**File -> Open Folder**), open a terminal (**Ctrl+`**). On Windows use `python` (or `py`).
2. Reset the demo (creates the git repo on first run):
   ```bash
   python reset_demo.py
   ```
3. Start the three things, each in its own terminal:
   ```bash
   python jira_lite/server.py      # terminal 1 -> board   http://127.0.0.1:5055
   python app/server.py            # terminal 2 -> the app http://127.0.0.1:5070
   python agent/ess_agent.py       # terminal 3 -> the agent
   ```
   (Or use **Run and Debug (Ctrl+Shift+D)**: `1. Reset demo`, `2. Start tracker`, `3. Start User Management app`, `4. Run ESS AI agent`.)
4. The agent pauses twice - type `y` + Enter at each:
   * **DEVELOPER APPROVAL** - approve the plan before any code changes
   * **REVIEW BEFORE COMMIT** - look at the diff, then approve the commit
5. After the run, **refresh the app** (no restart needed) - the bug is gone. On the board, open the card in *In Review* and click **Approve & mark Done**.

**Before every demo run:** `python reset_demo.py` (bugs, tickets, user list and git back to the start).

> The app uses port **5070** on purpose: Chrome and Edge refuse to open port 5060 (`ERR_UNSAFE_PORT`).

---

## The 3 bugs on the board

Run the agent three times - it picks the highest-priority open bug each time (or use `--ticket ESS-202`).

| Ticket | Priority | Bug a user sees | Where |
|---|---|---|---|
| **ESS-201** | Highest | Click **Delete** on `EMP1` -> `EMP10` and `EMP11` disappear too (delete matches by *prefix*, so data is lost) | `delete_user()` |
| **ESS-202** | High | Click **+** and add `EMP2` again -> a second `EMP2` row is created | `add_user()` |
| **ESS-203** | Medium | Click **+**, type spaces as username -> a blank row is saved; extra spaces are kept | `_validate()` |

Each fix is a few lines, lives on its own branch (`fix/ESS-20x-...`) cut from `main`, and the three branches merge together cleanly.

Try the bug yourself first (the **+** icon, then Delete on EMP1), then run the agent, then try again.

---

## Suggested talk track (about 4 minutes)

| Step on screen | What to say |
|---|---|
| **1 Read the bug** - card jumps to *In Progress* | "Work starts from a real ticket, not from a prompt." |
| **2 Understand the code** - baseline tests all green | "All 6 tests pass, yet customers see data loss - the tests don't cover it." |
| **3 Analyse & plan** - root cause, evidence, UNKNOWNs | "It explains what it found and flags what it doesn't know. Nothing changed yet." |
| **Approval #1** | "The developer approves the plan. AI never goes straight to code." |
| **4 Red** - new tests fail | "The bug is reproduced as a test *before* the fix." |
| **5 Green** - 9 tests pass | "Evidence, not claims: the real test run." |
| **6 Review** - 5-line diff, **REVIEW BEFORE COMMIT** | "Nothing is committed until a human has seen the diff." Open the card on the board: the same diff is there. |
| **7 Commit** - branch + commit message | "Small, reviewable change on a fix branch." |
| **8 In Review** -> click **Approve** | "AI prepares the change. A human approves the release." |

Say **n** at the review prompt to show the safety net: nothing is committed, the agent's files are removed, and the ticket goes back to *To Do*.

---

## Two modes

| | `--mode offline` (default) | `--mode ai` |
|---|---|---|
| Analysis + fix come from | A **scripted playbook** (`agent/offline_playbook.py`) for ESS-201/202/203 | A real model call - works for **any ticket**, including ones you create |
| Needs | Nothing | `pip install anthropic` and `ANTHROPIC_API_KEY` |
| Reliable for a live meeting | Yes - never fails | Depends on network / API |
| Ticket API, tests, git, review gate, board updates | **Real** | **Real** |

Be upfront in the meeting: in offline mode the *thinking* is pre-scripted; the board, test runs, git branch/commit and review gate are real.

```bash
pip install anthropic
set ANTHROPIC_API_KEY=your-key        # Windows cmd   (PowerShell: $env:ANTHROPIC_API_KEY="...")
python agent/ess_agent.py --mode ai
```
Use an **ESS-approved, company-managed key**. Override the model with `ESS_MODEL`. In AI mode, if tests fail the failure is sent back to the model (up to 3 attempts). The agent can only write `.py` files under `app/` and `tests/`, and it stages and commits **only the files it wrote** - your own uncommitted edits are never touched.

Other options: `--yes` (auto-approve both gates), `--fast` (no pauses), `--ticket ESS-202`.

### Create your own ticket live
Click **+ New ticket** on the board (title, type, priority, description, steps, expected/actual, acceptance criteria). Then run `python agent/ess_agent.py --mode ai --ticket ESS-204`. Offline mode only knows ESS-201/202/203 and will tell you so.

---

## What's in the box

```
reset_demo.py                restore the starting state (buggy code, users, tickets, git baseline)
app/user_service.py          the business logic - contains the 3 bugs
app/server.py                web server for the User Management app (reloads the service when the code changes)
app/static/index.html        the UI: table, + icon, Edit / Delete, add/edit dialog
data/seed_users.json         starting employees (EMP1, EMP2, EMP3, EMP10, EMP11)
jira_lite/server.py          tiny Jira-like tracker: live board, REST API, diff panel, Approve button
jira_lite/seed_tickets.json  the demo tickets
agent/ess_agent.py           the 8-step workflow agent
agent/offline_playbook.py    scripted analysis, regression tests and fix for each bug
tests/                       existing tests (green before any fix)
.vscode/launch.json          one-click run configs
```

Tracker API: `GET/POST /api/tickets`, `GET /api/tickets/ESS-201`, `PATCH /api/tickets/ESS-201 {"status":"Done"}`, `POST /api/tickets/ESS-201/comments {"author":"me","body":"hi"}`.
App API: `GET/POST /api/users`, `PUT/DELETE /api/users/<EMPID>`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot reach the tracker` | Start it: `python jira_lite/server.py`. |
| `No git repo yet` | Run `python reset_demo.py` once. |
| `git is not installed` | Install Git for Windows from git-scm.com, restart VS Code. |
| Board / app shows old data | `python reset_demo.py`, then refresh both pages. |
| Port 5055 or 5070 busy | Close the old terminal, or change `PORT` in the server file (and `JIRA_LITE_URL` / `USER_APP_URL`). Avoid 5060 - browsers block it. |
| `No open bugs in 'To Do'` | Run `python reset_demo.py`. |
| `Patch ... does not apply cleanly` | You edited `app/user_service.py`; run `python reset_demo.py`. |
| Switching to main failed | Commit or stash your own changes, or run `python reset_demo.py`. |
| Garbled symbols in terminal | Use VS Code's integrated terminal; the agent forces UTF-8 output. |

## Making it your own

* **A new scripted bug:** add a ticket to `jira_lite/seed_tickets.json`, then add an entry to `PLAYBOOKS` in `agent/offline_playbook.py` (analysis, plan, regression test file, and a small `replace` patch). Put the buggy code into `demo_assets/user_service_buggy.py` too so reset restores it.
* **Real tools later:** swap the tracker client `api()` in `ess_agent.py` for Jira / Azure DevOps REST calls and keep the rest of the flow. Add CI checks (lint, secret scan) as extra steps before the commit.
* **pytest instead of unittest:** change the command in `run_tests()`.
