import unittest
from fastapi.testclient import TestClient
from backend.main import app

class TestSuggestCaseType(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_suggest_case_type_endpoint(self):
        payload = {
            "raw_text": "This is a case of fatal accident where the deceased died on the spot.",
            "selected_case_type": "death"
        }
        response = self.client.post("/api/ocr/suggest-case-type", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("suggestions", data)
        self.assertIn("selected", data)
        self.assertEqual(data["selected"], "death")
        
        # Verify format of suggestions
        suggestions = data["suggestions"]
        self.assertGreater(len(suggestions), 0)
        for s in suggestions:
            self.assertIn("case_type", s)
            self.assertIn("confidence", s)
            self.assertIsInstance(s["confidence"], (int, float))

if __name__ == "__main__":
    unittest.main()
