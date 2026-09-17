import json
import unittest
from unittest.mock import patch

from backend.v5.admin import (
    DECISIONS,
    NEXT_ACTIONS,
    OPERATIONAL_FIELDS,
    OWNERS,
    PRIORITIES,
    STATUSES,
    admin_handler,
)
from backend.v5.authorizer import AdminAuthorizationError, authorize_admin
from backend.v5.handler import handler
from backend.v5.repository import FakeRepository, RepositoryUnavailable
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo


def event(method, path, body=None, query=None):
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body is not None else "",
        "queryStringParameters": query,
    }


class AdminCrmV2Tests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        first, _ = submit(
            payload_with_photo(self.repo, "admin-key-1"),
            "admin-key-1", self.repo, "request-admin-1",
        )
        second_payload = {**P, "full_name": "Мария Alpha", "phone": "+79990000002", "age": 31}
        second, _ = submit(
            payload_with_photo(self.repo, "admin-key-2", second_payload),
            "admin-key-2", self.repo, "request-admin-2",
        )
        self.first_id = first["application_id"]
        self.second_id = second["application_id"]

    def call(self, method, path, body=None, query=None):
        return admin_handler(
            event(method, path, body, query),
            repo=self.repo,
            actor_identity="operator@example.test",
        )

    @staticmethod
    def body(response):
        return json.loads(response["body"])

    def test_list_search_is_case_insensitive_substring_and_numeric(self):
        cases = (
            ("мАРия", self.second_id),
            ("ALP", self.second_id),
            ("31", self.second_id),
            ("9990000001", self.first_id),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                response = self.call("GET", "/admin/applications", query={"q": query})
                rows = self.body(response)["applications"]
                self.assertEqual([row["application_id"] for row in rows], [expected])

    def test_list_exposes_same_application_operational_values_as_card(self):
        self.repo.update_admin_application(
            self.first_id,
            {"owner": "Влад", "priority": "Высокий", "next_action": "Рассмотреть"},
            "actor", "request-update",
        )
        listed = self.body(self.call("GET", "/admin/applications"))["applications"]
        row = next(item for item in listed if item["application_id"] == self.first_id)
        card = self.body(self.call("GET", "/admin/applications/" + self.first_id))["application"]
        for name in ("status", "owner", "priority", "next_action", "next_contact_at", "decision"):
            self.assertEqual(row[name], card[name])
        self.assertEqual(row["application_number"], 1)

    def test_card_has_one_application_consent_and_service_events(self):
        response = self.call("GET", "/admin/applications/" + self.first_id)
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["application"]["application_id"], self.first_id)
        self.assertNotIn("applications", body)
        self.assertEqual(body["consents"][0]["consent_version"], "CONSENT-PD-2.2")
        self.assertEqual(body["events"][0]["action"], "application_created")

    def test_duplicate_warning_is_attached_to_original_application(self):
        duplicate_payload = {**P, "phone": "+7 (999) 000-00-01", "email": "other@example.test"}
        duplicate, _ = submit(
            payload_with_photo(self.repo, "admin-duplicate", duplicate_payload),
            "admin-duplicate", self.repo, "duplicate-request",
        )
        self.assertTrue(duplicate["duplicate_submission"])
        card = self.body(self.call("GET", "/admin/applications/" + self.first_id))["application"]
        self.assertEqual(card["duplicate_attempt_count"], 1)
        self.assertEqual(card["last_duplicate_match_basis"], "normalized_phone")
        events = self.body(self.call("GET", "/admin/applications/" + self.first_id))["events"]
        self.assertTrue(any(item["action"].startswith("duplicate_submission") for item in events))

    def test_decision_sets_status_and_update_is_application_scoped(self):
        second_before = self.repo.get_admin_application(self.second_id)["application"]
        response = self.call(
            "PATCH",
            "/admin/applications/" + self.first_id,
            {"decision": "На рассмотрении", "owner": "Лара", "priority": "Средний", "next_action": "Связаться", "next_contact_at": "2026-09-20T18:30", "internal_comment": "Позвонить"},
        )
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["application"]["status"], "На рассмотрении")
        self.assertEqual(body["application"]["decision"], "На рассмотрении")
        self.assertEqual(self.repo.get_admin_application(self.second_id)["application"], second_before)
        self.assertIn("actor=auth-", self.repo.audit[-1]["action"])
        self.assertNotIn("Позвонить", self.repo.audit[-1]["action"])

    def test_status_is_not_directly_editable_and_values_are_controlled(self):
        scenarios = (
            ({"status": "Одобрен"}, "immutable_or_unknown_field"),
            ({"lifecycle_status": "Одобрен"}, "immutable_or_unknown_field"),
            ({"owner": "Другой"}, "invalid_owner"),
            ({"priority": "Срочно"}, "invalid_priority"),
            ({"next_action": "Позвонить"}, "invalid_next_action"),
            ({"decision": "Рассмотрена"}, "invalid_decision"),
            ({"next_contact_at": "2026-09-20"}, "invalid_next_contact_at"),
            ({"phone": "+70000000000"}, "immutable_or_unknown_field"),
        )
        for payload, code in scenarios:
            with self.subTest(payload=payload):
                response = self.call("PATCH", "/admin/applications/" + self.first_id, payload)
                self.assertEqual(response["statusCode"], 422)
                self.assertEqual(self.body(response)["error"]["code"], code)

    def test_workflow_requires_approved_action_and_contact_time(self):
        missing_contact = self.call(
            "PATCH", "/admin/applications/" + self.first_id,
            {"decision": "Интервью назначено", "next_action": "Провести интервью"},
        )
        self.assertEqual(missing_contact["statusCode"], 422)
        self.assertEqual(self.body(missing_contact)["error"]["code"], "next_contact_required")
        wrong_action = self.call(
            "PATCH", "/admin/applications/" + self.first_id,
            {"decision": "Пауза", "next_action": "Связаться", "next_contact_at": "2026-09-20T18:30"},
        )
        self.assertEqual(wrong_action["statusCode"], 422)
        self.assertEqual(self.body(wrong_action)["error"]["code"], "invalid_next_action_for_status")
        valid = self.call(
            "PATCH", "/admin/applications/" + self.first_id,
            {"decision": "Пауза", "next_action": "Связаться позже", "next_contact_at": "2026-09-20T18:30"},
        )
        self.assertEqual(valid["statusCode"], 200)
        self.assertEqual(self.body(valid)["application"]["status"], "Пауза")

    def test_only_internal_comment_is_free_text(self):
        self.assertEqual(OPERATIONAL_FIELDS, ("owner", "priority", "next_action", "next_contact_at", "decision", "internal_comment"))
        response = self.call("PATCH", "/admin/applications/" + self.first_id, {"internal_comment": "Свободный рабочий комментарий"})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body(response)["application"]["internal_comment"], "Свободный рабочий комментарий")

    def test_approved_dictionaries_are_exact(self):
        self.assertEqual(STATUSES, ("Новая заявка", "На рассмотрении", "Нужен контакт", "Интервью назначено", "Интервью пройдено", "Одобрен", "Ожидаем ответ", "Пауза", "Активный участник", "Не подходит"))
        self.assertEqual(DECISIONS, STATUSES[1:])
        self.assertEqual(OWNERS, ("Влад", "Лара"))
        self.assertEqual(PRIORITIES, ("Высокий", "Средний", "Низкий"))
        self.assertEqual(NEXT_ACTIONS, ("Рассмотреть", "Связаться", "Назначить интервью", "Провести интервью", "Обсудить", "Пригласить", "Дождаться ответа", "Добавить в участники", "Связаться позже"))

    def test_admin_is_test_only_and_fails_closed_without_gateway_subject(self):
        direct = admin_handler(event("GET", "/admin/applications"), repo=self.repo)
        self.assertEqual(direct["statusCode"], 404)
        self.assertEqual(handler(event("GET", "/admin/applications"), repo=self.repo)["statusCode"], 401)
        spoofed = event("GET", "/admin/applications")
        spoofed["headers"].update({"Authorization": "Bearer spoof", "X-User": "spoof"})
        spoofed["body"] = json.dumps({"actor_identity": "spoof"})
        self.assertEqual(handler(spoofed, repo=self.repo)["statusCode"], 401)

    def test_trusted_gateway_subject_can_read_and_write(self):
        read = event("GET", "/admin/applications")
        read["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        self.assertEqual(handler(read, repo=self.repo)["statusCode"], 200)
        write = event("PATCH", "/admin/applications/" + self.first_id, {"owner": "Влад"})
        write["requestContext"] = read["requestContext"]
        self.assertEqual(handler(write, repo=self.repo)["statusCode"], 200)

    def test_authorizer_uses_only_gateway_sub(self):
        with self.assertRaisesRegex(AdminAuthorizationError, "admin_authentication_required"):
            authorize_admin(event("GET", "/admin/applications"))
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": " subject "}}}}
        self.assertEqual(authorize_admin(trusted).subject, "subject")

    def test_handler_repository_lifecycle_preserves_auth_boundary(self):
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "subject"}}}}
        with patch("backend.v5.handler.runtime_repository", return_value=self.repo) as runtime:
            self.assertEqual(handler(trusted)["statusCode"], 200)
        runtime.assert_called_once_with()
        with patch("backend.v5.handler.runtime_repository", side_effect=RepositoryUnavailable("ydb_unavailable")):
            self.assertEqual(handler(trusted)["statusCode"], 503)


if __name__ == "__main__":
    unittest.main()
