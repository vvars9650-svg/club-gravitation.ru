import json
import unittest

from backend.v5.admin import STATUSES, admin_handler
from backend.v5.handler import handler
from backend.v5.repository import FakeRepository
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P


def event(method, path, body=None, query=None):
    return {"httpMethod": method, "path": path, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body) if body is not None else "", "queryStringParameters": query}


class AdminMvpTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        submit(P, "admin-key-1", self.repo, "request-admin-1")
        submit({**P, "full_name": "Мария Тестова", "phone": "+79990000002"}, "admin-key-2", self.repo, "request-admin-2")
        self.first_id = self.repo.by_key["admin-key-1"]["participant_id"]

    def call(self, method, path, body=None, query=None):
        return admin_handler(event(method, path, body, query), repo=self.repo, actor_identity="operator@example.test")

    def body(self, response):
        return json.loads(response["body"])

    def test_applications_list_search_filter_and_sort_are_test_only(self):
        self.repo.by_key["admin-key-1"]["environment"] = "PROD"
        response = self.call("GET", "/admin/applications", query={"q": "Мария", "sort": "full_name", "order": "asc"})
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["environment"], "TEST")
        self.assertEqual([row["full_name"] for row in body["applications"]], ["Мария Тестова"])
        self.assertTrue(all(row["environment"] == "TEST" for row in body["applications"]))

    def test_participant_card_has_form_history_and_read_only_consent(self):
        submit({**P, "occupation": "новая анкета"}, "admin-key-3", self.repo, "request-admin-3")
        response = self.call("GET", "/admin/participants/" + self.first_id)
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(body["applications"]), 2)
        self.assertIn("occupation", body["applications"][0]["form"])
        self.assertEqual(body["consents"][0]["consent_version"], "CONSENT-PD-2.0")

    def test_patch_allowlist_and_audit_event(self):
        response = self.call("PATCH", "/admin/participants/" + self.first_id, {"lifecycle_status": "На рассмотрении", "owner": "Влад", "internal_comment": "Связаться в TEST"})
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["participant"]["lifecycle_status"], "На рассмотрении")
        audit = self.repo.audit[-1]
        self.assertIn("fields=internal_comment,lifecycle_status,owner", audit["action"])
        self.assertIn("actor=auth-", audit["action"])
        self.assertNotIn("Связаться в TEST", audit["action"])
        self.assertNotIn("+7999", audit["action"])

    def test_patch_rejects_intake_fields_and_invalid_status(self):
        immutable = self.call("PATCH", "/admin/participants/" + self.first_id, {"phone": "+70000000000"})
        bad_status = self.call("PATCH", "/admin/participants/" + self.first_id, {"lifecycle_status": "Придуманный"})
        self.assertEqual(immutable["statusCode"], 422)
        self.assertEqual(self.body(immutable)["error"]["code"], "immutable_or_unknown_field")
        self.assertEqual(bad_status["statusCode"], 422)
        self.assertEqual(self.body(bad_status)["error"]["code"], "invalid_lifecycle_status")

    def test_admin_is_not_published_without_auth_identity(self):
        response = admin_handler(event("GET", "/admin/applications"), repo=self.repo)
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(self.body(response)["error"]["code"], "admin_not_published")
        runtime_response = handler(event("GET", "/admin/applications"), repo=self.repo)
        self.assertEqual(runtime_response["statusCode"], 404)

    def test_handler_accepts_only_trusted_gateway_jwt_sub(self):
        spoofed = event("GET", "/admin/applications")
        spoofed["headers"].update({"X-User": "spoof", "Authorization": "Bearer spoof"})
        spoofed["body"] = json.dumps({"actor_identity": "spoof"})
        spoofed["queryStringParameters"] = {"actor": "spoof"}
        self.assertEqual(handler(spoofed, repo=self.repo)["statusCode"], 404)
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        self.assertEqual(handler(trusted, repo=self.repo)["statusCode"], 200)
        patch = event("PATCH", "/admin/participants/" + self.first_id, {"owner": "Лара"})
        patch["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        self.assertEqual(handler(patch, repo=self.repo)["statusCode"], 200)
        self.assertIn("actor=auth-", self.repo.audit[-1]["action"])
        self.assertNotIn("identity-hub-subject", self.repo.audit[-1]["action"])
        missing_sub = event("GET", "/admin/applications")
        missing_sub["requestContext"] = {"authorizer": {"jwt": {"claims": {"email": "not-an-actor@example.test"}}}}
        self.assertEqual(handler(missing_sub, repo=self.repo)["statusCode"], 404)

    def test_intake_routes_do_not_require_admin_claims(self):
        self.assertEqual(handler({"httpMethod": "GET", "path": "/health"}, repo=self.repo)["statusCode"], 200)
        intake = event("POST", "/applications", P)
        intake["headers"]["Idempotency-Key"] = "intake-auth-independent"
        self.assertEqual(handler(intake, repo=self.repo)["statusCode"], 201)

    def test_statuses_are_approved(self):
        self.assertEqual(STATUSES, ("Новая заявка", "На рассмотрении", "Нужен контакт", "Интервью назначено", "Интервью пройдено", "Одобрен", "Активный участник", "Пауза", "Не подходит"))
