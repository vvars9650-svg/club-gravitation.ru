import re
import unittest
from pathlib import Path


DEPLOYMENT = Path(__file__).resolve().parents[1] / "deployment"
CONFIG = DEPLOYMENT / "admin-api.test.yaml"
LIVE_PATCH = DEPLOYMENT / "admin-api.live-minimal.patch.yaml"


class AdminAuthorizationConfigTests(unittest.TestCase):
    def setUp(self):
        self.source = CONFIG.read_text(encoding="utf-8")

    def test_config_is_test_only_and_contains_no_credentials(self):
        self.assertIn("GRAVITATION V5 Admin API (TEST)", self.source)
        self.assertIn("https://auth.yandex.cloud/.well-known/openid-configuration", self.source)
        self.assertNotRegex(self.source, r"(?i)(client_secret|access_token|refresh_token|private_key)\s*:")
        self.assertNotIn("prod", self.source.lower())
        self.assertIn("default: https://test.club-gravitation.ru", self.source)
        self.assertNotIn("http://127.0.0.1", self.source)

    def test_gateway_requires_bearer_jwt_and_subject(self):
        self.assertIn("type: jwt", self.source)
        self.assertIn("name: Authorization", self.source)
        self.assertIn('prefix: "Bearer "', self.source)
        self.assertIn("- https://auth.yandex.cloud", self.source)
        self.assertIn("- sub", self.source)
        self.assertIn("audiences:", self.source)

    def test_every_admin_operation_requires_jwt_without_custom_scopes(self):
        self.assertRegex(self.source, re.compile(r"/admin/applications:.*?security:.*?- adminJwt: \[\]", re.S))
        self.assertRegex(self.source, re.compile(r"operationId: adminGetParticipant.*?- adminJwt: \[\]", re.S))
        self.assertRegex(self.source, re.compile(r"operationId: adminPatchParticipant.*?- adminJwt: \[\]", re.S))
        self.assertEqual(self.source.count("- adminJwt: []"), 3)
        self.assertNotRegex(self.source, r"admin:(?:read|write)")
        self.assertEqual(self.source.count("function_id: ${var.admin_function_id}"), 3)

    def test_cors_is_exact_origin_and_bearer_header_only(self):
        self.assertEqual(self.source.count("origin: ${var.admin_origin}"), 2)
        self.assertEqual(self.source.count("allowedHeaders: [Authorization, Content-Type]"), 2)
        self.assertNotIn("origin: true", self.source)
        self.assertNotIn("origin: '*'", self.source)
        self.assertNotIn("credentials: true", self.source)

    def test_live_gateway_patch_changes_only_two_admin_cors_origins(self):
        patch = LIVE_PATCH.read_text(encoding="utf-8")
        self.assertEqual(patch.count("origin: https://test.club-gravitation.ru"), 2)
        self.assertIn("/admin/applications:", patch)
        self.assertIn("/admin/participants/{id}:", patch)
        self.assertNotRegex(patch, r"(?m)^  /(?:health|applications|photo-uploads(?:/|:))")
        self.assertNotIn("security:", patch)
        self.assertNotIn("components:", patch)


if __name__ == "__main__":
    unittest.main()
