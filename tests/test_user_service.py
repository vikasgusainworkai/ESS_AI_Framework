"""Existing user-service tests (all green before any ticket is worked on)."""
import tempfile
import unittest
from pathlib import Path

from app.user_service import UserService


class UserServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = UserService()

    def test_add_and_list_user(self):
        self.svc.add_user("EMP1", "asha", "Developer")
        self.assertEqual(self.svc.list_users(), [{"empid": "EMP1", "username": "asha", "designation": "Developer"}])

    def test_get_user(self):
        self.svc.add_user("EMP1", "asha", "Developer")
        self.assertEqual(self.svc.get_user("EMP1")["username"], "asha")

    def test_update_user(self):
        self.svc.add_user("EMP1", "asha", "Developer")
        self.svc.update_user("EMP1", "asha.rao", "Tech Lead")
        self.assertEqual(self.svc.get_user("EMP1")["designation"], "Tech Lead")

    def test_update_unknown_user_raises(self):
        with self.assertRaises(KeyError):
            self.svc.update_user("EMP99", "x", "y")

    def test_delete_user(self):
        self.svc.add_user("EMP1", "asha", "Developer")
        self.svc.delete_user("EMP1")
        self.assertEqual(self.svc.list_users(), [])

    def test_users_are_saved_to_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "users.json"
            UserService(path).add_user("EMP1", "asha", "Developer")
            self.assertEqual(UserService(path).get_user("EMP1")["username"], "asha")


if __name__ == "__main__":
    unittest.main()
