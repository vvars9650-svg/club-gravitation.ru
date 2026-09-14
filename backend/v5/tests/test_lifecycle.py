"""Internal-only V5 data lifecycle tests; no HTTP lifecycle routes exist."""

import json
import unittest

from backend.v5.handler import handler
from backend.v5.repository import DESTRUCTION_CLASSIFICATION, FakeRepository
from backend.v5.tests.test_v5 import payload_with_photo


PAYLOAD = {
    "full_name": "Synthetic Person", "age": 30, "gender": "Мужчина", "city": "Краснодар",
    "visit_krasnodar": "", "phone": "+79990000001", "email": "synthetic@example.test",
    "preferred_contact": "по email", "profile_or_messenger_url": "", "public_profile_url": "",
    "occupation": "synthetic", "life_outside_work": "synthetic", "what_interested": "synthetic",
    "what_participant_brings": "synthetic", "what_friends_value": "synthetic",
    "desired_connections": ["Новые друзья"], "desired_connections_other": "",
    "values_in_people": "synthetic", "barriers_to_meeting": "synthetic",
    "acquaintance_methods": ["Через живой разговор"], "acquaintance_methods_other": "",
    "return_reason": "synthetic", "source": "Сайт / поиск", "policy_acknowledged": True,
    "personal_data_consent": True, "consent_version": "CONSENT-PD-2.2",
    "policy_version": "PPD-2.2", "form_version": "FORM-2.2",
}


def event(key, payload=PAYLOAD):
    return {"httpMethod": "POST", "headers": {"Content-Type": "application/json", "Idempotency-Key": key}, "body": json.dumps(payload)}


class LifecycleTests(unittest.TestCase):
    def create_participant(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, "lifecycle-first", PAYLOAD)
        response = handler(event("lifecycle-first", payload), repo=repo)
        self.assertEqual(response["statusCode"], 201)
        participant_id = json.loads(response["body"])["participant_id"]
        return repo, participant_id

    def test_block_existing_and_repeat_is_idempotent(self):
        repo, participant_id = self.create_participant()
        self.assertTrue(repo.block_processing(participant_id, "REQ-BLOCK", "internal_request"))
        self.assertFalse(repo.block_processing(participant_id, "REQ-BLOCK-2", "internal_request"))
        participant = repo.find_participant(participant_id)
        self.assertTrue(participant["processing_blocked"])
        self.assertEqual(participant["processing_block_reason"], "internal_request")

    def test_block_new_participant_persists_lifecycle_fields(self):
        repo, participant_id = self.create_participant()
        participant = repo.find_participant(participant_id)
        self.assertFalse(participant["processing_blocked"])
        self.assertTrue(repo.block_processing(participant_id, "REQ-NEW-BLOCK", "internal_request"))
        participant = repo.find_participant(participant_id)
        self.assertTrue(participant["processing_blocked"])
        self.assertEqual(participant["processing_block_request_id"], "REQ-NEW-BLOCK")

    def test_blocked_participant_cannot_submit_and_creates_no_evidence(self):
        repo, participant_id = self.create_participant()
        repo.block_processing(participant_id, "REQ-BLOCK", "internal_request")
        before = (len(repo.by_key), len(repo.audit))
        payload = payload_with_photo(repo, "lifecycle-second", PAYLOAD)
        response = handler(event("lifecycle-second", payload), repo=repo)
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "processing_blocked")
        self.assertEqual(len(repo.by_key), before[0])
        self.assertEqual(len(repo.audit), before[1])

    def test_subject_lookup_and_destruction_plan(self):
        repo, participant_id = self.create_participant()
        self.assertEqual(repo.find_participant(participant_id)["participant_id"], participant_id)
        self.assertEqual(repo.find_participant_by_phone("+79990000001")["participant_id"], participant_id)
        application_id = next(iter(repo.by_key.values()))["application_id"]
        self.assertEqual(repo.find_application(application_id)["participant_id"], participant_id)
        plan = repo.destruction_plan(participant_id)
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["delete_performed"])
        self.assertEqual(plan["records"]["applications"]["count"], 1)
        self.assertEqual(plan["records"]["participant_phone_keys"]["count"], 1)
        self.assertTrue(plan["records"]["audit_log"]["retention_decision_required"])
        for name, expected in DESTRUCTION_CLASSIFICATION.items():
            self.assertEqual({key: plan["records"][name][key] for key in expected}, expected)
            self.assertNotIn("contains_pii", plan["records"][name])

    def test_lifecycle_audit_never_copies_pii(self):
        repo, participant_id = self.create_participant()
        repo.block_processing(participant_id, "REQ-BLOCK", "internal_request")
        block_audit = repo.audit[-1]
        serialized = json.dumps(block_audit, ensure_ascii=False)
        self.assertEqual(block_audit["action"], "processing_blocked")
        for forbidden in ("+79990000001", "synthetic@example.test", "Synthetic Person", "internal_request"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

