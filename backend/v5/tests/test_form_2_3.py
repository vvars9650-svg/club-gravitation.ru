import json
import unittest

from backend.v5.domain import DomainError, validate
from backend.v5.handler import handler
from backend.v5.admin import admin_handler
from backend.v5.repository import FakeRepository
from backend.v5.tests.test_v5 import P, e, payload_with_photo

SHORT = {key: P[key] for key in (
    'full_name', 'age', 'gender', 'city', 'visit_krasnodar', 'phone', 'email',
    'profile_or_messenger_url', 'photo_object_id', 'policy_acknowledged',
    'personal_data_consent', 'consent_version', 'policy_version')}
SHORT.update(form_version='FORM-2.3', profile_or_messenger_url='Мессенджер @synthetic')


class ShortFormTests(unittest.TestCase):
    def test_free_contact_and_legacy_contract(self):
        self.assertEqual(validate(SHORT)['profile_or_messenger_url'], 'Мессенджер @synthetic')
        self.assertEqual(validate(P)['occupation'], 'Инженер')
        for contact in ('@synthetic', '+79990000001', 'Позвоните вечером', 'https://example.test'):
            self.assertEqual(validate({**SHORT, 'profile_or_messenger_url': contact})['profile_or_messenger_url'], contact)

    def test_invalid_contact_age_and_old_fields(self):
        for changes in ({'profile_or_messenger_url': ''}, {'profile_or_messenger_url': []},
                        {'profile_or_messenger_url': 'x' * 501}, {'age': 30.5}, {'age': True},
                        {'occupation': 'unexpected'}, {'desired_connections': []}):
            with self.assertRaises(DomainError):
                validate({**SHORT, **changes})

    def test_submission_evidence_replay_duplicate_and_admin(self):
        repo = FakeRepository()
        payload = payload_with_photo(repo, 'short-key', SHORT)
        result = handler(e(payload, 'short-key'), repo=repo)
        self.assertEqual(result['statusCode'], 201)
        body = json.loads(result['body'])
        record = repo.by_key['short-key']
        self.assertEqual(record['consent']['form_version'], 'FORM-2.3')
        self.assertEqual(record['consent']['consent_version'], 'CONSENT-PD-2.2')
        self.assertEqual(record['form']['occupation'], '')
        self.assertEqual(handler(e(payload, 'short-key'), repo=repo)['statusCode'], 200)
        changed = {**payload, 'profile_or_messenger_url': '@other'}
        self.assertEqual(handler(e(changed, 'short-key'), repo=repo)['statusCode'], 409)
        duplicate = payload_with_photo(repo, 'short-duplicate', SHORT)
        repeated = json.loads(handler(e(duplicate, 'short-duplicate'), repo=repo)['body'])
        self.assertTrue(repeated['already_registered'])
        self.assertEqual(repeated['application_number'], body['application_number'])
        card = admin_handler({'httpMethod': 'GET', 'path': '/admin/applications/' + body['application_id']}, repo=repo, actor_identity='synthetic-operator')
        self.assertEqual(card['statusCode'], 200)
        self.assertIn('@synthetic', card['body'])
        unauthorized = handler({'httpMethod': 'GET', 'path': '/admin/applications/' + body['application_id']}, repo=repo)
        self.assertEqual(unauthorized['statusCode'], 401)


if __name__ == '__main__':
    unittest.main()
