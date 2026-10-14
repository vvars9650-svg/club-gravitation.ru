import re, subprocess, unittest
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
        for name in ('PPD-2.2.txt','CONSENT-PD-2.2.txt'):
            historical=subprocess.check_output(['git','show','eaf7519:legal/frozen/'+name],cwd=ROOT)
            current=(ROOT/'legal/frozen'/name).read_bytes()
            self.assertEqual(current.replace(b'\r\n',b'\n'),historical.replace(b'\r\n',b'\n'))
