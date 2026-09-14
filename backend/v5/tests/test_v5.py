import json
import unittest

from backend.v5.handler import handler
from backend.v5.repository import FakeRepository

P = {
    "full_name": "Иван Тестов", "age": 30, "gender": "Мужчина",
    "city": "Краснодар", "visit_krasnodar": "", "phone": "8 (999) 000-00-01",
    "email": "ivan@example.test", "preferred_contact": "по email",
    "profile_or_messenger_url": "https://example.test/profile",
    "public_profile_url": "https://example.test/ivan", "occupation": "Инженер",
    "life_outside_work": "Спорт", "what_interested": "Новые знакомства",
    "what_participant_brings": "Юмор", "what_friends_value": "Надёжность",
    "desired_connections": ["Новые друзья"], "desired_connections_other": "",
    "values_in_people": "Искренность", "barriers_to_meeting": "",
    "acquaintance_methods": ["Через живой разговор"], "acquaintance_methods_other": "",
    "return_reason": "Хорошая компания", "source": "Сайт / поиск",
    "policy_acknowledged": True, "personal_data_consent": True,
    "consent_version": "CONSENT-PD-2.1", "policy_version": "PPD-2.1",
    "form_version": "FORM-2.2", "environment": "PROD", "granted_at": "spoof",
    "consent_text_hash": "spoof",
}


def e(p=P, k="k1"):
    return {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json", "Idempotency-Key": k},
        "body": json.dumps(p),
    }


class T(unittest.TestCase):
    def test_all(self):
        repo = FakeRepository()
        self.assertEqual(handler({"httpMethod": "GET", "path": "/health"}, repo=repo)["statusCode"], 200)
        self.assertEqual(handler(e(), repo=repo)["statusCode"], 201)
        self.assertEqual(repo.by_key["k1"]["form"]["phone"], "+79990000001")
        self.assertNotIn("raw_payload", repo.by_key["k1"])
        self.assertEqual(handler(e(), repo=repo)["statusCode"], 200)
        self.assertEqual(handler(e({**P, "full_name": "changed"}, "k1"), repo=repo)["statusCode"], 409)
        for key, changes in enumerate((
            {"policy_acknowledged": False}, {"personal_data_consent": False}, {"age": 20},
            {"email": "bad"}, {"public_profile_url": "ftp://x"},
            {"city": "Сочи"}, {"consent_version": "bad"},
        ), 2):
            self.assertEqual(handler(e({**P, **changes}, "k" + str(key)), repo=repo)["statusCode"], 422)


if __name__ == "__main__":
    unittest.main()
