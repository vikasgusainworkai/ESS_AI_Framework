"""Regression tests for ESS-203: EMPID, username and designation are required and trimmed."""
import unittest

from app.user_service import UserService


class Ess203RequiredFieldsTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()

    def test_blank_space_only_or_missing_values_are_rejected_on_add(self):
        cases = [
            (("", "asha", "Developer"), "EMPID is required"),
            (("EMP1", "   ", "Developer"), "Username is required"),
            (("EMP1", "asha", None), "Designation is required"),
        ]
        for args, message in cases:
            with self.subTest(args=args):
                with self.assertRaises(ValueError) as ctx:
                    self.svc.add_user(*args)
                self.assertEqual(str(ctx.exception), message)
        self.assertEqual(self.svc.list_users(), [])

    def test_values_are_trimmed_before_saving(self):
        self.svc.add_user("  EMP1 ", "  asha  ", " Developer ")
        self.assertEqual(self.svc.list_users(), [{"empid": "EMP1", "username": "asha", "designation": "Developer"}])

    def test_same_rules_apply_when_editing(self):
        self.svc.add_user("EMP1", "asha", "Developer")
        with self.assertRaises(ValueError) as ctx:
            self.svc.update_user("EMP1", "  ", "Tech Lead")
        self.assertEqual(str(ctx.exception), "Username is required")
        self.svc.update_user("EMP1", " asha.rao ", "  Tech Lead ")
        self.assertEqual(self.svc.get_user("EMP1"), {"empid": "EMP1", "username": "asha.rao", "designation": "Tech Lead"})


if __name__ == "__main__":
    unittest.main()
