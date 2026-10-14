import json, os, tempfile, unittest, zipfile, subprocess, sys
from pathlib import Path
from unittest.mock import patch
from backend.v5.runtime_config import runtime_settings
from backend.v5.repository import RepositoryUnavailable, FakeRepository
from backend.v5.handler import handler
from backend.v5.legal_text import CONSENT_TEXT_SHA256
from backend.v5.build_production import build_production_zip, WRAPPER
from backend.v5.tests.test_form_2_3 import SHORT
from backend.v5.tests.test_v5 import e


class ProductionCandidateTests(unittest.TestCase):
    def test_prod_has_no_test_configuration_fallback(self):
        with patch.dict(os.environ,{'V5_ENVIRONMENT':'PROD','YDB_ENDPOINT':'synthetic','YDB_DATABASE':'synthetic','V5_TEST_PHOTO_BUCKET':'synthetic','V5_TEST_CONSENT_TEXT_HASH':'TEST-synthetic'},clear=True):
            with self.assertRaisesRegex(RepositoryUnavailable,'missing_prod_configuration'):
                runtime_settings()

    def test_prod_requires_canonical_approved_consent(self):
        env={'V5_ENVIRONMENT':'PROD','V5_PROD_YDB_ENDPOINT':'synthetic','V5_PROD_YDB_DATABASE':'synthetic','V5_PROD_PHOTO_BUCKET':'synthetic','V5_PROD_CONSENT_TEXT_HASH':'TEST-unapproved'}
        with patch.dict(os.environ,env,clear=True):
            with self.assertRaisesRegex(RepositoryUnavailable,'invalid_prod_consent_hash'):runtime_settings()
        with patch.dict(os.environ,{**env,'V5_PROD_CONSENT_TEXT_HASH':CONSENT_TEXT_SHA256},clear=True):
            self.assertEqual(runtime_settings()['environment'],'PROD')

    def test_short_form_is_closed_before_any_prod_repository_access(self):
        with patch.dict(os.environ,{'V5_ENVIRONMENT':'PROD'},clear=True), patch('backend.v5.handler.runtime_repository') as repo:
            response=handler(e(SHORT,'synthetic-short-prod'))
            self.assertEqual(response['statusCode'],503)
            self.assertEqual(json.loads(response['body'])['error']['code'],'short_form_prod_legal_gate_closed')
            repo.assert_not_called()

    def test_production_wrapper_refuses_test_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(build_production_zip(Path(tmp)/'prod.zip')) as archive:
                archive.extractall(tmp)
            output=subprocess.check_output([sys.executable,'-c',"import json,index; print(json.dumps(index.handler({'httpMethod':'GET','path':'/health'})))"],cwd=tmp,env={**os.environ,'V5_ENVIRONMENT':'TEST'},text=True)
            self.assertEqual(json.loads(output)['statusCode'],503)

    def test_production_manifest_and_frozen_source_are_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(build_production_zip(Path(tmp)/'prod.zip')) as archive:
                manifest=json.loads(archive.read('DEPLOYMENT-MANIFEST.json'))
                self.assertEqual(manifest['target'],'PROD')
                self.assertEqual(manifest['short_form_legal_gate'],'CLOSED')
                self.assertIn('legal/frozen/CONSENT-PD-2.2.txt',archive.namelist())
                self.assertFalse(any('/drafts/' in name for name in archive.namelist()))
