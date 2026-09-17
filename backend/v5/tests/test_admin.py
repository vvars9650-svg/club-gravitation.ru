import json
import unittest
from unittest.mock import patch

from backend.v5.admin import STATUSES, admin_handler
from backend.v5.authorizer import AdminAuthorizationError, authorize_admin
from backend.v5.handler import handler
from backend.v5.repository import FakeRepository, RepositoryUnavailable
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo


def event(method, path, body=None, query=None):
    return {"httpMethod": method, "path": path, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body) if body is not None else "", "queryStringParameters": query}


def gateway_v01_participant_event(method, participant_id, body=None):
    request = event(method, "/admin/participants/{id}", body)
    request["pathParams"] = {"id": participant_id}
    return request


class AdminMvpTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        submit(payload_with_photo(self.repo, "admin-key-1"), "admin-key-1", self.repo, "request-admin-1")
        second = {**P, "full_name": "Мария Тестова", "phone": "+79990000002"}
        submit(payload_with_photo(self.repo, "admin-key-2", second), "admin-key-2", self.repo, "request-admin-2")
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
        third = payload_with_photo(self.repo, "admin-key-3", {**P, "occupation": "новая анкета"})
        submit(third, "admin-key-3", self.repo, "request-admin-3")
        response = self.call("GET", "/admin/participants/" + self.first_id)
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(body["applications"]), 2)
        self.assertIn("occupation", body["applications"][0]["form"])
        self.assertEqual(body["consents"][0]["consent_version"], "CONSENT-PD-2.2")
        self.assertEqual(body["consents"][0]["policy_version"], "PPD-2.2")
        self.assertEqual(body["consents"][0]["form_version"], "FORM-2.2")
        self.assertEqual(body["consents"][0]["consent_text_hash"], "7a4ed02773773d680bb56399c943b94e2f35cf97d96b89a29e156d132fca6bf7")

    def test_gateway_v01_get_returns_existing_participant_card(self):
        response = admin_handler(
            gateway_v01_participant_event("GET", self.first_id),
            repo=self.repo,
            actor_identity="operator@example.test",
        )
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["participant"]["participant_id"], self.first_id)
        self.assertTrue(body["applications"])
        self.assertTrue(body["consents"])

    def test_gateway_v01_get_returns_controlled_not_found(self):
        response = admin_handler(
            gateway_v01_participant_event("GET", "PT-missing"),
            repo=self.repo,
            actor_identity="operator@example.test",
        )
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(self.body(response)["error"]["code"], "participant_not_found")

    def test_gateway_v01_patch_updates_selected_participant(self):
        second_id = self.repo.by_key["admin-key-2"]["participant_id"]
        second_owner = self.repo.get_admin_participant(second_id)["participant"]["owner"]
        response = admin_handler(
            gateway_v01_participant_event("PATCH", self.first_id, {"owner": "Лара"}),
            repo=self.repo,
            actor_identity="operator@example.test",
        )
        body = self.body(response)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["participant"]["participant_id"], self.first_id)
        self.assertEqual(body["participant"]["owner"], "Лара")
        self.assertEqual(self.repo.get_admin_participant(second_id)["participant"]["owner"], second_owner)

    def test_concrete_participant_path_remains_supported(self):
        response = self.call("GET", "/admin/participants/" + self.first_id)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body(response)["participant"]["participant_id"], self.first_id)

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

    def test_full_authorized_read_card_write_and_read_flow(self):
        list_request = event("GET", "/admin/applications")
        list_request["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "e2e-operator"}}}}
        listed = handler(list_request, repo=self.repo)
        listed_body = self.body(listed)
        self.assertEqual(listed["statusCode"], 200)
        self.assertEqual(listed_body["environment"], "TEST")
        self.assertTrue(any(row["participant_id"] == self.first_id for row in listed_body["applications"]))

        card_request = event("GET", "/admin/participants/" + self.first_id)
        card_request["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "e2e-operator"}}}}
        card = handler(card_request, repo=self.repo)
        self.assertEqual(card["statusCode"], 200)
        self.assertEqual(self.body(card)["participant"]["participant_id"], self.first_id)

        patch_request = event("PATCH", "/admin/participants/" + self.first_id, {"owner": "E2E оператор"})
        patch_request["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "e2e-operator"}}}}
        saved = handler(patch_request, repo=self.repo)
        saved_body = self.body(saved)
        self.assertEqual(saved["statusCode"], 200)
        self.assertEqual(saved_body["participant"]["owner"], "E2E оператор")
        self.assertEqual(saved_body["changed_fields"], ["owner"])

        reread = handler(card_request, repo=self.repo)
        self.assertEqual(reread["statusCode"], 200)
        self.assertEqual(self.body(reread)["participant"]["owner"], "E2E оператор")
        self.assertIn("actor=auth-", self.repo.audit[-1]["action"])
        self.assertNotIn("e2e-operator", self.repo.audit[-1]["action"])

    def test_patch_priority_with_unchanged_empty_next_contact_uses_current_contract(self):
        response = self.call(
            "PATCH", "/admin/participants/" + self.first_id,
            {"priority": "Высокий", "next_contact_at": ""},
        )

        self.assertEqual(response["statusCode"], 200)
        body = self.body(response)
        self.assertEqual(body["participant"]["priority"], "Высокий")
        self.assertIsNone(body["participant"]["next_contact_at"])
        self.assertEqual(body["changed_fields"], ["next_contact_at", "priority"])
        self.assertIn("fields=next_contact_at,priority", self.repo.audit[-1]["action"])

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
        self.assertEqual(runtime_response["statusCode"], 401)
        self.assertEqual(self.body(runtime_response)["error"]["code"], "admin_authentication_required")

    def test_handler_accepts_only_trusted_gateway_jwt_sub(self):
        spoofed = event("GET", "/admin/applications")
        spoofed["headers"].update({"X-User": "spoof", "X-Admin-Scopes": "admin:read admin:write", "Authorization": "Bearer spoof", "Cookie": "sub=spoof; scope=admin:write"})
        spoofed["body"] = json.dumps({"actor_identity": "spoof", "scopes": ["admin:read", "admin:write"]})
        spoofed["queryStringParameters"] = {"actor": "spoof", "scope": "admin:write"}
        spoofed["cookies"] = ["sub=spoof", "scope=admin:write"]
        self.assertEqual(handler(spoofed, repo=self.repo)["statusCode"], 401)
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
        self.assertEqual(handler(missing_sub, repo=self.repo)["statusCode"], 401)

    def test_handler_builds_runtime_repository_for_trusted_admin(self):
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        with patch("backend.v5.handler.runtime_repository", return_value=self.repo) as runtime:
            response = handler(trusted)
        runtime.assert_called_once_with()
        self.assertEqual(response["statusCode"], 200)

    def test_handler_uses_injected_admin_repository_without_runtime_creation(self):
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        with patch("backend.v5.handler.runtime_repository") as runtime:
            response = handler(trusted, repo=self.repo)
        runtime.assert_not_called()
        self.assertEqual(response["statusCode"], 200)

    def test_handler_does_not_build_repository_for_spoofed_admin_identity(self):
        spoofed = event("GET", "/admin/applications", {"actor_identity": "spoof"}, {"actor": "spoof"})
        spoofed["headers"].update({"Authorization": "Bearer spoof", "X-User": "spoof"})
        with patch("backend.v5.handler.runtime_repository") as runtime:
            response = handler(spoofed)
        runtime.assert_not_called()
        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(self.body(response)["error"]["code"], "admin_authentication_required")

    def test_handler_returns_runtime_repository_error_for_trusted_admin(self):
        trusted = event("GET", "/admin/applications")
        trusted["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        with patch("backend.v5.handler.runtime_repository", side_effect=RepositoryUnavailable("ydb_unavailable")):
            response = handler(trusted)
        self.assertEqual(response["statusCode"], 503)
        self.assertEqual(self.body(response)["error"]["code"], "ydb_unavailable")

    def test_intake_routes_do_not_require_admin_claims(self):
        self.assertEqual(handler({"httpMethod": "GET", "path": "/health"}, repo=self.repo)["statusCode"], 200)
        intake = event("POST", "/applications", P)
        intake["headers"]["Idempotency-Key"] = "intake-auth-independent"
        intake["body"] = json.dumps(payload_with_photo(self.repo, "intake-auth-independent"))
        self.assertEqual(handler(intake, repo=self.repo)["statusCode"], 201)

    def test_authorizer_requires_gateway_context_and_subject_only(self):
        with self.assertRaisesRegex(AdminAuthorizationError, "admin_authentication_required"):
            authorize_admin(event("GET", "/admin/applications"))

        missing_subject = event("GET", "/admin/applications")
        missing_subject["requestContext"] = {"authorizer": {"jwt": {"claims": {"email": "operator@example.test"}}}}
        with self.assertRaisesRegex(AdminAuthorizationError, "admin_authentication_required"):
            authorize_admin(missing_subject)

        no_scopes = event("GET", "/admin/applications")
        no_scopes["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": " subject "}}}}
        self.assertEqual(authorize_admin(no_scopes).subject, "subject")

        irrelevant_scopes = event("PATCH", "/admin/participants/PT-1", {"owner": "TEST"})
        irrelevant_scopes["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "subject", "scope": "openid email profile"}, "scopes": []}}}
        self.assertEqual(authorize_admin(irrelevant_scopes).subject, "subject")

    def test_gateway_subject_grants_full_test_admin_read_and_write_without_custom_scopes(self):
        read = event("GET", "/admin/applications")
        read["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        self.assertEqual(handler(read, repo=self.repo)["statusCode"], 200)

        write = event("PATCH", "/admin/participants/" + self.first_id, {"owner": "Влад"})
        write["requestContext"] = {"authorizer": {"jwt": {"claims": {"sub": "identity-hub-subject"}}}}
        response = handler(write, repo=self.repo)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body(response)["participant"]["owner"], "Влад")

    def test_every_admin_endpoint_fails_closed_without_gateway_authorization(self):
        requests = (
            ("GET", "/admin/applications", None),
            ("GET", "/admin/participants/" + self.first_id, None),
            ("PATCH", "/admin/participants/" + self.first_id, {"owner": "spoof"}),
        )
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                with patch("backend.v5.handler.runtime_repository") as runtime:
                    response = handler(event(method, path, body))
                runtime.assert_not_called()
                self.assertEqual(response["statusCode"], 401)
                self.assertEqual(self.body(response)["error"]["code"], "admin_authentication_required")

    def test_statuses_are_approved(self):
        self.assertEqual(STATUSES, ("Новая заявка", "На рассмотрении", "Нужен контакт", "Интервью назначено", "Интервью пройдено", "Одобрен", "Активный участник", "Пауза", "Не подходит"))
