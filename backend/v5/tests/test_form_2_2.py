import unittest

from backend.v5.domain import DomainError, FORM_FIELDS, phone, validate
from backend.v5.tests.test_v5 import P


class Form22ContractTests(unittest.TestCase):
    def assert_error(self, changes, code):
        with self.assertRaises(DomainError) as raised:
            validate({**P, **changes})
        self.assertEqual(raised.exception.code, code)

    def test_legal_facts_are_independent_and_versions_are_exact(self):
        self.assert_error({"policy_acknowledged": False}, "policy_acknowledgement_required")
        self.assert_error({"personal_data_consent": False}, "consent_required")
        self.assert_error({"form_version": "FORM-2.1"}, "invalid_legal_version")
        self.assert_error({"policy_version": "PPD-2.0"}, "invalid_legal_version")
        self.assert_error({"consent_version": "CONSENT-PD-2.0"}, "invalid_legal_version")

    def test_required_fields(self):
        for field in ("full_name", "gender", "city", "email", "occupation", "life_outside_work", "source"):
            self.assert_error({field: ""}, "missing_" + field)
        self.assert_error({"desired_connections": []}, "invalid_desired_connections")
        self.assert_error({"acquaintance_methods": []}, "invalid_acquaintance_methods")
        self.assert_error({"photo_object_id": ""}, "photo_required")

    def test_gender_and_conditional_visit(self):
        self.assert_error({"gender": "Предпочитаю обсудить лично"}, "invalid_gender")
        self.assert_error({"city": "Сочи", "visit_krasnodar": ""}, "missing_visit_krasnodar")
        self.assert_error({"city": "Сочи", "visit_krasnodar": "иногда"}, "invalid_visit_krasnodar")
        self.assert_error({"city": "Краснодар", "visit_krasnodar": "Да, регулярно"}, "invalid_visit_krasnodar")
        result = validate({**P, "city": "Сочи", "visit_krasnodar": "Да, время от времени"})
        self.assertEqual(result["visit_krasnodar"], "Да, время от времени")

    def test_other_answers_are_conditional(self):
        self.assert_error(
            {"desired_connections": ["Другое"], "desired_connections_other": ""},
            "missing_desired_connections_other",
        )
        self.assert_error(
            {"acquaintance_methods": ["Другое"], "acquaintance_methods_other": ""},
            "missing_acquaintance_methods_other",
        )
        result = validate({
            **P,
            "desired_connections": ["Новые друзья", "Другое"],
            "desired_connections_other": "Общение по интересам",
            "acquaintance_methods": ["Через живой разговор", "Другое"],
            "acquaintance_methods_other": "На прогулке",
        })
        self.assertEqual(result["desired_connections"][1], "Другое")
        self.assertEqual(result["acquaintance_methods"][1], "Другое")

    def test_phone_validation_and_normalization(self):
        for raw in ("9990000000", "7 999 000-00-00", "8 (999) 000-00-00", "+7 (999) 000-00-00"):
            self.assertEqual(phone(raw), "+79990000000")
        for raw in ("123", "7999000000a", "699900000000", "+8 999 000-00-00", "++79990000000"):
            with self.assertRaises(DomainError):
                phone(raw)

    def test_email_arrays_options_and_legacy_rejection(self):
        for value in ("bad", "name@", "@example.com", "name@example"):
            self.assert_error({"email": value}, "invalid_email")
        self.assert_error({"desired_connections": "Новые друзья"}, "invalid_desired_connections")
        self.assert_error({"acquaintance_methods": ["unknown"]}, "invalid_acquaintance_methods")
        self.assert_error({"source": "Telegram"}, "invalid_source")
        for legacy in (
            "telegram", "interests", "social_comfort", "initiative", "acquaintance_scenario",
            "successful_evening", "unacceptable_behavior", "convenient_days", "comfortable_price",
        ):
            self.assert_error({legacy: "legacy"}, "legacy_form_fields_not_allowed")

    def test_canonical_output_contains_only_current_form_fields(self):
        result = validate(P)
        self.assertEqual(set(result), set(FORM_FIELDS))
        self.assertEqual(result["phone"], "+79990000001")
        self.assertIsInstance(result["desired_connections"], list)
        self.assertIsInstance(result["acquaintance_methods"], list)


if __name__ == "__main__":
    unittest.main()
