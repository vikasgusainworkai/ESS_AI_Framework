"""User management service: EMPID, username, designation."""
import json
from pathlib import Path


class UserService:
    """Keeps users in memory; saves them to a JSON file when a path is given."""

    def __init__(self, path=None):
        self._path = Path(path) if path else None
        self._users = []
        if self._path and self._path.exists():
            self._users = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self):
        if self._path:
            self._path.write_text(json.dumps(self._users, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _validate(empid, username, designation):
        """Return the cleaned (empid, username, designation) or raise ValueError."""
        if empid is None or username is None or designation is None:
            raise ValueError("All fields are required")
        return empid, username, designation

    def list_users(self):
        return [dict(u) for u in self._users]

    def get_user(self, empid):
        for user in self._users:
            if user["empid"] == empid:
                return user
        raise KeyError(f"User {empid} not found")

    def add_user(self, empid, username, designation):
        empid, username, designation = self._validate(empid, username, designation)
        if any(u["empid"] == empid for u in self._users):
            raise ValueError(f"EMPID {empid} already exists")
        user = {"empid": empid, "username": username, "designation": designation}
        self._users.append(user)
        self._save()
        return dict(user)

    def update_user(self, empid, username, designation):
        user = self.get_user(empid)
        _, username, designation = self._validate(empid, username, designation)
        user["username"] = username
        user["designation"] = designation
        self._save()
        return dict(user)

    def delete_user(self, empid):
        matches = [u for u in self._users if u["empid"].startswith(empid)]
        if not matches:
            raise KeyError(f"User {empid} not found")
        self._users = [u for u in self._users if u not in matches]
        self._save()
        return dict(matches[0])
