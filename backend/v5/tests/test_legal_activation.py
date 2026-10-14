import json, unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from backend.v5.domain import DomainError, validate, fingerprint
from backend.v5.legal_text import CURRENT_CONSENT_TEXT_SHA256, CONSENT_TEXT_SHA256, verify_current_documents, legal_text_sha256
from backend.v5.repository import FakeRepository
from backend.v5.service import submit
from backend.v5.tests.test_v5 import P, payload_with_photo
from backend.v5.tests.test_form_2_3 import SHORT
from backend.v5.tests import test_ydb_repository as ydb_fixture


class LegalActivationTests(unittest.TestCase):
    def test_prod_legacy_replay_is_preserved_after_old_intake_is_retired(self):
        repo=FakeRepository();repo.environment='PROD'
        payload=payload_with_photo(repo,'historical-prod-22',P)
        with patch.dict('os.environ',{'V5_ALLOW_LEGACY_INTAKE':'true'}):
            original,_=submit(payload,'historical-prod-22',repo,'historical')
        historical=deepcopy(original['consent'])
        with patch.dict('os.environ',{'V5_ALLOW_LEGACY_INTAKE':'false'}):
            replay,again=submit(payload,'historical-prod-22',repo,'replay')
            self.assertTrue(again);self.assertEqual(replay['consent'],historical)
            with self.assertRaises(DomainError) as error:
                submit(payload_with_photo(repo,'stale-new-22',P),'stale-new-22',repo,'stale')
            self.assertEqual(error.exception.code,'legacy_form_retired_reload_required')
    def test_frozen_manifest_matches_all_current_sources(self):
        root=Path(__file__).resolve().parents[3]
        approval=json.loads((root/'legal/approval-2.3.json').read_text(encoding='utf-8'))
        self.assertEqual(approval['approved_at'],'14.10.2026')
        verify_current_documents()
        for document in approval['documents'].values():
            self.assertEqual(legal_text_sha256((root/document['path']).read_bytes()),document['canonical_sha256'])

    def test_new_and_legacy_evidence_and_replay_are_independent(self):
        repo=FakeRepository()
        old_payload=payload_with_photo(repo,'old-22',P)
        old,_=submit(old_payload,'old-22',repo,'old')
        historical=deepcopy(old['consent'])
        current=payload_with_photo(repo,'new-23',{**SHORT,'phone':'+79990000002'})
        new,_=submit(current,'new-23',repo,'new')
        self.assertEqual(new['consent']['consent_version'],'CONSENT-PD-2.3')
        self.assertEqual(new['consent']['policy_version'],'PPD-2.3')
        self.assertEqual(new['consent']['consent_text_hash'],'TEST-'+CURRENT_CONSENT_TEXT_SHA256)
        replay,again=submit(old_payload,'old-22',repo,'replay')
        self.assertTrue(again)
        self.assertEqual(replay['consent'],historical)
        self.assertEqual(historical['consent_text_hash'],'TEST-'+CONSENT_TEXT_SHA256)
        self.assertEqual(new['application_number'],old['application_number']+1)

    def test_mixed_legal_versions_are_rejected(self):
        for payload in ({**SHORT,'consent_version':'CONSENT-PD-2.2'}, {**SHORT,'policy_version':'PPD-2.2'}, {**P,'consent_version':'CONSENT-PD-2.3'}):
            with self.assertRaises(DomainError):validate(payload)

    def test_legacy_short_test_idempotency_does_not_claim_new_consent(self):
        repo=FakeRepository()
        payload=payload_with_photo(repo,'short-before-activation',SHORT)
        old,_=submit(payload,'short-before-activation',repo,'before')
        saved=repo.by_key['short-before-activation']
        saved['payload_fingerprint']=fingerprint(validate(payload))
        saved['consent']['consent_version']='CONSENT-PD-2.2'
        saved['consent']['policy_version']='PPD-2.2'
        historical=deepcopy(saved['consent'])
        with self.assertRaises(DomainError) as error:submit(payload,'short-before-activation',repo,'after')
        self.assertEqual(error.exception.code,'idempotency_conflict')
        self.assertEqual(repo.by_key['short-before-activation']['consent'],historical)

    def test_prod_ydb_binds_exact_versions_hash_and_environment(self):
        tx=ydb_fixture.submission_transaction('activated-ydb')
        repo=ydb_fixture.YdbRepositoryTests().make_repo(tx)
        repo._environment='PROD'
        record=ydb_fixture.make_record()
        record['form']=validate(SHORT)
        record['form_version']='FORM-2.3'
        self.assertTrue(repo.save('activated-ydb',record))
        write=next(p for p in tx.params if '$consent_version' in p)
        self.assertEqual(write['$environment'],'PROD')
        self.assertEqual(write['$form_version'],'FORM-2.3')
        self.assertEqual(write['$consent_version'],'CONSENT-PD-2.3')
        self.assertEqual(write['$policy_version'],'PPD-2.3')
        self.assertEqual(write['$consent_text_hash'],CURRENT_CONSENT_TEXT_SHA256)
