import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAPI(unittest.TestCase):
    def test_root(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_invalid_ticket(self):
        response = client.post("/tickets", json={
            "employee_name": "A",
            "issue": "Bad",
            "priority": "Invalid"
        })
        self.assertEqual(response.status_code, 422)

    def test_missing_ticket(self):
        with patch("app.main.get_database_connection") as mock_db:
            mock_db.return_value.cursor.return_value.fetchone.return_value = None
            response = client.patch("/tickets/999999/status", json={"status": "Closed"})
            self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
