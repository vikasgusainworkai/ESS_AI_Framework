"""Regression tests for ESS-202: an EMPID can only be added once."""
import unittest

from app.user_service import UserService


class Ess202DuplicateEmpidTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()
        self.svc.add_user("EMP1", "asha", "Developer")
        self.svc.add_user("EMP2", "ravi", "Tester")

    def test_adding_existing_empid_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.svc.add_user("EMP2", "meena", "Manager")
        self.assertEqual(str(ctx.exception), "EMPID EMP2 already exists")

    def test_list_is_unchanged_after_rejected_add(self):
        before = self.svc.list_users()
        with self.assertRaises(ValueError):
            self.svc.add_user("EMP2", "meena", "Manager")
        self.assertEqual(self.svc.list_users(), before)

    def test_new_empid_still_added(self):
        self.svc.add_user("EMP3", "meena", "Manager")
        self.assertEqual([u["empid"] for u in self.svc.list_users()], ["EMP1", "EMP2", "EMP3"])


if __name__ == "__main__":
    unittest.main()
