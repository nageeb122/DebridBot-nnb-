import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import service_health
import user_store


class ServiceHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_means_api_responded(self):
        provider = type("Provider", (), {
            "slug": "torbox",
            "list_torrents": AsyncMock(return_value=[object(), object()]),
        })()
        result = await service_health.check_provider(provider)
        self.assertEqual(result.status, "ok")
        self.assertIn("torrents=2", result.detail)

    async def test_timeout_is_reported(self):
        async def slow():
            await asyncio.sleep(0.05)
        provider = type("Provider", (), {
            "slug": "slow",
            "list_torrents": AsyncMock(side_effect=slow),
        })()
        result = await service_health.check_provider(provider, timeout=0.001)
        self.assertEqual(result.status, "timeout")

    async def test_error_does_not_leak_exception_message(self):
        async def fail():
            raise RuntimeError("private response or token-like data")
        provider = type("Provider", (), {
            "slug": "broken",
            "list_torrents": AsyncMock(side_effect=RuntimeError("private response or token-like data")),
        })()
        result = await service_health.check_provider(provider)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.detail, "RuntimeError")
        self.assertNotIn("private", result.detail)


class ServiceHealthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = user_store.DB_PATH
        user_store.DB_PATH = Path(self.temp_dir.name) / "health.sqlite3"
        user_store.init_db()

    def tearDown(self):
        user_store.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_latest_health_result_is_persisted_without_secrets(self):
        user_store.save_service_health("torbox", "ok", "API responded")
        user_store.save_service_health("torbox", "error", "RuntimeError")
        rows = user_store.get_service_health()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[0]["detail"], "RuntimeError")
        self.assertNotIn("token", rows[0])


if __name__ == "__main__":
    unittest.main()
