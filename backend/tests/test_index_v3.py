import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "index_v3.py"
SPEC = importlib.util.spec_from_file_location("gravitation_index_v3", MODULE_PATH)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class DummyContext:
    request_id = "req-test-123"


class BackendHelpersTest(unittest.TestCase):
    def test_normalize_phone(self):
        self.assertEqual(
            backend.normalize_phone("+7 (999) 123-45-67"),
            "+79991234567",
        )
        self.assertEqual(
            backend.normalize_phone("8 999 123 45 67"),
            "+79991234567",
        )

    def test_normalize_email_and_telegram(self):
        self.assertEqual(
            backend.normalize_email(" Test@Example.COM "),
            "test@example.com",
        )
        self.assertEqual(
            backend.normalize_telegram("https://t.me/TestUser"),
            "@testuser",
        )
        self.assertEqual(
            backend.normalize_telegram("@Another_User"),
            "@another_user",
        )

    def test_aliases_are_mapped(self):
        normalized = backend.normalize_payload(
            {
                "name": "Иван Иванов",
                "city_visit": "Да",
                "life_beyond_work": "Спорт",
                "interest_reason": "Люди",
                "expectations": "Общение",
                "connection_goal": "Дружба",
                "values_people": "Уважение",
                "meeting_barriers": "Время",
                "introduction_scenario": "Через общее дело",
                "personal_data_consent": "true",
                "rules_consent": "true",
                "phone": "+7 999 123-45-67",
            }
        )
        self.assertEqual(normalized["full_name"], "Иван Иванов")
        self.assertEqual(normalized["visit_krasnodar"], "Да")
        self.assertEqual(normalized["life_outside_work"], "Спорт")
        self.assertEqual(normalized["what_interested"], "Люди")
        self.assertEqual(normalized["event_expectations"], "Общение")
        self.assertEqual(normalized["desired_connections"], "Дружба")
        self.assertEqual(normalized["values_in_people"], "Уважение")
        self.assertEqual(normalized["barriers_to_meeting"], "Время")
        self.assertEqual(
            normalized["acquaintance_scenario"],
            "Через общее дело",
        )
        self.assertEqual(normalized["pd_consent"], "true")
        self.assertEqual(normalized["rules_accepted"], "true")
        self.assertEqual(normalized["phone"], "+79991234567")

    def test_stable_ids_are_deterministic(self):
        key = "test-key-1234567890"
        first = backend.stable_id("APP", key, "application", 20)
        second = backend.stable_id("APP", key, "application", 20)
        other = backend.stable_id("APP", key + "x", "application", 20)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertTrue(first.startswith("APP-"))

    def test_idempotency_key_validation(self):
        self.assertEqual(
            backend.validate_idempotency_key("abcDEF1234567890"),
            "abcDEF1234567890",
        )
        with self.assertRaises(ValueError):
            backend.validate_idempotency_key("short")
        with self.assertRaises(ValueError):
            backend.validate_idempotency_key("bad key with spaces")

    def test_photo_detection(self):
        self.assertEqual(
            backend.detect_image_type(b"\xff\xd8\xffrest"),
            ("image/jpeg", ".jpg"),
        )
        self.assertEqual(
            backend.detect_image_type(b"\x89PNG\r\n\x1a\nrest"),
            ("image/png", ".png"),
        )
        self.assertEqual(
            backend.detect_image_type(b"RIFF1234WEBPrest"),
            ("image/webp", ".webp"),
        )

    def test_fingerprint_changes_when_photo_changes(self):
        data = {"full_name": "Test", "phone": "+79991234567"}
        _, fp1 = backend.build_payload_snapshot(data, b"photo-a")
        _, fp2 = backend.build_payload_snapshot(data, b"photo-b")
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_is_stable_for_same_payload(self):
        data = {"phone": "+79991234567", "full_name": "Test"}
        _, fp1 = backend.build_payload_snapshot(data, b"photo-a")
        _, fp2 = backend.build_payload_snapshot(
            {"full_name": "Test", "phone": "+79991234567"},
            b"photo-a",
        )
        self.assertEqual(fp1, fp2)


class HandlerTest(unittest.TestCase):
    def _event(self, body, key="abcDEF1234567890"):
        return {
            "httpMethod": "POST",
            "headers": {
                "Content-Type": "application/json",
                "Idempotency-Key": key,
            },
            "body": json.dumps(body, ensure_ascii=False),
        }

    @patch.object(backend, "save_application")
    def test_handler_success(self, save_application):
        save_application.return_value = {
            "participant_id": "GR-1",
            "application_id": "APP-1",
            "file_id": "FILE-1",
            "participant_reused": False,
            "idempotent_replay": False,
        }

        response = backend.handler(
            self._event({"full_name": "Test"}),
            DummyContext(),
        )
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 201)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["participant_id"], "GR-1")
        self.assertEqual(payload["request_id"], "req-test-123")
        save_application.assert_called_once()

    @patch.object(backend, "save_application")
    def test_handler_replay_returns_200(self, save_application):
        save_application.return_value = {
            "participant_id": "GR-1",
            "application_id": "APP-1",
            "file_id": "FILE-1",
            "participant_reused": True,
            "idempotent_replay": True,
        }

        response = backend.handler(
            self._event({"full_name": "Test"}),
            DummyContext(),
        )
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(payload["idempotent_replay"])

    def test_handler_requires_idempotency_key(self):
        event = {
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"full_name": "Test"}),
        }
        response = backend.handler(event, DummyContext())
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(payload["code"], "validation_error")

    def test_handler_rejects_wrong_method(self):
        response = backend.handler(
            {"httpMethod": "GET", "headers": {}, "body": ""},
            DummyContext(),
        )
        self.assertEqual(response["statusCode"], 405)

    def test_urlencoded_body_is_supported(self):
        event = {
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            "body": "name=Test+User&phone=%2B79991234567",
        }
        parsed = backend.parse_event_body(event)
        self.assertEqual(parsed["name"], "Test User")
        self.assertEqual(parsed["phone"], "+79991234567")


if __name__ == "__main__":
    unittest.main()
