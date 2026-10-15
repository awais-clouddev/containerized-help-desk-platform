import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ROW = (1, "Awais", "Example issue", "High", "Open", "2026-10-15 12:00:00")


class MemoryCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value


class CacheTests(unittest.TestCase):
    def test_filter_case_and_request_order(self):
        for field, values in (
            ("priority", ("High", "high")),
            ("priority", ("high", "High")),
            ("status", ("Open", "open")),
            ("status", ("open", "Open")),
        ):
            with self.subTest(field=field, values=values):
                cache = MemoryCache()
                db = Mock()
                db.cursor.return_value.fetchall.return_value = [ROW]
                with patch("app.main.get_redis_connection", return_value=cache), \
                     patch("app.main.get_database_connection", return_value=db) as connect:
                    first = client.get("/tickets", params={field: values[0]})
                    second = client.get("/tickets", params={field: values[1]})
                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(first.json()["tickets"], second.json()["tickets"])
                self.assertEqual(second.json()["source"], "redis-cache")
                self.assertEqual(connect.call_count, 1)
                query, parameters = db.cursor.return_value.execute.call_args.args
                self.assertIn(f"LOWER({field}) = %s", query)
                self.assertEqual(parameters, [values[0].lower()])

    def test_corrupt_cache_falls_back(self):
        for value in ("not-json", "{}", "[{}]", "null"):
            with self.subTest(value=value):
                cache = Mock()
                cache.get.return_value = value
                db = Mock()
                db.cursor.return_value.fetchall.return_value = [ROW]
                with patch("app.main.get_redis_connection", return_value=cache), \
                     patch("app.main.get_database_connection", return_value=db):
                    response = client.get("/tickets")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["source"], "postgresql")
                self.assertEqual(len(response.json()["tickets"]), 1)
                cache.setex.assert_called_once()

    def test_filter_delimiters_do_not_collide(self):
        cache = MemoryCache()
        db = Mock()
        db.cursor.return_value.fetchall.return_value = []
        with patch("app.main.get_redis_connection", return_value=cache), \
             patch("app.main.get_database_connection", return_value=db) as connect:
            for filters in (
                {"search": "a:status:b", "status": "c"},
                {"search": "a", "status": "b:status:c"},
            ):
                self.assertEqual(client.get("/tickets", params=filters).status_code, 200)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(len(cache.data), 2)


if __name__ == "__main__":
    unittest.main()
