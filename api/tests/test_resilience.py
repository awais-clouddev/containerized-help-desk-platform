import os
import unittest
from unittest.mock import Mock, patch
from redis.exceptions import RedisError
from fastapi.testclient import TestClient
from app import main

client = TestClient(main.app)
ROW = (1, "Awais", "Example issue", "High", "Open", "2026-10-15 12:00:00")


class ResilienceTests(unittest.TestCase):
    def test_database_errors_rollback_and_close(self):
        operations = [
            lambda: main.create_ticket(main.TicketCreate(
                employee_name="Awais", issue="Example issue", priority="High")),
            lambda: main.get_tickets(search="", status="", priority=""),
            lambda: main.update_ticket_status(
                1, main.TicketStatusUpdate(status="Closed")),
            main.dashboard_summary,
        ]
        for operation in operations:
            db = Mock()
            cursor = db.cursor.return_value
            cursor.execute.side_effect = RuntimeError("query failed")
            cache = Mock()
            cache.get.return_value = None
            with patch("app.main.get_database_connection", return_value=db), \
                 patch("app.main.get_redis_connection", return_value=cache):
                with self.assertRaisesRegex(RuntimeError, "query failed"):
                    operation()
            db.rollback.assert_called_once()
            cursor.close.assert_called_once()
            db.close.assert_called_once()

    def test_cursor_creation_failure_closes_connection(self):
        db = Mock()
        db.cursor.side_effect = RuntimeError("cursor failed")
        with patch("app.main.get_database_connection", return_value=db):
            with self.assertRaisesRegex(RuntimeError, "cursor failed"):
                with main.database_session():
                    self.fail("Should not enter session")
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    def test_cursor_close_failure_still_closes_connection(self):
        db = Mock()
        db.cursor.return_value.close.side_effect = RuntimeError("close failed")
        with patch("app.main.get_database_connection", return_value=db):
            with self.assertRaisesRegex(RuntimeError, "close failed"):
                with main.database_session():
                    pass
        db.close.assert_called_once()

    def test_commit_failure_rolls_back_and_closes(self):
        db = Mock()
        db.cursor.return_value.fetchone.return_value = ROW
        db.commit.side_effect = RuntimeError("commit failed")
        with patch("app.main.get_database_connection", return_value=db):
            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                main.create_ticket(main.TicketCreate(
                    employee_name="Awais", issue="Example issue", priority="High"))
        db.rollback.assert_called_once()
        db.cursor.return_value.close.assert_called_once()
        db.close.assert_called_once()

    def test_committed_write_survives_redis_failure(self):
        db = Mock()
        db.cursor.return_value.fetchone.return_value = ROW
        cache = Mock()
        cache.scan_iter.side_effect = RedisError("cache offline")
        with patch("app.main.get_database_connection", return_value=db), \
             patch("app.main.get_redis_connection", return_value=cache):
            response = client.post("/tickets", json={
                "employee_name": "Awais",
                "issue": "Example issue",
                "priority": "High",
            })
        self.assertEqual(response.status_code, 201, response.text)
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_explicit_connection_timeouts(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.main.psycopg2.connect") as connect:
                main.get_database_connection()
                settings = connect.call_args.kwargs
                self.assertEqual(settings["connect_timeout"], 5)
                self.assertIn("statement_timeout=5000", settings["options"])
                self.assertIn("lock_timeout=3000", settings["options"])
            with patch("app.main.redis.Redis") as connect:
                main.get_redis_connection()
                settings = connect.call_args.kwargs
                self.assertEqual(settings["socket_connect_timeout"], 2)
                self.assertEqual(settings["socket_timeout"], 2)
                self.assertIn("retry", settings)

    def test_health_response_hides_internal_error(self):
        with patch("app.main.get_database_connection",
                   side_effect=RuntimeError("private connection details")):
            response = client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Dependencies unavailable")
        self.assertNotIn("private connection details", response.text)


if __name__ == "__main__":
    unittest.main()
