"""
Offline playbook for the demo (no API key, no internet, never fails in a meeting).

These are SCRIPTED answers for tickets ESS-201, ESS-202 and ESS-203: the analysis, plan,
regression tests and fix are written in advance. `--mode ai` replaces this file with a real
model call and works for ANY ticket, including ones you create on the board.

A fix is a small patch ({"old": ..., "new": ...} applied to the current file) so each ticket
changes only its own lines of app/user_service.py.
"""

SERVICE = "app/user_service.py"

# ----------------------------------------------------------------------------- ESS-201: delete
TESTS_201 = '''"""Regression tests for ESS-201: delete must remove only the exact EMPID."""
import unittest

from app.user_service import UserService


class Ess201DeleteTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()
        for empid, name, role in [("EMP1", "asha", "Developer"), ("EMP10", "ravi", "Tester"), ("EMP11", "meena", "Manager")]:
            self.svc.add_user(empid, name, role)

    def test_delete_removes_only_the_exact_empid(self):
        self.svc.delete_user("EMP1")
        self.assertEqual([u["empid"] for u in self.svc.list_users()], ["EMP10", "EMP11"])

    def test_delete_returns_the_deleted_user(self):
        deleted = self.svc.delete_user("EMP10")
        self.assertEqual(deleted["username"], "ravi")
        self.assertEqual(len(self.svc.list_users()), 2)

    def test_unknown_empid_raises_and_removes_nobody(self):
        with self.assertRaises(KeyError):
            self.svc.delete_user("EMP")  # only the start of an id - not a real EMPID
        self.assertEqual(len(self.svc.list_users()), 3)


if __name__ == "__main__":
    unittest.main()
'''

OLD_DELETE = '''        matches = [u for u in self._users if u["empid"].startswith(empid)]
        if not matches:
            raise KeyError(f"User {empid} not found")
        self._users = [u for u in self._users if u not in matches]
        self._save()
        return dict(matches[0])
'''
NEW_DELETE = '''        user = self.get_user(empid)  # exact match; raises KeyError if unknown
        self._users.remove(user)
        self._save()
        return dict(user)
'''

# ----------------------------------------------------------------------------- ESS-202: duplicate EMPID
TESTS_202 = '''"""Regression tests for ESS-202: an EMPID can only be added once."""
import unittest

from app.user_service import UserService


class Ess202DuplicateEmpidTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.add_user("EMP2", "vikram", "QA Analyst")

    def test_adding_an_existing_empid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMP2 already exists"):
            self.svc.add_user("EMP2", "someone.else", "Developer")

    def test_list_is_unchanged_after_a_rejected_add(self):
        with self.assertRaises(ValueError):
            self.svc.add_user("EMP2", "someone.else", "Developer")
        self.assertEqual(self.svc.list_users(), [{"empid": "EMP2", "username": "vikram", "designation": "QA Analyst"}])

    def test_a_different_empid_can_still_be_added(self):
        self.svc.add_user("EMP3", "neha", "Product Manager")
        self.assertEqual(len(self.svc.list_users()), 2)


if __name__ == "__main__":
    unittest.main()
'''

OLD_ADD = '''        user = {"empid": empid, "username": username, "designation": designation}
'''
NEW_ADD = '''        if any(u["empid"] == empid for u in self._users):
            raise ValueError(f"EMPID {empid} already exists")
        user = {"empid": empid, "username": username, "designation": designation}
'''

# ----------------------------------------------------------------------------- ESS-203: validation
TESTS_203 = '''"""Regression tests for ESS-203: required fields and trimming when adding / editing a user."""
import unittest

from app.user_service import UserService


class Ess203ValidationTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()

    def test_blank_username_is_rejected(self):
        for bad in ("", "   ", None):
            with self.assertRaisesRegex(ValueError, "Username is required"):
                self.svc.add_user("EMP9", bad, "Developer")
        self.assertEqual(self.svc.list_users(), [])

    def test_blank_empid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMPID is required"):
            self.svc.add_user("  ", "asha", "Developer")

    def test_blank_designation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Designation is required"):
            self.svc.add_user("EMP9", "asha", "")

    def test_values_are_trimmed_before_saving(self):
        user = self.svc.add_user("  EMP9 ", "  asha  ", " Developer ")
        self.assertEqual(user, {"empid": "EMP9", "username": "asha", "designation": "Developer"})

    def test_editing_with_a_blank_username_is_rejected_and_keeps_old_data(self):
        self.svc.add_user("EMP9", "asha", "Developer")
        with self.assertRaisesRegex(ValueError, "Username is required"):
            self.svc.update_user("EMP9", "   ", "Tech Lead")
        self.assertEqual(self.svc.get_user("EMP9")["designation"], "Developer")


if __name__ == "__main__":
    unittest.main()
'''

OLD_VALIDATE = '''        if empid is None or username is None or designation is None:
            raise ValueError("All fields are required")
        return empid, username, designation
'''
NEW_VALIDATE = '''        cleaned = []
        for label, value in (("EMPID", empid), ("Username", username), ("Designation", designation)):
            text = "" if value is None else str(value).strip()
            if not text:
                raise ValueError(f"{label} is required")
            cleaned.append(text)
        return tuple(cleaned)
'''

PLAYBOOKS = {
    "ESS-201": {
        "focus": (SERVICE, "delete_user"),
        "analysis": {
            "root_cause": (
                "delete_user() selects rows with `empid.startswith(...)` instead of an exact match, "
                "then removes every selected row. Deleting EMP1 therefore also deletes EMP10 and EMP11. "
                "Every other method (get_user, update_user) already uses an exact match."
            ),
            "evidence": [
                "app/user_service.py: delete_user() builds `matches` with u['empid'].startswith(empid)",
                "All matches are removed: `self._users = [u for u in self._users if u not in matches]`",
                "Existing delete test only has one user (EMP1), so the prefix problem is never exercised",
            ],
            "unknowns": [
                "Should deleting a user also be recorded in an audit log? (not in the ticket - not changed)",
            ],
        },
        "plan": [
            "Add regression tests (tests/test_ess_201.py) with EMP1 / EMP10 / EMP11 and confirm they FAIL",
            "Change delete_user() to look the user up with get_user() (exact match) and remove only that one",
            "Keep the change inside delete_user(); add, edit and list stay untouched",
            "Run the full test suite and confirm existing + new tests pass",
            "Show the diff for developer review, then commit on a fix branch and move the ticket to In Review",
        ],
        "files": [
            {"path": "tests/test_ess_201.py", "content": TESTS_201},
            {"path": SERVICE, "replace": [{"old": OLD_DELETE, "new": NEW_DELETE}]},
        ],
        "branch_slug": "delete-exact-empid",
        "commit_title": "Delete only the user with the exact EMPID",
        "summary": [
            "delete_user() now uses an exact EMPID match (was startswith, which also removed EMP10 / EMP11)",
            "Unknown EMPID still raises KeyError and removes nobody",
            "Add regression tests in tests/test_ess_201.py",
        ],
    },
    "ESS-202": {
        "focus": (SERVICE, "add_user"),
        "analysis": {
            "root_cause": (
                "add_user() appends the new user without checking whether the EMPID is already in the list, "
                "so duplicates are created. get_user() returns the first match, which is why Edit and Delete "
                "then only ever touch the first of the duplicate rows."
            ),
            "evidence": [
                "app/user_service.py: add_user() goes straight from validation to `self._users.append(user)`",
                "get_user() returns the first row whose EMPID matches",
                "No existing test adds the same EMPID twice",
            ],
            "unknowns": [
                "Is EMPID case-sensitive? ('emp2' vs 'EMP2') - implemented as exact match, same as get_user()",
                "Should usernames be unique too? The ticket only talks about EMPID - not changed",
            ],
        },
        "plan": [
            "Add regression tests (tests/test_ess_202.py) that add EMP2 twice and confirm they FAIL",
            "In add_user(), raise ValueError('EMPID <id> already exists') before appending",
            "Keep the change inside add_user(); edit, delete and list stay untouched",
            "Run the full test suite and confirm existing + new tests pass",
            "Show the diff for developer review, then commit on a fix branch and move the ticket to In Review",
        ],
        "files": [
            {"path": "tests/test_ess_202.py", "content": TESTS_202},
            {"path": SERVICE, "replace": [{"old": OLD_ADD, "new": NEW_ADD}]},
        ],
        "branch_slug": "reject-duplicate-empid",
        "commit_title": "Reject adding a user with an existing EMPID",
        "summary": [
            "add_user() raises ValueError('EMPID <id> already exists') instead of creating a second row",
            "User list is unchanged after a rejected add",
            "Add regression tests in tests/test_ess_202.py",
        ],
    },
    "ESS-203": {
        "focus": (SERVICE, "_validate"),
        "analysis": {
            "root_cause": (
                "_validate() only checks for None. Empty strings and space-only strings pass, and the values "
                "are returned exactly as typed (no trimming). Both add_user() and update_user() rely on "
                "_validate(), so the problem exists in both places."
            ),
            "evidence": [
                "app/user_service.py: _validate() only tests `is None`, then returns the raw values",
                "The web form always sends strings, so None never happens - blank text is accepted",
                "Existing tests only use valid, already-trimmed values",
            ],
            "unknowns": [
                "Maximum length / allowed characters for EMPID and username are not specified - not enforced",
            ],
        },
        "plan": [
            "Add regression tests (tests/test_ess_203.py) for blank values, trimming and edit, confirm they FAIL",
            "Rewrite _validate() to trim each value and raise ValueError('<Field> is required') when empty",
            "Change only _validate(): add_user() and update_user() already call it, so both are fixed",
            "Run the full test suite and confirm existing + new tests pass",
            "Show the diff for developer review, then commit on a fix branch and move the ticket to In Review",
        ],
        "files": [
            {"path": "tests/test_ess_203.py", "content": TESTS_203},
            {"path": SERVICE, "replace": [{"old": OLD_VALIDATE, "new": NEW_VALIDATE}]},
        ],
        "branch_slug": "validate-required-fields",
        "commit_title": "Require and trim EMPID, username and designation",
        "summary": [
            "_validate() trims values and raises ValueError('<Field> is required') for blank / missing input",
            "Same rules now apply to add and edit (both call _validate)",
            "Add regression tests in tests/test_ess_203.py",
        ],
    },
}
