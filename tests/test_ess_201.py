"""Regression tests for ESS-201: delete must remove only the exact EMPID."""
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
