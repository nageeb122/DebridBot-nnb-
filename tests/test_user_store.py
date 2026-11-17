import tempfile
import unittest
from pathlib import Path

import user_store


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = user_store.DB_PATH
        user_store.DB_PATH = Path(self.temp_dir.name) / "users.sqlite3"
        user_store.init_db()

    def tearDown(self):
        user_store.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_open_mode_allows_unblocked_users_by_default(self):
        self.assertTrue(user_store.is_authorized(101, frozenset(), frozenset()))

    def test_configured_allowlist_defaults_to_restricted(self):
        allowed = frozenset({101})
        self.assertTrue(user_store.is_authorized(101, frozenset(), allowed))
        self.assertFalse(user_store.is_authorized(202, frozenset(), allowed))

    def test_approved_user_is_allowed_in_restricted_mode(self):
        user_store.set_access_mode("restricted")
        user_store.set_user_status(202, "approved")
        self.assertTrue(user_store.is_authorized(202, frozenset(), frozenset()))

    def test_blocked_user_is_denied_even_if_in_config_allowlist(self):
        user_store.set_user_status(101, "blocked")
        self.assertFalse(
            user_store.is_authorized(101, frozenset(), frozenset({101}))
        )

    def test_admin_bypasses_block_and_restriction(self):
        user_store.set_user_status(101, "blocked")
        self.assertTrue(
            user_store.is_authorized(101, frozenset({101}), frozenset())
        )

    def test_activity_is_persisted_and_counted(self):
        user_store.record_activity(303, "sample_user", "Sample")
        user_store.record_activity(303, "sample_user", "Sample")
        rows = user_store.list_users()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_id"], 303)
        self.assertEqual(rows[0]["message_count"], 2)

    def test_unblock_clears_override(self):
        user_store.set_user_status(404, "blocked")
        user_store.clear_user_status(404)
        self.assertTrue(user_store.is_authorized(404, frozenset(), frozenset()))


if __name__ == "__main__":
    unittest.main()
