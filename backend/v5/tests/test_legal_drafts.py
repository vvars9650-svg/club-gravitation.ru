import re, hashlib, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


class LegalDraftTests(unittest.TestCase):
    def test_published_draft_text_has_consistent_versions_and_no_service_notes(self):
        for name in ('CONSENT-PD-2.3.txt','PPD-2.3.txt','FORM-2.3.md'):
            text=(ROOT/'legal/drafts'/name).read_text(encoding='utf-8')
            self.assertIn('2.3',text)
            self.assertIsNone(re.search(r'верси[яи]\s+2\.2',text,re.I))
            for service in ('TEST','payload','profile_or_messenger_url','ГРАНИЦА НОВОЙ ФОРМЫ','Статус: ПРОЕКТ','canonical hash'):
                self.assertNotIn(service,text)
            self.assertIn('контакт',text)

    def test_approved_frozen_baseline_is_byte_identical_to_accepted_head(self):
        # Digests captured from accepted eaf7519; work in shallow CI checkouts.
        digests={'PPD-2.2.txt':'8931c111270f121935c36b734f940a7cef637584cc59a35483514baed793ea3b','CONSENT-PD-2.2.txt':'d5b017fd246b17184d665bb5d1f4ef498618ff523171f4379f56494a73f88cdc'}
        for name, expected in digests.items():
            current=(ROOT/'legal/frozen'/name).read_bytes()
            self.assertEqual(hashlib.sha256(current.replace(b'\r\n',b'\n')).hexdigest(),expected)
